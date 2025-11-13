"""
통합 파이프라인
라즈베리파이에서 효율적으로 실행하기 위한 스트리밍 + 녹화 통합 파이프라인
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo
import threading
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from loguru import logger
from core.config import ConfigManager
from camera.gst_utils import get_video_sink, get_available_h264_decoder, get_available_decoder, create_video_sink_with_properties, get_gstreamer_version, is_gstreamer_1_20_or_later

# Core imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.enums import PipelineMode, ErrorType

# Note: GStreamer는 main.py에서 초기화됨


class GstPipeline:
    """스트리밍과 녹화를 하나의 파이프라인으로 처리하는 통합 파이프라인"""

    def __init__(self, rtsp_url: str, camera_id: str, camera_name: str,
                 window_handle=None, mode: PipelineMode = PipelineMode.STREAMING_ONLY):
        """
        통합 파이프라인 초기화

        Args:
            rtsp_url: RTSP 스트림 URL
            camera_id: 카메라 ID
            camera_name: 카메라 이름
            window_handle: 윈도우 핸들 (스트리밍용)
            mode: 파이프라인 동작 모드
        """
        self.rtsp_url = rtsp_url
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.window_handle = window_handle
        self.mode = mode

        self.pipeline = None
        self.video_sink = None
        self.recording_bin = None
        self.tee = None
        self.streaming_valve = None  # 스트리밍 제어용 Valve 추가
        self.recording_valve = None
        self.bus = None
        self.text_overlay = None  # OSD 텍스트 오버레이
        self._timestamp_update_timer = None  # 타임스탬프 업데이트 타이머
        self.splitmuxsink = None  # splitmuxsink 엘리먼트 (자동 파일 분할)

        self._is_playing = False
        self._is_recording = False
        self._main_loop = None
        self._thread = None
        self._fragment_id = 0  # 파일 분할 ID 추적

        # 녹화 상태 변경 콜백
        self._recording_state_callbacks = []  # (camera_id, is_recording) 콜백 리스트

        # 연결 상태 변경 콜백
        self._connection_state_callbacks = []  # (camera_id, is_connected) 콜백 리스트

        # 녹화 설정 로드
        config = ConfigManager.get_instance()
        recording_config = config.get_recording_config()
        storage_config = config.config.get('storage', {})

        # 녹화 디렉토리 설정 (storage.recording_path 사용)
        recording_path = storage_config.get('recording_path', './recordings')
        self.recording_dir = Path(recording_path) / camera_id

        self.current_recording_file = None
        self.recording_start_time = None

        # 파일 분할 주기 (분 → 나노초 변환, splitmuxsink용)
        rotation_minutes = recording_config.get('rotation_minutes', 10)
        self.file_duration_ns = rotation_minutes * 60 * Gst.SECOND

        # 파일 포맷 저장 (파일명 생성 시 사용)
        self.file_format = recording_config.get('file_format', 'mp4')

        # 비디오 코덱 저장 (depay/parse 엘리먼트 생성 시 사용)
        self.video_codec = recording_config.get('codec', 'h264')


        # 에러 상태 추적
        self._streaming_branch_error = False
        self._recording_branch_error = False
        self._last_error_time = {}

        # 재연결 관리
        self.retry_count = 0
        self.max_retries = 10
        self.reconnect_timer = None

        # 녹화 재시도 관리
        self._recording_retry_timer = None
        self._recording_retry_count = 0
        self._max_recording_retry = 20  # 최대 재시도 횟수 (20회 = 약 2분)
        self._recording_retry_interval = 6.0  # 재시도 간격 (초)
        self._recording_should_auto_resume = False  # 자동 재개 플래그
        self._ever_connected = False  # 최소 1번이라도 연결된 적 있는지 추적

        # 프레임 모니터링 (연결 끊김 조기 감지)
        self._last_frame_time = None  # 마지막 프레임 도착 시간
        self._frame_monitor_timer = None  # 프레임 체크 타이머
        self._frame_timeout_seconds = 5.0  # 프레임 타임아웃 (초)
        self._frame_check_interval = 2.0  # 프레임 체크 간격 (초)

        logger.debug(f"Recording config loaded: recording_path={recording_path}, rotation={rotation_minutes}min, format={self.file_format}, codec={self.video_codec}")

    def register_recording_callback(self, callback):
        """
        녹화 상태 변경 콜백 등록

        Args:
            callback: 콜백 함수 (camera_id, is_recording)를 인자로 받음
        """
        if callback not in self._recording_state_callbacks:
            self._recording_state_callbacks.append(callback)
            logger.debug(f"Recording callback registered for {self.camera_id}")

    def register_connection_callback(self, callback):
        """
        연결 상태 변경 콜백 등록

        Args:
            callback: 콜백 함수 (camera_id, is_connected)를 인자로 받음
        """
        if callback not in self._connection_state_callbacks:
            self._connection_state_callbacks.append(callback)
            logger.debug(f"Connection callback registered for {self.camera_id}")

    def unregister_recording_callback(self, callback):
        """
        녹화 상태 변경 콜백 해제

        Args:
            callback: 해제할 콜백 함수
        """
        if callback in self._recording_state_callbacks:
            self._recording_state_callbacks.remove(callback)
            logger.debug(f"Recording callback unregistered for {self.camera_id}")

    def unregister_connection_callback(self, callback):
        """
        연결 상태 변경 콜백 해제

        Args:
            callback: 해제할 콜백 함수
        """
        if callback in self._connection_state_callbacks:
            self._connection_state_callbacks.remove(callback)
            logger.debug(f"Connection callback unregistered for {self.camera_id}")

    def cleanup_callbacks(self):
        """
        모든 콜백 정리 (파이프라인 종료 시 호출)
        메모리 누수 방지 및 중복 콜백 실행 방지를 위해 사용
        """
        self._recording_state_callbacks.clear()
        self._connection_state_callbacks.clear()
        logger.debug(f"All callbacks cleared for {self.camera_id}")

    def _notify_connection_state_change(self, is_connected: bool):
        """
        연결 상태 변경 시 모든 등록된 콜백 호출

        Args:
            is_connected: 연결 여부
        """
        logger.debug(f"[CONNECTION SYNC] Notifying connection state change: {self.camera_id} -> {is_connected}")
        for callback in self._connection_state_callbacks:
            try:
                callback(self.camera_id, is_connected)
            except Exception as e:
                logger.error(f"Error in connection callback: {e}")

    def _notify_recording_state_change(self, is_recording: bool):
        """
        녹화 상태 변경 시 모든 등록된 콜백 호출

        Args:
            is_recording: 녹화 중 여부
        """
        logger.debug(f"[RECORDING SYNC] Notifying recording state change: {self.camera_id} -> {is_recording}")
        for callback in self._recording_state_callbacks:
            try:
                callback(self.camera_id, is_recording)
            except Exception as e:
                logger.error(f"Error in recording callback: {e}")


    def create_pipeline(self) -> bool:
        """
        통합 파이프라인 생성
        tee 엘리먼트를 사용하여 하나의 스트림을 스트리밍과 녹화로 분기

        Returns:
            True if successful
        """
        try:
            logger.debug(f"Creating unified pipeline for {self.camera_name} (mode: {self.mode.value})")

            # ✅ 파이프라인 재생성 시 녹화 상태 초기화 (재연결 시 상태 불일치 방지)
            if self._is_recording:
                logger.warning(f"[RECONNECT] Resetting stale recording state before pipeline creation")
                self._is_recording = False
                self.recording_start_time = None

            # 파이프라인 생성
            self.pipeline = Gst.Pipeline.new("unified-pipeline")

            # 스트리밍 설정 로드
            config = ConfigManager.get_instance()
            streaming_config = config.get_streaming_config()

            # RTSP 소스
            rtspsrc = Gst.ElementFactory.make("rtspsrc", "source")
            rtspsrc.set_property("location", self.rtsp_url)

            # latency_ms 설정 (기본값: 200ms)
            latency_ms = streaming_config.get("latency_ms", 200)
            rtspsrc.set_property("latency", latency_ms)
            logger.debug(f"RTSP latency set to {latency_ms}ms")

            rtspsrc.set_property("protocols", "tcp")

            # tcp_timeout 설정 (기본값: 10000ms = 10초)
            # GStreamer는 마이크로초 단위이므로 1000을 곱함
            tcp_timeout = streaming_config.get("tcp_timeout", 10000)
            rtspsrc.set_property("tcp-timeout", tcp_timeout * 1000)
            logger.debug(f"TCP timeout set to {tcp_timeout}ms")

            # RTSP Keep-Alive 설정 (연결 끊김 조기 감지)
            # do-rtsp-keep-alive: RTSP 서버에 주기적으로 keep-alive 메시지 전송
            rtspsrc.set_property("do-rtsp-keep-alive", True)

            # timeout: keep-alive 간격 및 응답 타임아웃 (microseconds 단위)
            # 기본값: 5초 (빠른 연결 끊김 감지를 위해)
            # 값이 작을수록 빠르게 감지하지만, 네트워크 부하 증가
            keepalive_timeout = streaming_config.get("keepalive_timeout", 5)
            rtspsrc.set_property("timeout", keepalive_timeout * 1000000)  # microseconds
            logger.debug(f"RTSP keep-alive enabled with {keepalive_timeout}s timeout")

            rtspsrc.set_property("retry", 5)

            # rtspsrc를 파이프라인에 추가
            self.pipeline.add(rtspsrc)
            logger.debug("RTSP source added to pipeline")

            # GStreamer 버전에 따라 다른 파이프라인 구조 사용
            if is_gstreamer_1_20_or_later():
                # GStreamer 1.20+ (Windows): 기존 방식 사용
                # rtspsrc → depay → parse → tee
                logger.debug("[VERSION] GStreamer 1.20+ detected - using legacy pipeline structure")

                # 디페이로드 및 파서 (코덱에 따라 선택)
                if self.video_codec == 'h265' or self.video_codec == 'hevc':
                    depay = Gst.ElementFactory.make("rtph265depay", "depay")
                    parse = Gst.ElementFactory.make("h265parse", "parse")
                    parse.set_property("config-interval", 1)
                    logger.debug("Using H.265/HEVC codec")
                else:  # 기본값: h264
                    depay = Gst.ElementFactory.make("rtph264depay", "depay")
                    parse = Gst.ElementFactory.make("h264parse", "parse")
                    parse.set_property("config-interval", 1)
                    logger.debug("Using H.264 codec")

                if not depay or not parse:
                    raise Exception(f"Failed to create depay/parse elements for codec: {self.video_codec}")

                # Tee 엘리먼트 - 스트림 분기점
                self.tee = Gst.ElementFactory.make("tee", "tee")
                self.tee.set_property("allow-not-linked", True)
                logger.debug("Tee element created with allow-not-linked=True")

                # 엘리먼트를 파이프라인에 추가
                self.pipeline.add(depay)
                self.pipeline.add(parse)
                self.pipeline.add(self.tee)

                # 기본 체인 연결 (소스는 나중에 pad-added 시그널로 연결)
                depay.link(parse)
                parse.link(self.tee)

                # 프레임 모니터링을 위한 Pad Probe 추가 (parse → tee 연결 후)
                parse_src_pad = parse.get_static_pad("src")
                if parse_src_pad:
                    parse_src_pad.add_probe(
                        Gst.PadProbeType.BUFFER,
                        self._on_frame_probe
                    )
                    logger.debug("[FRAME MONITOR] Pad probe added to parser output")

                # RTSP 소스의 동적 패드 연결
                rtspsrc.connect("pad-added", self._on_pad_added, depay)

            else:
                # GStreamer 1.18 (Raspberry Pi): 새로운 방식 사용
                # rtspsrc → jitterbuffer → depay → parse → tee
                logger.debug("[VERSION] GStreamer 1.18 detected - using new pipeline structure with jitterbuffer")
                if not self._create_source_branch():
                    logger.error("Failed to create source branch")
                    return False

            # 항상 두 브랜치 모두 생성 (런타임 중 모드 전환 지원)
            # Valve로 활성화/비활성화 제어
            self._create_streaming_branch()
            self._create_recording_branch()

            # 초기 모드 설정 적용 (Valve 제어)
            self._apply_mode_settings()

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # 윈도우 핸들 설정 (스트리밍 모드인 경우)
            if self.window_handle and self.video_sink:
                self.bus.enable_sync_message_emission()
                self.bus.connect("sync-message::element", self._on_sync_message)

            # 파이프라인 엘리먼트 검증
            if not self._verify_pipeline_elements():
                logger.error("Pipeline element verification failed")
                return False

            logger.info(f"Unified pipeline created for {self.camera_name} (mode: {self.mode.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to create unified pipeline: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _create_source_branch(self):
        """
        소스 브랜치 생성 (rtspsrc → jitterbuffer → depay → parse → tee)
        GStreamer 버전에 따라 다른 파이프라인 구조 사용

        - GStreamer 1.20+ (Windows): rtspsrc → depay → jitterbuffer → parse → tee
        - GStreamer 1.18 (Raspberry Pi): rtspsrc → jitterbuffer → depay → parse → tee
        """
        try:
            # RTSP 소스 (이미 create_pipeline에서 생성됨)
            rtspsrc = self.pipeline.get_by_name("source")
            if not rtspsrc:
                raise Exception("rtspsrc not found in pipeline")

            # Tee 엘리먼트 - 스트림 분기점
            self.tee = Gst.ElementFactory.make("tee", "tee")
            if not self.tee:
                raise Exception("Failed to create tee element")

            self.tee.set_property("allow-not-linked", True)
            self.pipeline.add(self.tee)
            logger.debug("Tee element created with allow-not-linked=True")

            # h264parse 엘리먼트 생성
            if self.video_codec == 'h265' or self.video_codec == 'hevc':
                h264parse = Gst.ElementFactory.make("h265parse", "parse")
                logger.debug("Using H.265 parse for source branch")
            else:  # 기본값: h264
                h264parse = Gst.ElementFactory.make("h264parse", "parse")
                logger.debug("Using H.264 parse for source branch")

            if not h264parse:
                raise Exception(f"Failed to create parse element for codec: {self.video_codec}")

            h264parse.set_property("config-interval", 1)
            self.pipeline.add(h264parse)

            # GStreamer 버전에 따라 다른 파이프라인 구조 사용
            if is_gstreamer_1_20_or_later():
                # GStreamer 1.20+ (Windows): rtspsrc → depay → jitterbuffer → parse → tee
                logger.debug("[VERSION] GStreamer 1.20+ detected - using depay → jitterbuffer → parse order")

                # rtph264depay 생성
                if self.video_codec == 'h265' or self.video_codec == 'hevc':
                    rtph264depay = Gst.ElementFactory.make("rtph265depay", "depay")
                    logger.debug("Using H.265 depay")
                else:
                    rtph264depay = Gst.ElementFactory.make("rtph264depay", "depay")
                    logger.debug("Using H.264 depay")

                if not rtph264depay:
                    raise Exception("Failed to create rtph264depay")

                # wait-for-keyframe 속성 설정 (GStreamer 1.20+에서만 사용 가능)
                rtph264depay.set_property("wait-for-keyframe", True)
                logger.debug("[VERSION] wait-for-keyframe property set (GStreamer 1.20+)")
                self.pipeline.add(rtph264depay)

                # rtpjitterbuffer 생성
                rtpjitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "rtpjitterbuffer")
                if not rtpjitterbuffer:
                    raise Exception("Failed to create rtpjitterbuffer")

                rtpjitterbuffer.set_property("latency", 100)
                self.pipeline.add(rtpjitterbuffer)

                # 연결: depay → jitterbuffer → parse → tee
                if not rtph264depay.link(rtpjitterbuffer):
                    raise Exception("Failed to link rtph264depay → rtpjitterbuffer")
                logger.debug("[SOURCE DEBUG] Linked: rtph264depay → rtpjitterbuffer")

                if not rtpjitterbuffer.link(h264parse):
                    raise Exception("Failed to link rtpjitterbuffer → h264parse")
                logger.debug("[SOURCE DEBUG] Linked: rtpjitterbuffer → h264parse")

                if not h264parse.link(self.tee):
                    raise Exception("Failed to link h264parse → tee")
                logger.debug("[SOURCE DEBUG] Linked: h264parse → tee")

                # 프레임 모니터링을 위한 Pad Probe 추가
                parse_src_pad = h264parse.get_static_pad("src")
                if parse_src_pad:
                    parse_src_pad.add_probe(
                        Gst.PadProbeType.BUFFER,
                        self._on_frame_probe
                    )
                    logger.debug("[FRAME MONITOR] Pad probe added to parser output")

                # RTSP 소스의 동적 패드 연결: rtspsrc → depay
                rtspsrc.connect("pad-added", self._on_rtspsrc_pad_added, rtph264depay)
                logger.debug("[SOURCE DEBUG] Connected pad-added signal: rtspsrc → rtph264depay")

            else:
                # GStreamer 1.18 (Raspberry Pi): rtspsrc → jitterbuffer → depay → parse → tee
                logger.debug("[VERSION] GStreamer 1.18 detected - using jitterbuffer → depay → parse order")

                # rtpjitterbuffer 생성 (먼저)
                rtpjitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "rtpjitterbuffer")
                if not rtpjitterbuffer:
                    raise Exception("Failed to create rtpjitterbuffer")

                rtpjitterbuffer.set_property("latency", 100)
                rtpjitterbuffer.set_property("drop-on-latency", True)
                self.pipeline.add(rtpjitterbuffer)

                # rtph264depay 생성 (나중에)
                if self.video_codec == 'h265' or self.video_codec == 'hevc':
                    rtph264depay = Gst.ElementFactory.make("rtph265depay", "depay")
                    logger.debug("Using H.265 depay")
                else:
                    rtph264depay = Gst.ElementFactory.make("rtph264depay", "depay")
                    logger.debug("Using H.264 depay")

                if not rtph264depay:
                    raise Exception("Failed to create rtph264depay")

                # wait-for-keyframe 속성은 GStreamer 1.20+에서만 사용 가능
                # GStreamer 1.18에서는 이 속성이 없으므로 스킵
                logger.debug("[VERSION] wait-for-keyframe property not available in GStreamer < 1.20")
                self.pipeline.add(rtph264depay)

                # 연결: jitterbuffer → depay → parse → tee
                if not rtpjitterbuffer.link(rtph264depay):
                    raise Exception("Failed to link rtpjitterbuffer → rtph264depay")
                logger.debug("[SOURCE DEBUG] Linked: rtpjitterbuffer → rtph264depay")

                if not rtph264depay.link(h264parse):
                    raise Exception("Failed to link rtph264depay → h264parse")
                logger.debug("[SOURCE DEBUG] Linked: rtph264depay → h264parse")

                if not h264parse.link(self.tee):
                    raise Exception("Failed to link h264parse → tee")
                logger.debug("[SOURCE DEBUG] Linked: h264parse → tee")

                # 프레임 모니터링을 위한 Pad Probe 추가
                parse_src_pad = h264parse.get_static_pad("src")
                if parse_src_pad:
                    parse_src_pad.add_probe(
                        Gst.PadProbeType.BUFFER,
                        self._on_frame_probe
                    )
                    logger.debug("[FRAME MONITOR] Pad probe added to parser output")

                # RTSP 소스의 동적 패드 연결: rtspsrc → jitterbuffer
                rtspsrc.connect("pad-added", self._on_rtspsrc_pad_added, rtpjitterbuffer)
                logger.debug("[SOURCE DEBUG] Connected pad-added signal: rtspsrc → rtpjitterbuffer")

            logger.info("[SOURCE DEBUG] Source branch created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create source branch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _create_streaming_branch(self):
        """스트리밍 브랜치 생성"""
        try:
            # 스트리밍 설정 로드
            config = ConfigManager.get_instance()
            streaming_config = config.get_streaming_config()

            # 스트리밍 큐 - 낮은 지연시간을 위한 설정
            stream_queue = Gst.ElementFactory.make("queue", "stream_queue")
            stream_queue.set_property("max-size-buffers", 10)  # 버퍼 개수 증가 (5 -> 10)
            stream_queue.set_property("max-size-time", 2 * Gst.SECOND)  # 2초 버퍼로 증가
            stream_queue.set_property("max-size-bytes", 0)  # 바이트 제한 없음
            stream_queue.set_property("leaky", 2)  # downstream leaky
            logger.debug("Stream queue configured - buffers=10, time=2s, leaky=downstream")

            # Valve 엘리먼트 - 스트리밍 on/off 제어
            self.streaming_valve = Gst.ElementFactory.make("valve", "streaming_valve")
            # 초기값은 나중에 _apply_mode_settings()에서 설정됨
            # 하지만 파이프라인이 PLAYING 상태로 가기 위해서는 최소 하나의 sink가 데이터를 받아야 함
            # 따라서 스트리밍 브랜치는 기본적으로 열어둠
            self.streaming_valve.set_property("drop", False)  # False = 데이터 흐름 허용 (중요!)
            logger.debug("[VALVE DEBUG] streaming_valve initial state: drop=False (open for pipeline startup)")

            # 디코더 - 설정에 따라 선택
            # use_hardware_acceleration 설정 확인
            use_hw_accel = streaming_config.get("use_hardware_acceleration", True)
            decoder_preference = streaming_config.get("decoder_preference", None)

            if use_hw_accel:
                # 하드웨어 가속 사용: 설정된 우선순위 또는 자동 선택
                decoder_name = get_available_decoder(
                    codec=self.video_codec,
                    prefer_hardware=True,
                    decoder_preference=decoder_preference
                )
                logger.info(f"Hardware acceleration enabled - selected {self.video_codec.upper()} decoder: {decoder_name}")
            else:
                # 소프트웨어 디코더 강제 사용
                decoder_name = get_available_decoder(
                    codec=self.video_codec,
                    prefer_hardware=False,
                    decoder_preference=None
                )
                logger.info(f"Hardware acceleration disabled - using software {self.video_codec.upper()} decoder: {decoder_name}")

            # parse만 있는 경우 소프트웨어 디코더로 폴백
            if decoder_name in ["h264parse", "h265parse"]:
                fallback = "avdec_h265" if self.video_codec in ['h265', 'hevc'] else "avdec_h264"
                logger.warning(f"No hardware decoder available, using software decoder {fallback}")
                decoder_name = fallback

            decoder = Gst.ElementFactory.make(decoder_name, "decoder")

            if not decoder:
                # 폴백 디코더 시도
                fallback = "avdec_h265" if self.video_codec in ['h265', 'hevc'] else "avdec_h264"
                logger.error(f"Failed to create decoder '{decoder_name}', falling back to {fallback}")
                decoder = Gst.ElementFactory.make(fallback, "decoder")

            if not decoder:
                raise Exception(f"Failed to create any {self.video_codec.upper()} decoder (tried: {decoder_name}, fallback)")

            # 비디오 변환
            convert = Gst.ElementFactory.make("videoconvert", "convert")

            # ===== 영상 변환 (Flip/Rotation) 추가 =====
            videoflip = None
            camera_config = self._get_camera_config()
            transform_config = camera_config.get("video_transform", {}) if camera_config else {}

            if transform_config.get("enabled", False):
                # ⭐ IMPORTANT: JSON에서 대소문자 혼용 가능하므로 lower()로 정규화
                flip_mode = transform_config.get("flip", "none").lower()  # 소문자로 변환
                rotation = transform_config.get("rotation", 0)

                method = self._get_videoflip_method(flip_mode, rotation)

                if method is not None:
                    videoflip = Gst.ElementFactory.make("videoflip", "videoflip")
                    if videoflip:
                        videoflip.set_property("method", method)
                        logger.info(f"Video transform enabled: flip={flip_mode}, rotation={rotation}, method={method}")
                    else:
                        logger.warning("Failed to create videoflip element")
                else:
                    logger.debug("Video transform disabled (method=none)")

            # OSD (Text Overlay) - 카메라 이름 및 타임스탬프
            show_timestamp = streaming_config.get("show_timestamp", True)
            show_camera_name = streaming_config.get("show_camera_name", True)

            if show_timestamp or show_camera_name:
                self.text_overlay = Gst.ElementFactory.make("textoverlay", "text_overlay")

                # OSD 설정
                osd_font_size = streaming_config.get("osd_font_size", 14)
                osd_font_color = streaming_config.get("osd_font_color", [255, 255, 255])

                # 폰트 설정
                self.text_overlay.set_property("font-desc", f"Sans Bold {osd_font_size}")

                # 텍스트 색상 (ARGB 형식)
                r, g, b = osd_font_color[0], osd_font_color[1], osd_font_color[2]
                color_argb = 0xFF000000 | (r << 16) | (g << 8) | b
                self.text_overlay.set_property("color", color_argb)

                # 배경 설정 (중요! 텍스트 가독성을 위해 반투명 검은 배경 추가)
                self.text_overlay.set_property("shaded-background", True)

                # 위치 및 스타일 설정 (IT_RNVR.json에서 로드)
                osd_valignment = streaming_config.get("osd_valignment", "top")
                osd_halignment = streaming_config.get("osd_halignment", "left")
                osd_xpad = streaming_config.get("osd_xpad", 10)
                osd_ypad = streaming_config.get("osd_ypad", 10)

                self.text_overlay.set_property("valignment", osd_valignment)  # 수직 정렬
                self.text_overlay.set_property("halignment", osd_halignment)  # 수평 정렬
                self.text_overlay.set_property("xpad", osd_xpad)  # 좌우 패딩
                self.text_overlay.set_property("ypad", osd_ypad)  # 상하 패딩

                logger.debug(f"OSD position: {osd_valignment}/{osd_halignment}, padding: {osd_xpad}/{osd_ypad}")

                # 텍스트 선명도 향상
                self.text_overlay.set_property("line-alignment", "left")
                self.text_overlay.set_property("draw-shadow", False)
                self.text_overlay.set_property("draw-outline", False)

                # 초기 텍스트 설정
                text_parts = []
                if show_camera_name:
                    text_parts.append(self.camera_name)
                if show_timestamp:
                    text_parts.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                initial_text = " | ".join(text_parts)
                self.text_overlay.set_property("text", initial_text)

                logger.info(f"OSD enabled - Camera: {show_camera_name}, Timestamp: {show_timestamp}")
            else:
                self.text_overlay = None
                logger.debug("OSD disabled")

            scale = Gst.ElementFactory.make("videoscale", "scale")

            # 캡슐 필터 (해상도 설정)
            caps_filter = Gst.ElementFactory.make("capsfilter", "caps_filter")
            caps = Gst.Caps.from_string("video/x-raw,width=1280,height=720")
            caps_filter.set_property("caps", caps)

            # 최종 큐 - 비디오 싱크 전 버퍼링
            final_queue = Gst.ElementFactory.make("queue", "final_queue")
            final_queue.set_property("max-size-buffers", 2)  # 최소 버퍼
            final_queue.set_property("max-size-time", 0)
            final_queue.set_property("max-size-bytes", 0)
            final_queue.set_property("leaky", 2)  # downstream leaky

            # 비디오 싱크 (플랫폼별 자동 선택 - 공통 유틸리티 사용)
            video_sink_name = get_video_sink()
            self.video_sink = create_video_sink_with_properties(
                video_sink_name,
                sync=False,  # 비동기 렌더링
                force_aspect_ratio=True,
                async_handling=False  # async를 false로 설정하여 즉시 PLAYING 상태로 전환
            )

            if not self.video_sink:
                logger.error(f"Failed to create video sink: {video_sink_name}")
                # 폴백으로 기본 비디오 싱크 생성
                self.video_sink = Gst.ElementFactory.make("autovideosink", "videosink")
                if self.video_sink:
                    self.video_sink.set_property("sync", False)
                else:
                    self.video_sink = Gst.ElementFactory.make("fakesink", "videosink")
                    if self.video_sink:
                        self.video_sink.set_property("sync", False)
                        self.video_sink.set_property("silent", True)

            # 추가 속성 설정 (video_sink가 성공적으로 생성된 경우)
            if self.video_sink:
                try:
                    # QoS 활성화
                    self.video_sink.set_property("qos", True)
                except:
                    pass  # 속성이 없으면 무시

                try:
                    # 최대 지연 시간 설정 (20ms)
                    self.video_sink.set_property("max-lateness", 20 * Gst.MSECOND)
                except:
                    pass  # 속성이 없으면 무시

            # 엘리먼트를 파이프라인에 추가
            self.pipeline.add(stream_queue)
            self.pipeline.add(self.streaming_valve)
            self.pipeline.add(decoder)
            self.pipeline.add(convert)
            if videoflip:
                self.pipeline.add(videoflip)
            if self.text_overlay:
                self.pipeline.add(self.text_overlay)
            self.pipeline.add(scale)
            self.pipeline.add(caps_filter)
            self.pipeline.add(final_queue)
            self.pipeline.add(self.video_sink)

            # 엘리먼트 연결
            logger.debug("[STREAMING DEBUG] Linking streaming branch elements...")

            if not stream_queue.link(self.streaming_valve):
                raise Exception("Failed to link stream_queue → streaming_valve")
            logger.debug("[STREAMING DEBUG] Linked: stream_queue → streaming_valve")

            # v4l2 디코더의 경우 colorimetry 협상 문제 해결을 위한 capssetter 추가
            # GStreamer 1.18에서 v4l2h264dec는 h264parse가 제공하는 colorimetry 값을 거부할 수 있음
            # 해결: capssetter로 v4l2h264dec가 지원하는 colorimetry(bt709)로 강제 설정
            if decoder_name.startswith('v4l2') and not is_gstreamer_1_20_or_later():
                capssetter = Gst.ElementFactory.make("capssetter", "capssetter")
                if capssetter:
                    # v4l2h264dec가 지원하는 colorimetry로 강제 설정
                    # bt709는 v4l2h264dec가 지원하는 colorimetry 중 하나
                    capssetter_caps = Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au,colorimetry=bt709")
                    capssetter.set_property("caps", capssetter_caps)
                    self.pipeline.add(capssetter)

                    if not self.streaming_valve.link(capssetter):
                        raise Exception("Failed to link streaming_valve → capssetter")
                    logger.debug("[V4L2] Linked: streaming_valve → capssetter")

                    if not capssetter.link(decoder):
                        raise Exception("Failed to link capssetter → decoder")
                    logger.debug(f"[V4L2] Linked: capssetter → decoder (forced colorimetry=bt709 for v4l2)")
                else:
                    logger.warning("Failed to create capssetter, linking directly")
                    if not self.streaming_valve.link(decoder):
                        raise Exception("Failed to link streaming_valve → decoder")
                    logger.debug("[STREAMING DEBUG] Linked: streaming_valve → decoder")
            else:
                # 일반 디코더는 직접 연결
                if not self.streaming_valve.link(decoder):
                    raise Exception("Failed to link streaming_valve → decoder")
                logger.debug("[STREAMING DEBUG] Linked: streaming_valve → decoder")

            # v4l2 디코더의 경우 caps 협상을 위한 추가 처리 (GStreamer 1.18 호환)
            # v4l2h264dec는 DMA 버퍼를 출력하므로 명시적 caps 필터가 필요할 수 있음
            if decoder_name.startswith('v4l2') and not is_gstreamer_1_20_or_later():
                # v4l2 디코더 → caps 필터 → convert 순서로 연결
                decoder_caps_filter = Gst.ElementFactory.make("capsfilter", "decoder_caps_filter")
                # 더 구체적인 caps 설정: I420 또는 NV12 형식 명시
                decoder_caps = Gst.Caps.from_string("video/x-raw,format=(string){I420,NV12,NV21}")
                decoder_caps_filter.set_property("caps", decoder_caps)
                self.pipeline.add(decoder_caps_filter)

                if not decoder.link(decoder_caps_filter):
                    raise Exception("Failed to link decoder → decoder_caps_filter")
                logger.debug(f"[V4L2] Linked: decoder → decoder_caps_filter (caps: {decoder_caps.to_string()})")

                if not decoder_caps_filter.link(convert):
                    raise Exception("Failed to link decoder_caps_filter → convert")
                logger.debug("[STREAMING DEBUG] Linked: decoder_caps_filter → convert")
            else:
                # 일반 디코더는 직접 연결
                if not decoder.link(convert):
                    raise Exception("Failed to link decoder → convert")
                logger.debug("[STREAMING DEBUG] Linked: decoder → convert")

            # 연결 순서: convert → [videoflip] → [textoverlay] → scale
            current_element = convert

            # videoflip이 있으면 연결
            if videoflip:
                if not current_element.link(videoflip):
                    raise Exception(f"Failed to link {current_element.get_name()} → videoflip")
                logger.debug(f"[STREAMING DEBUG] Linked: {current_element.get_name()} → videoflip")
                current_element = videoflip

            # textoverlay가 있으면 연결
            if self.text_overlay:
                if not current_element.link(self.text_overlay):
                    raise Exception(f"Failed to link {current_element.get_name()} → text_overlay")
                logger.debug(f"[STREAMING DEBUG] Linked: {current_element.get_name()} → text_overlay")
                current_element = self.text_overlay

            # scale 연결
            if not current_element.link(scale):
                raise Exception(f"Failed to link {current_element.get_name()} → scale")
            logger.debug(f"[STREAMING DEBUG] Linked: {current_element.get_name()} → scale")

            if not scale.link(caps_filter):
                raise Exception("Failed to link scale → caps_filter")
            logger.debug("[STREAMING DEBUG] Linked: scale → caps_filter")

            if not caps_filter.link(final_queue):
                raise Exception("Failed to link caps_filter → final_queue")
            logger.debug("[STREAMING DEBUG] Linked: caps_filter → final_queue")

            if not final_queue.link(self.video_sink):
                raise Exception("Failed to link final_queue → video_sink")
            logger.debug("[STREAMING DEBUG] Linked: final_queue → video_sink")

            # 동적패드 : Tee에서 스트리밍 큐로 연결
            # - Tee는 동적으로 출력 개수가 결정됨 (1개, 2개, 3개...)

            # GStreamer 버전 호환성 관련
            # - 윈도우 PC: GStreamer 1.26.7 (최신 버전), 라즈베리파이: GStreamer 1.18.4 (구 버전)
            # tee_pad = self.tee.request_pad_simple("src_%u")
            if is_gstreamer_1_20_or_later():
                tee_pad = self.tee.request_pad_simple("src_%u")
            else:
                # GStreamer 1.18 호환 (라즈베리파이)
                pad_template = self.tee.get_pad_template("src_%u")
                tee_pad = self.tee.request_pad(pad_template, None, None)

            queue_pad = stream_queue.get_static_pad("sink")
            link_result = tee_pad.link(queue_pad)

            if link_result != Gst.PadLinkReturn.OK:
                raise Exception(f"Failed to link tee → stream_queue (result: {link_result})")
            logger.debug("[STREAMING DEBUG] Linked: tee → stream_queue")

            logger.debug("[STREAMING DEBUG] Streaming branch created successfully")

        except Exception as e:
            logger.error(f"Failed to create streaming branch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise  # 상위로 예외 전파

    def _create_recording_branch(self):
        """녹화 브랜치 생성 (splitmuxsink + valve 사용)"""
        try:
            # 녹화 디렉토리 생성 시도 (실패해도 파이프라인은 생성)
            try:
                self.recording_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"[RECORDING DEBUG] Recording directory created: {self.recording_dir}")
            except Exception as dir_err:
                logger.error(f"[STORAGE] Failed to create recording directory: {dir_err}")
                logger.error(f"[STORAGE] Recording will be DISABLED until storage path becomes available")
                # 녹화 경로 사용 불가 플래그 설정
                self._recording_branch_error = True

            # 녹화 큐 - 안정성을 위한 설정
            record_queue = Gst.ElementFactory.make("queue", "record_queue")
            record_queue.set_property("max-size-buffers", 0)  # 버퍼 개수 제한 없음
            record_queue.set_property("max-size-time", 5 * Gst.SECOND)  # 5초 버퍼
            record_queue.set_property("max-size-bytes", 50 * 1024 * 1024)  # 50MB 버퍼
            record_queue.set_property("leaky", 2)  # downstream leaky

            logger.debug("[RECORDING DEBUG] Record queue configured")

            # Valve 엘리먼트 - 녹화 on/off 제어
            self.recording_valve = Gst.ElementFactory.make("valve", "recording_valve")
            self.recording_valve.set_property("drop", True)  # 초기에는 녹화 중지
            logger.debug("[VALVE DEBUG] recording_valve initial state: drop=True (closed)")

            # Parse 엘리먼트 - 녹화용 (코덱에 따라 선택)
            if self.video_codec == 'h265' or self.video_codec == 'hevc':
                record_parse = Gst.ElementFactory.make("h265parse", "record_parse")
                logger.debug("Using H.265 parse for recording")
            else:  # 기본값: h264
                record_parse = Gst.ElementFactory.make("h264parse", "record_parse")
                logger.debug("Using H.264 parse for recording")

            if not record_parse:
                raise Exception(f"Failed to create record_parse for codec: {self.video_codec}")

            # 키프레임 설정
            record_parse.set_property("config-interval", 1)  # 1초마다 키프레임 확인

            # splitmuxsink 생성 (자동 파일 분할 지원)
            self.splitmuxsink = Gst.ElementFactory.make("splitmuxsink", "splitmuxsink")
            if not self.splitmuxsink:
                raise Exception("Failed to create splitmuxsink")

            # 파일 분할 시간 설정 (나노초 단위)
            self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
            logger.debug(f"[RECORDING DEBUG] splitmuxsink max-size-time: {self.file_duration_ns / Gst.SECOND}s")

            # 시간 기반 분할이 실패할 경우를 대비
            max_file_size = 100 * 1024 * 1024  # 100MB
            self.splitmuxsink.set_property("max-size-bytes", max_file_size)
            logger.debug(f"[RECORDING DEBUG] splitmuxsink max-size-bytes: {max_file_size} bytes")            

            # muxer 설정 (파일 포맷에 따라)
            if self.file_format == 'mp4':
                muxer_factory = "mp4mux"
            elif self.file_format == 'mkv':
                muxer_factory = "matroskamux"
            elif self.file_format == 'avi':
                muxer_factory = "avimux"
            else:
                logger.warning(f"Unsupported format '{self.file_format}', using matroskamux")
                muxer_factory = "matroskamux"

            self.splitmuxsink.set_property("muxer-factory", muxer_factory)

            # muxer 속성 설정 (mp4의 경우 fragment 설정)
            if self.file_format == 'mp4':
                # mp4mux 속성 설정: GstStructure 객체로 생성
                # fragment-duration: 밀리초 단위
                # streamable: false로 변경하여 완전한 moov atom 생성 보장 (파일 무결성 향상)
                # faststart: true로 설정하여 moov atom을 파일 앞쪽에 배치 (재생 성능 향상)
                muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=false,faststart=true")
                if muxer_props:
                    self.splitmuxsink.set_property("muxer-properties", muxer_props)
                    logger.debug("[RECORDING DEBUG] MP4 muxer properties set: fragment-duration=1000ms, streamable=false, faststart=true")
                else:
                    logger.warning("[RECORDING DEBUG] Failed to create muxer-properties structure, using defaults")

            # splitmuxsink 설정
            self.splitmuxsink.set_property("async-handling", True)  # 비동기 처리
            self.splitmuxsink.set_property("send-keyframe-requests", True)  # 키프레임 요청

            # async-finalize 속성 추가 (GStreamer 1.16+)
            # 파일 finalize를 비동기로 처리하여 파이프라인 중단 없이 파일 완료
            try:
                self.splitmuxsink.set_property("async-finalize", True)
                logger.debug("[RECORDING DEBUG] async-finalize enabled for smooth file finalization")
            except:
                logger.debug("[RECORDING DEBUG] async-finalize not supported in this GStreamer version")

            # format-location 시그널 연결 - 파일명 동적 생성
            self._recording_fragment_id = 0
            self.splitmuxsink.connect("format-location", self._on_format_location)

            logger.debug(f"[RECORDING DEBUG] splitmuxsink configured with format-location handler")

            # 엘리먼트를 파이프라인에 추가
            self.pipeline.add(record_queue)
            self.pipeline.add(self.recording_valve)
            self.pipeline.add(record_parse)
            self.pipeline.add(self.splitmuxsink)

            # 엘리먼트 연결: queue → valve → parse → splitmuxsink
            logger.debug("[RECORDING DEBUG] Linking recording branch elements...")

            if not record_queue.link(self.recording_valve):
                raise Exception("Failed to link record_queue → recording_valve")
            logger.debug("[RECORDING DEBUG] Linked: record_queue → recording_valve")

            if not self.recording_valve.link(record_parse):
                raise Exception("Failed to link recording_valve → record_parse")
            logger.debug("[RECORDING DEBUG] Linked: recording_valve → record_parse")

            if not record_parse.link(self.splitmuxsink):
                raise Exception("Failed to link record_parse → splitmuxsink")
            logger.debug("[RECORDING DEBUG] Linked: record_parse → splitmuxsink")

            # 동적패드 : Tee에서 녹화 큐로 연결
            # - Tee는 동적으로 출력 개수가 결정됨 (1개, 2개, 3개...)
            
            # GStreamer 버전 호환성 관련
            # - 윈도우 PC: GStreamer 1.26.7 (최신 버전), 라즈베리파이: GStreamer 1.18.4 (구 버전)
            # tee_pad = self.tee.request_pad_simple("src_%u")
            if is_gstreamer_1_20_or_later():
                tee_pad = self.tee.request_pad_simple("src_%u")
            else:
                # GStreamer 1.18 호환 (라즈베리파이)
                pad_template = self.tee.get_pad_template("src_%u")
                tee_pad = self.tee.request_pad(pad_template, None, None)


            queue_pad = record_queue.get_static_pad("sink")
            link_result = tee_pad.link(queue_pad)

            if link_result != Gst.PadLinkReturn.OK:
                raise Exception(f"Failed to link tee → record_queue (result: {link_result})")
            logger.debug("[RECORDING DEBUG] Linked: tee → record_queue")

            logger.info("[RECORDING DEBUG] Recording branch created successfully with splitmuxsink")

        except Exception as e:
            logger.error(f"Failed to create recording branch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise  # 상위로 예외 전파

    def _on_pad_added(self, src, pad, depay):
        """
        RTSP 소스의 동적 패드 연결 (GStreamer 1.20+ 기존 방식)

        Args:
            src: rtspsrc 엘리먼트
            pad: 동적 패드
            depay: depay 엘리먼트
        """
        pad_caps = pad.get_current_caps()
        if not pad_caps:
            return

        structure = pad_caps.get_structure(0)
        name = structure.get_name()

        if name.startswith("application/x-rtp"):
            sink_pad = depay.get_static_pad("sink")
            if not sink_pad.is_linked():
                pad.link(sink_pad)
                logger.debug(f"Linked RTP pad: {name}")

    def _on_rtspsrc_pad_added(self, src, pad, target_element):
        """
        RTSP 소스의 동적 패드 연결 (GStreamer 1.18 새로운 방식)

        Args:
            src: rtspsrc 엘리먼트
            pad: 동적 패드
            target_element: 연결할 대상 엘리먼트 (jitterbuffer)
        """
        logger.info(f"[PAD-ADDED] pad-added signal received from {src.get_name()}, pad: {pad.get_name()}")

        pad_caps = pad.get_current_caps()
        if not pad_caps:
            logger.warning(f"[PAD-ADDED] No caps available for pad {pad.get_name()}")
            return

        structure = pad_caps.get_structure(0)
        name = structure.get_name()
        logger.info(f"[PAD-ADDED] Pad caps: {name}")

        if name.startswith("application/x-rtp"):
            sink_pad = target_element.get_static_pad("sink")
            if not sink_pad:
                logger.error(f"[PAD-ADDED] Target element {target_element.get_name()} has no sink pad")
                return

            if not sink_pad.is_linked():
                ret = pad.link(sink_pad)
                if ret == Gst.PadLinkReturn.OK:
                    logger.success(f"[PAD-ADDED] ✓ Linked RTP pad: {name} → {target_element.get_name()}")
                else:
                    logger.error(f"[PAD-ADDED] ✗ Failed to link RTP pad: {name} → {target_element.get_name()} (result: {ret})")
            else:
                logger.warning(f"[PAD-ADDED] Sink pad already linked for {target_element.get_name()}")
        else:
            logger.debug(f"[PAD-ADDED] Ignoring non-RTP pad: {name}")

    def _on_sync_message(self, bus, message):
        """동기 메시지 처리 (윈도우 핸들 설정)"""
        if message.get_structure() is None:
            return

        if message.get_structure().get_name() == 'prepare-window-handle':
            if self.window_handle and self.video_sink:
                try:
                    GstVideo.VideoOverlay.set_window_handle(self.video_sink, self.window_handle)
                    logger.debug(f"Window handle set: {self.window_handle}")
                except Exception as e:
                    logger.error(f"Failed to set window handle: {e}")

    def _on_frame_probe(self, pad, info):
        """
        프레임 도착 시 호출되는 Pad Probe 콜백
        매 프레임마다 호출되어 마지막 프레임 도착 시간을 업데이트
        """
        self._last_frame_time = time.time()
        return Gst.PadProbeReturn.OK

    def _check_frame_timeout(self):
        """
        프레임 타임아웃 체크 (주기적으로 호출)
        마지막 프레임 도착 시간을 확인하여 연결 끊김 감지
        """
        try:
            if not self._is_playing:
                return True  # 파이프라인이 중지되면 타이머 계속 유지

            if self._last_frame_time is None:
                # 아직 프레임이 도착하지 않음 (초기 연결 중)
                return True

            elapsed = time.time() - self._last_frame_time
            if elapsed > self._frame_timeout_seconds:
                logger.warning(f"[FRAME MONITOR] No frames received for {elapsed:.1f}s (timeout: {self._frame_timeout_seconds}s)")
                logger.warning(f"[FRAME MONITOR] Connection lost detected - starting reconnection")

                # 연결 끊김으로 판단하고 재연결 시작
                self._async_stop_and_reconnect()

                return False  # 타이머 중지 (재연결 시 새로 시작)

            return True  # 타이머 계속

        except Exception as e:
            logger.error(f"[FRAME MONITOR] Error in frame timeout check: {e}")
            return True

    def _start_frame_monitor(self):
        """프레임 모니터링 시작"""
        try:
            # 마지막 프레임 시간 초기화
            self._last_frame_time = time.time()

            # 기존 타이머가 있으면 중지
            if self._frame_monitor_timer:
                GLib.source_remove(self._frame_monitor_timer)
                self._frame_monitor_timer = None

            # 새 타이머 시작
            interval_ms = int(self._frame_check_interval * 1000)
            self._frame_monitor_timer = GLib.timeout_add(interval_ms, self._check_frame_timeout)
            logger.info(f"[FRAME MONITOR] Started - checking every {self._frame_check_interval}s, timeout: {self._frame_timeout_seconds}s")

        except Exception as e:
            logger.error(f"[FRAME MONITOR] Failed to start: {e}")

    def _stop_frame_monitor(self):
        """프레임 모니터링 중지"""
        try:
            if self._frame_monitor_timer:
                GLib.source_remove(self._frame_monitor_timer)
                self._frame_monitor_timer = None
                logger.debug("[FRAME MONITOR] Stopped")

            self._last_frame_time = None

        except Exception as e:
            logger.error(f"[FRAME MONITOR] Failed to stop: {e}")

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            src_name = message.src.get_name() if message.src else "unknown"
            logger.error(f"Pipeline error from {src_name}: {err}")
            logger.debug(f"Error debug info: {debug}")

            # 에러 타입 분석
            error_str = str(err)
            debug_str = str(debug) if debug else ""
            error_code = err.code

            # 에러 분류
            error_type = self._classify_error(src_name, err, debug, error_code)

            # 에러 타입별 처리
            # - RTSP 네트워크 에러
            if error_type == ErrorType.RTSP_NETWORK:
                # self._handle_rtsp_error(err)
                logger.info("ErrorType.RTSP_NETWORK")
            # - 저장소 분리
            elif error_type == ErrorType.STORAGE_DISCONNECTED:
                self._handle_storage_error(err)
                logger.info("ErrorType.STORAGE_DISCONNECTED")
            # - 디스크 Full
            elif error_type == ErrorType.DISK_FULL:
                self._handle_disk_full_error(err)
            # - 디코더 에러
            elif error_type == ErrorType.DECODER:
                self._handle_decoder_error(err)
            # - Video Sink 에러
            elif error_type == ErrorType.VIDEO_SINK:
                self._handle_videosink_error(err)
            # - 알 수 없는 에러
            else:                
                self._handle_unknown_error(src_name, err)

        elif t == Gst.MessageType.EOS:
            logger.info("End of stream")
            # EOS는 녹화 중지나 파일 회전에서 발생할 수 있음
            # 녹화 중지 시에는 회전하지 않음
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                logger.info(f"[STATE] Pipeline state: {old_state.value_nick} → {new_state.value_nick}")

                # PLAYING 상태 전환 시 추가 정보
                if new_state == Gst.State.PLAYING:
                    logger.success(f"[STATE] ✓ Pipeline now PLAYING - frames should start flowing")
        elif t == Gst.MessageType.BUFFERING:
            # 네트워크 버퍼링 메시지 처리 - 불필요한 재연결 방지
            percent = message.parse_buffering()
            src_name = message.src.get_name() if message.src else "unknown"

            if percent < 100:
                logger.info(f"[BUFFERING] {src_name}: {percent}% - Network slow, buffering...")
                # 버퍼링 중이므로 재연결하지 않음
                # 필요 시 파이프라인 일시 정지 고려 가능
                # self.pipeline.set_state(Gst.State.PAUSED)
            else:
                logger.info(f"[BUFFERING] {src_name}: Complete (100%)")
                # 버퍼링 완료 - 재생 재개
                # self.pipeline.set_state(Gst.State.PLAYING)

        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            src_name = message.src.get_name() if message.src else "unknown"
            logger.warning(f"Pipeline warning from {src_name}: {warn}")
            if src_name in ["splitmuxsink", "record_parse", "recording_valve"]:
                logger.warning(f"[RECORDING DEBUG] Recording branch warning: {warn}")

    def _classify_error(self, src_name, err, debug, error_code):
        """
        에러 타입 분류 - GStreamer 에러 도메인 우선, 메시지 문자열은 fallback

        분류 우선순위:
        1. GStreamer error domain (Gst.ResourceError, Gst.StreamError 등)
        2. 소스 엘리먼트 이름 (source, sink, splitmuxsink 등)
        3. 에러 메시지 문자열 (최후 fallback)
        """
        error_str = str(err).lower()
        debug_str = str(debug).lower() if debug else ""

        # 1. GStreamer 에러 도메인 우선 확인
        try:
            domain = err.domain

            # ResourceError: 리소스 접근 관련 에러 (네트워크, 파일, 디스크 등)
            if domain == Gst.ResourceError.quark():
                # 리소스를 찾을 수 없음 (RTSP 연결 실패, 파일 없음)
                if error_code == Gst.ResourceError.NOT_FOUND:
                    if src_name == "source":
                        return ErrorType.RTSP_NETWORK
                    else:
                        return ErrorType.STORAGE_DISCONNECTED

                # 쓰기 실패 (파일 쓰기, 네트워크 쓰기)
                elif error_code == Gst.ResourceError.OPEN_WRITE:
                    if src_name == "source":
                        return ErrorType.RTSP_NETWORK
                    else:
                        return ErrorType.STORAGE_DISCONNECTED

                # 읽기 실패
                elif error_code == Gst.ResourceError.READ:
                    if src_name == "source":
                        return ErrorType.RTSP_NETWORK
                    else:
                        return ErrorType.STORAGE_DISCONNECTED

                # 디스크 용량 부족
                elif error_code == Gst.ResourceError.NO_SPACE_LEFT:
                    return ErrorType.DISK_FULL

                # 파일/리소스 열기 실패
                elif error_code == Gst.ResourceError.OPEN_READ:
                    if src_name == "source":
                        return ErrorType.RTSP_NETWORK

                # 기타 리소스 에러
                elif src_name == "source":
                    return ErrorType.RTSP_NETWORK
                elif (src_name.startswith("sink") or
                      "splitmuxsink" in src_name or
                      "mux" in src_name or          # mp4mux, matroskamux 등
                      "filesink" in src_name):       # 내부 filesink
                    return ErrorType.STORAGE_DISCONNECTED

            # StreamError: 스트림 처리 관련 에러 (디코딩, 형식 등)
            elif domain == Gst.StreamError.quark():
                if src_name == "source":
                    # RTSP 스트림 에러는 네트워크 문제일 가능성 높음
                    return ErrorType.RTSP_NETWORK
                elif "dec" in src_name:
                    return ErrorType.DECODER

            # CoreError: GStreamer 코어 에러 (상태 변경 실패 등)
            elif domain == Gst.CoreError.quark():
                if error_code == Gst.CoreError.STATE_CHANGE:
                    if (src_name.startswith("sink") or
                        "splitmuxsink" in src_name or
                        "mux" in src_name or          # mp4mux, matroskamux 등
                        "filesink" in src_name):       # 내부 filesink
                        return ErrorType.STORAGE_DISCONNECTED

        except Exception as domain_err:
            # 도메인 확인 실패 시 fallback으로 계속
            logger.debug(f"Error domain check failed: {domain_err}")

        # 2. 소스 엘리먼트 이름 기반 분류 (기존 로직 유지)
        if src_name == "source":
            # RTSP 소스 에러 코드
            # 1: Internal data stream error
            # 7: Could not open (재연결 타임아웃)
            # 9: Could not read
            # 10: Could not write
            if error_code in [1, 7, 9, 10]:
                return ErrorType.RTSP_NETWORK

        # 저장소 관련 sink/muxer 에러
        if (src_name.startswith("sink") or
            "splitmuxsink" in src_name or
            "mux" in src_name or          # mp4mux, matroskamux 등
            "filesink" in src_name):       # 내부 filesink
            # Could not write (저장소 쓰기 실패)
            if (error_code == 10 and
                "could not write" in error_str and
                ("permission denied" in debug_str or
                 "file descriptor" in debug_str)):
                return ErrorType.STORAGE_DISCONNECTED

            # No file name specified (파일 경로 접근 불가)
            if (error_code == 3 and
                "no file name specified" in error_str and
                "gst_file_sink_open_file" in debug_str):
                return ErrorType.STORAGE_DISCONNECTED

            # State change failed (Sink 시작 실패)
            if (error_code == 4 and
                "state change failed" in error_str and
                ("failed to start" in debug_str or "gstbasesink.c" in debug_str)):
                return ErrorType.STORAGE_DISCONNECTED

        # 3. 에러 메시지 문자열 기반 분류 (최후 fallback)
        # 디스크 용량 부족
        if ("space" in error_str or "no space" in error_str):
            return ErrorType.DISK_FULL

        # 디코더 에러
        if "dec" in src_name and "decode" in error_str:
            return ErrorType.DECODER

        # Video sink 에러
        if "videosink" in src_name or "output window" in error_str:
            return ErrorType.VIDEO_SINK

        return ErrorType.UNKNOWN

    def _handle_rtsp_error(self, err):
        """RTSP 에러 처리 - 전체 재시작"""
        logger.critical(f"[RTSP] Network error: {err}")
        
        # 1. 스레드 join 문제 해결 (우선순위: 높음)
        # 문제: GLib 스레드에서 자기 자신을 join 불가 해결책: 에러 핸들러에서 비동기로 정지 처리
        # GLib 스레드에서 직접 stop() 호출하지 않고, 별도 스레드로 비동기 처리
        threading.Thread(target=self._async_stop_and_reconnect, daemon=True).start()    

    def _handle_storage_error(self, err):
        """저장소 에러 처리 - Recording Branch만 중지"""
        logger.critical(f"[STORAGE] USB disconnected: {err}")

        # 1. 녹화 중지 (storage_error 플래그로 split-now 신호 건너뛰기)
        self.stop_recording(storage_error=True)

        # 2. 에러 플래그 설정
        self._recording_branch_error = True
        self._last_error_time["recording"] = time.time()

        # 3. 자동 재개 플래그 설정 (녹화 중이었으므로 USB 복구 시 자동 재개)
        self._recording_should_auto_resume = True

        # 4. 녹화 재시도 스케줄링 시작
        self._schedule_recording_retry()

        logger.info("[STREAMING] Streaming continues")
        logger.info("[RECORDING] Will automatically resume when storage is available")

    def _handle_disk_full_error(self, err):
        """디스크 Full 처리 - 자동 정리"""
        logger.critical(f"[DISK] Disk full: {err}")
        self._handle_disk_full()

    def _handle_disk_full(self):
        """디스크 용량 부족 처리 - 자동 정리 및 재시도"""
        logger.critical("[DISK] Disk full detected, attempting auto cleanup")

        # 1. 녹화 중지
        if self._is_recording:
            logger.info("[DISK] Stopping recording due to disk full")
            self.stop_recording()

        # 2. StorageService를 통한 자동 정리
        try:
            from core.storage import StorageService
            storage_service = StorageService()

            # 오래된 파일 삭제 (7일 이상)
            deleted_count = storage_service.auto_cleanup(
                max_age_days=7,
                min_free_space_gb=2.0
            )

            logger.info(f"[DISK] Cleaned up {deleted_count} old files")

            # 3. 공간 확보 확인
            time.sleep(1.0)
            free_gb = storage_service.get_free_space_gb(str(self.recording_dir))

            if free_gb >= 2.0:
                logger.success(f"[DISK] Space freed: {free_gb:.2f}GB")
                # 녹화 자동 재개
                self._recording_should_auto_resume = True
                self._schedule_recording_retry()
            else:
                logger.error(f"[DISK] Still not enough space after cleanup: {free_gb:.2f}GB")
                # UI 알림
                self._notify_recording_state_change(False)

        except Exception as e:
            logger.error(f"[DISK] Cleanup failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _handle_decoder_error(self, err):
        """디코더 에러 처리 - 버퍼 플러시"""
        logger.warning(f"[DECODER] Decode error: {err}")

        # 버퍼 플러시
        self.pipeline.send_event(Gst.Event.new_flush_start())
        time.sleep(0.1)
        self.pipeline.send_event(Gst.Event.new_flush_stop(True))

        logger.info("[DECODER] Pipeline flushed")

    def _handle_videosink_error(self, err):
        """Video Sink 에러 처리 - 무시 또는 Streaming Branch 중지"""
        logger.warning(f"[VIDEOSINK] Display error: {err}")

        if not self.window_handle:
            # Headless 모드 - 무시
            logger.debug("[VIDEOSINK] Headless mode - error ignored")
            return

        # Streaming Branch만 중지
        self.streaming_valve.set_property("drop", True)
        self._is_streaming = False
        self._streaming_branch_error = True

        logger.info("[RECORDING] Recording continues")

    def _handle_unknown_error(self, src_name, err):
        """알 수 없는 에러 처리"""
        logger.warning(f"[UNKNOWN] Unhandled error from {src_name}: {err}")

        # RTSP 소스 관련 에러면 재연결 시도
        if src_name == "source":
            logger.info("[UNKNOWN] Source error detected, attempting reconnection")
            threading.Thread(target=self._async_stop_and_reconnect, daemon=True).start()
        else:
            # 다른 소스 에러는 로그만 남기고 무시
            logger.debug(f"[UNKNOWN] Non-critical error from {src_name}, ignoring")


    def _async_stop_and_reconnect(self):
        """비동기로 파이프라인 정지 및 재연결"""
        # 녹화 중이었는지 확인 (stop() 호출 전에 저장)
        was_recording = self._is_recording

        logger.debug(f"[RECONNECT] Async stop initiated - was_recording: {was_recording}")

        # ✅ 녹화 중이었으면 명시적으로 먼저 중지 (파이프라인 정지 전)
        if was_recording:
            logger.info("[RECONNECT] Stopping recording before pipeline stop")
            try:
                # 파이프라인이 아직 살아있을 때 녹화 중지
                self.stop_recording()
            except Exception as e:
                logger.warning(f"[RECONNECT] Failed to stop recording gracefully: {e}")
                # 실패해도 상태는 초기화
                self._is_recording = False
                self.recording_start_time = None

        # 파이프라인 정지
        self.stop()

        # 녹화 중이었으면 자동 재개 플래그 설정
        if was_recording:
            self._recording_should_auto_resume = True
            logger.info("[RECONNECT] Will auto-resume recording after reconnection")

        # 재연결 스케줄링
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프, 중복 방지)"""
        # 최대 재시도 횟수 초과 시 중단
        if self.retry_count >= self.max_retries:
            logger.error(f"[RECONNECT] Max retries ({self.max_retries}) reached for {self.camera_id}")

            # 사용자 알림: 연결 실패 상태 전달
            self._notify_connection_state_change(False)

            # UI에 ERROR 상태 표시를 위한 추가 알림
            # (상위 CameraStream 클래스에서 처리)
            logger.critical(f"[RECONNECT] Failed to reconnect to {self.camera_name} after {self.max_retries} attempts")

            return

        # 이전 타이머가 있으면 취소
        if self.reconnect_timer and self.reconnect_timer.is_alive():
            logger.debug("[RECONNECT] Cancelling previous reconnect timer")
            self.reconnect_timer.cancel()

        # 지수 백오프: 5초 → 10초 → 20초 → 40초 → 60초 (최대)
        delay = min(5 * (2 ** self.retry_count), 60)
        self.retry_count += 1

        logger.info(f"[RECONNECT] Reconnecting in {delay}s (attempt {self.retry_count}/{self.max_retries})")

        # 타이머 시작
        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

    def _test_rtsp_connection(self, timeout=3):
        """
        RTSP 연결 가능 여부를 빠르게 테스트
        TCP 소켓으로 네트워크 연결만 확인하여 부하 최소화

        Returns:
            bool: 연결 가능하면 True, 아니면 False
        """
        try:
            logger.debug(f"[CONNECTION TEST] Testing RTSP connection to {self.rtsp_url}")

            # RTSP URL에서 호스트와 포트 추출
            import re
            import socket

            # rtsp://username:password@host:port/path 형식 파싱
            pattern = r'rtsp://(?:([^:@]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?(/.*)?'
            match = re.match(pattern, self.rtsp_url)

            if not match:
                logger.warning("[CONNECTION TEST] Failed to parse RTSP URL")
                return False

            host = match.group(3)
            port = int(match.group(4)) if match.group(4) else 554

            logger.debug(f"[CONNECTION TEST] Checking TCP connection to {host}:{port}")

            # TCP 소켓 연결 테스트
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            try:
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.success(f"[CONNECTION TEST] ✓ TCP connection successful to {host}:{port}")
                    return True
                else:
                    logger.warning(f"[CONNECTION TEST] TCP connection failed to {host}:{port} (error: {result})")
                    return False

            except socket.timeout:
                logger.warning(f"[CONNECTION TEST] Connection timed out after {timeout}s")
                sock.close()
                return False
            except socket.error as e:
                logger.warning(f"[CONNECTION TEST] Socket error: {e}")
                sock.close()
                return False

        except Exception as e:
            logger.warning(f"[CONNECTION TEST] Exception during connection test: {e}")
            return False

    def _should_auto_start_recording(self) -> tuple[bool, str]:
        """
        재연결 후 녹화 자동 시작 여부 판단

        Returns:
            tuple[bool, str]: (녹화 시작 여부, 판단 근거 메시지)
        """
        # Case 1: 연결 끊김으로 인해 녹화가 중지된 경우 → 녹화 재개
        if self._recording_should_auto_resume:
            return True, "was recording before disconnect"

        # Case 2: 초기 연결 실패 후 첫 연결
        # _ever_connected=False이고 _recording_should_auto_resume=False인 경우
        # → recording_enabled_start 설정 확인
        if not self._ever_connected and not self._recording_should_auto_resume:
            try:
                config = ConfigManager.get_instance()
                cameras = config.config.get("cameras", [])
                camera_config = next((cam for cam in cameras if cam.get("camera_id") == self.camera_id), None)

                if camera_config:
                    recording_enabled_start = camera_config.get("recording_enabled_start", False)
                    if recording_enabled_start:
                        return True, "recording_enabled_start=True in config"
                    else:
                        return False, "recording_enabled_start=False in config"
            except Exception as e:
                logger.warning(f"Failed to check recording_enabled_start config: {e}")
                return False, f"config check failed: {e}"

        # Case 3: 재연결이지만 녹화 안하고 있었음 → 녹화 시작 안함
        return False, "was not recording before disconnect"

    def _auto_start_recording_after_reconnect(self):
        """
        재연결 후 녹화 자동 시작 처리
        녹화 시작 여부를 판단하고 필요 시 녹화 시작
        """
        should_start, reason = self._should_auto_start_recording()

        if should_start:
            logger.info(f"[RECONNECT] Will start recording: {reason}")

            # 짧은 대기 (파이프라인 안정화)
            time.sleep(1.0)

            # 녹화 시작 시도
            if self.start_recording():
                logger.success("[RECONNECT] Recording started successfully!")
                self._recording_should_auto_resume = False
            else:
                logger.warning("[RECONNECT] Failed to start recording, will retry via timer")
                # 실패 시 녹화 재시도 타이머 시작
                self._schedule_recording_retry()
        else:
            logger.debug(f"[RECONNECT] Not starting recording: {reason}")

    def _reconnect(self):
        """
        재연결 수행 (단순화된 버전)

        로직:
        1. 카메라 네트워크 상태만 반복 체크 (_test_rtsp_connection)
        2. 정상 확인되면 일반 연결 로직 재사용 (create_pipeline + start)
        3. 녹화 자동 시작 여부 판단 및 처리
        """
        # 이미 연결된 상태면 무시
        if self._is_playing:
            logger.debug(f"Pipeline already running for {self.camera_name}, skipping reconnect")
            self.retry_count = 0  # retry count 초기화
            return

        logger.info("[RECONNECT] Attempting to reconnect...")

        # ✅ Step 1: 카메라 네트워크 상태만 반복 체크
        if not self._test_rtsp_connection(timeout=3):
            logger.warning("[RECONNECT] Camera not responding - scheduling retry")
            # 재연결 타이머 재스케줄링
            self._schedule_reconnect()
            return

        logger.info("[RECONNECT] Camera network OK - proceeding with connection")

        # ✅ Step 2: 일반 연결 로직 재사용
        # 파이프라인 재생성 (stop()에서 None으로 초기화했으므로)
        if not self.create_pipeline():
            logger.error("[RECONNECT] Failed to create pipeline - scheduling retry")
            self._schedule_reconnect()
            return

        # 파이프라인 시작 (start() 메서드는 항상 동일한 로직 수행)
        if not self.start():
            logger.error("[RECONNECT] Failed to start pipeline - scheduling retry")
            self._schedule_reconnect()
            return

        # ✅ Step 3: 재연결 성공 - 녹화 자동 시작 처리
        logger.success("[RECONNECT] Pipeline reconnected successfully")
        self.retry_count = 0

        # 녹화 자동 시작 여부 판단 및 처리
        self._auto_start_recording_after_reconnect()

    

    def _schedule_recording_retry(self):
        """녹화 재시도 타이머 시작"""
        # 이미 타이머가 실행 중이면 무시
        if self._recording_retry_timer and self._recording_retry_timer.is_alive():
            logger.debug("[RECORDING RETRY] Timer already running")
            return

        # 재시도 카운터 초기화
        self._recording_retry_count = 0

        # 타이머 시작 (첫 재시도는 6초 후)
        self._recording_retry_timer = threading.Timer(
            self._recording_retry_interval,
            self._retry_recording
        )
        self._recording_retry_timer.daemon = True
        self._recording_retry_timer.start()

        logger.info(f"[RECORDING RETRY] Scheduled (interval: {self._recording_retry_interval}s, max attempts: {self._max_recording_retry})")    

    def _retry_recording(self):
        """녹화 재시도 실행"""
        # 자동 재개 플래그가 꺼져있으면 중단
        if not self._recording_should_auto_resume:
            logger.debug("[RECORDING RETRY] Auto-resume disabled, stopping retry")
            return

        # 최대 재시도 횟수 초과 시 중단
        self._recording_retry_count += 1
        if self._recording_retry_count > self._max_recording_retry:
            logger.warning(f"[RECORDING RETRY] Max retry count reached ({self._max_recording_retry})")
            self._recording_should_auto_resume = False
            return

        logger.debug(f"[RECORDING RETRY] Attempt {self._recording_retry_count}/{self._max_recording_retry}")

        # 저장소 경로 검증
        if self._validate_recording_path():
            logger.success(f"[RECORDING RETRY] Storage path available!")

            # 에러 플래그 초기화
            self._recording_branch_error = False

            # 녹화 시작 시도
            if self.start_recording():
                logger.success("[RECORDING RETRY] Recording resumed successfully!")
                self._recording_should_auto_resume = False  # 성공 시 플래그 초기화
                return
            else:
                logger.warning("[RECORDING RETRY] Failed to start recording (pipeline issue)")
        else:
            logger.debug(f"[RECORDING RETRY] Storage path still unavailable (retry {self._recording_retry_count}/{self._max_recording_retry})")

        # 다음 재시도 스케줄링
        self._recording_retry_timer = threading.Timer(
            self._recording_retry_interval,
            self._retry_recording
        )
        self._recording_retry_timer.daemon = True
        self._recording_retry_timer.start()

    def _cancel_recording_retry(self):
        """녹화 재시도 취소"""
        self._recording_should_auto_resume = False

        if self._recording_retry_timer and self._recording_retry_timer.is_alive():
            self._recording_retry_timer.cancel()
            self._recording_retry_timer = None
            logger.info("[RECORDING RETRY] Retry cancelled")    



    def start(self) -> bool:
        """
        파이프라인 시작

        주의:
        - 네트워크 연결 테스트는 이 메서드를 호출하기 전에 수행되어야 함
        - 초기 연결: CameraStream.connect() → GstPipeline.start() (연결 실패 시 _reconnect() 모드로 전환)
        - 재연결: _reconnect()에서 _test_rtsp_connection() 수행 후 이 메서드 호출
        """
        if not self.pipeline:
            logger.error("Pipeline not created")
            return False

        try:
            logger.debug(f"Starting pipeline for {self.camera_name}")

            # 파이프라인 상태를 단계적으로 변경
            ret = self.pipeline.set_state(Gst.State.READY)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to set pipeline to READY state")
                # 에러 메시지 확인
                bus_msg = self.bus.pop_filtered(Gst.MessageType.ERROR)
                if bus_msg:
                    err, debug = bus_msg.parse_error()
                    logger.error(f"Error detail: {err}, Debug: {debug}")
                return False

            # PAUSED 상태로 전환
            ret = self.pipeline.set_state(Gst.State.PAUSED)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to set pipeline to PAUSED state")
                bus_msg = self.bus.pop_filtered(Gst.MessageType.ERROR)
                if bus_msg:
                    err, debug = bus_msg.parse_error()
                    logger.error(f"Error detail: {err}, Debug: {debug}")
                return False

            # ⭐ 중요: splitmuxsink는 format-location 핸들러를 사용하므로
            #    여기서 location 속성을 설정하면 핸들러가 무시됨!
            # → 파일명은 start_recording() 메서드에서 format-location 핸들러를 통해 동적으로 생성됨
            logger.debug("[RECORDING DEBUG] Splitmuxsink will use format-location handler for file naming")

            # PLAYING 상태로 전환
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to set pipeline to PLAYING state")
                bus_msg = self.bus.pop_filtered(Gst.MessageType.ERROR)
                if bus_msg:
                    err, debug = bus_msg.parse_error()
                    logger.error(f"Error detail: {err}, Debug: {debug}")
                return False
            elif ret in [Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.NO_PREROLL]:
                # 라이브 소스는 즉시 성공하거나 비동기로 처리됨
                logger.debug("Pipeline started immediately (live source detected)")
            elif ret == Gst.StateChangeReturn.ASYNC:
                logger.debug("Pipeline state change is asynchronous, checking state...")
                # 라이브 소스는 빠르게 연결되므로 짧은 대기 시간 (3초)
                ret, current_state, pending_state = self.pipeline.get_state(3 * Gst.SECOND)

                # 라이브 소스 반환값 처리
                if ret == Gst.StateChangeReturn.NO_PREROLL:
                    logger.debug("Live source confirmed (NO_PREROLL)")

                elif ret == Gst.StateChangeReturn.SUCCESS:
                    logger.debug(f"Pipeline state successfully changed to: {current_state.value_nick}")

                elif ret == Gst.StateChangeReturn.ASYNC:
                    # 여전히 비동기 상태라면 라이브 소스일 가능성 높음
                    # RTSP 라이브 소스는 종종 계속 ASYNC 상태를 유지
                    if current_state in [Gst.State.PAUSED, Gst.State.PLAYING]:
                        logger.info(f"Live source pipeline running in {current_state.value_nick} state")
                    else:
                        logger.warning(f"Pipeline in unexpected state: {current_state.value_nick}")
                        # 그래도 계속 진행 (라이브 소스 특성)

                else:
                    # 타임아웃
                    logger.warning(f"Pipeline state change timed out (ret={ret})")
                    logger.debug(f"Current: {current_state.value_nick if current_state else 'None'}, Pending: {pending_state.value_nick if pending_state else 'None'}")
                    # 라이브 소스는 타임아웃 되어도 동작할 수 있음

            self._is_playing = True
            logger.debug(f"Pipeline successfully started for {self.camera_name}")

            # PLAYING 상태 전환 후 valve 상태 재적용 (상태 변경 시 리셋될 수 있음)
            logger.debug("[VALVE DEBUG] Re-applying valve settings after successful PLAYING state transition")
            self._apply_mode_settings()

            # 녹화는 start_recording() 메서드를 통해 명시적으로 시작해야 함
            # (자동 녹화는 _auto_start_recording()에서 콜백 등록 후 start_recording() 호출)
            logger.debug(f"[RECORDING DEBUG] Pipeline started in {self.mode.value} mode - recording valve will be controlled via start_recording()")

            # 메인 루프 시작
            self._main_loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._run_main_loop)
            self._thread.daemon = True
            self._thread.start()

            # OSD 타임스탬프 업데이트 시작
            if self.text_overlay:
                config = ConfigManager.get_instance()
                streaming_config = config.get_streaming_config()
                show_timestamp = streaming_config.get("show_timestamp", True)

                if show_timestamp:
                    self._start_timestamp_update()

            # 프레임 모니터링 시작 (연결 끊김 조기 감지)
            self._start_frame_monitor()

            logger.info(f"Pipeline started for {self.camera_name} (mode: {self.mode.value}, recording: {self._is_recording})")

            # 연결 상태 콜백 호출 (UI 동기화)
            self._notify_connection_state_change(True)

            # 연결 성공 플래그 설정 (초기 연결 실패 vs 재연결 구분용)
            self._ever_connected = True

            return True

        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")

            # 연결 실패 시 콜백 호출
            self._notify_connection_state_change(False)

            return False

    def stop(self):
        """파이프라인 정지 (중복 실행 방지)"""
        # 중복 실행 방지: 이미 정지 중이거나 정지된 상태면 무시
        if not self.pipeline or not self._is_playing:
            logger.debug(f"Pipeline already stopped or not running for {self.camera_name}")
            return

        try:
            logger.info(f"Stopping pipeline for {self.camera_name}")

            # _is_playing을 먼저 False로 설정하여 중복 stop() 호출 방지
            self._is_playing = False

            # 타임스탬프 업데이트 타이머 정지
            self._stop_timestamp_update()

            # 프레임 모니터링 중지
            self._stop_frame_monitor()

            # 녹화 재시도 타이머 취소
            self._cancel_recording_retry()

            # 재연결 타이머 취소
            if self.reconnect_timer:
                if self.reconnect_timer.is_alive():
                    self.reconnect_timer.cancel()
                    logger.debug(f"Reconnect timer cancelled for {self.camera_name}")
                self.reconnect_timer = None

            # 녹화 중이면 먼저 정지
            if self._is_recording:
                self.stop_recording()

            self.pipeline.set_state(Gst.State.NULL)

            if self._main_loop:
                self._main_loop.quit()

            # 현재 스레드가 pipeline 스레드가 아닌 경우에만 join
            if self._thread and self._thread.is_alive():
                current_thread = threading.current_thread()
                if current_thread != self._thread:
                    self._thread.join(timeout=2.0)
                else:
                    logger.debug("[STOP] Skipping thread join (called from pipeline thread)")

            # ✅ 파이프라인 객체 및 엘리먼트 참조 초기화 (재생성 시 충돌 방지)
            self.pipeline = None
            self.video_sink = None
            self.tee = None
            self.streaming_valve = None
            self.recording_valve = None
            self.splitmuxsink = None
            self.text_overlay = None
            self.bus = None
            logger.debug(f"[CLEANUP] Pipeline objects cleared for {self.camera_name}")

            logger.info(f"Pipeline stopped for {self.camera_name}")

            # 연결 끊김 상태 콜백 호출 (UI 동기화) - 한 번만 호출됨
            self._notify_connection_state_change(False)

        except Exception as e:
            logger.error(f"Error during pipeline stop: {e}")

    def start_recording(self) -> bool:
        """
        녹화 시작
        """
        # 파이프라인 실행 여부 확인
        if not self._is_playing:
            logger.error("Pipeline is not running")
            return False

        # ✅ 이미 녹화 중인지 확인 (재연결 시 상태 불일치 방지)
        if self._is_recording:
            logger.warning(f"Already recording: {self.camera_name} - forcing state reset")
            # 상태 불일치 해결: 강제로 초기화
            self._is_recording = False
            self.recording_start_time = None
            # 계속 진행하여 새로 녹화 시작

        try:
            # 1. 저장 경로 검증 (녹화 시작 전 필수!)
            if not self._validate_recording_path():
                logger.error("[STORAGE] Recording path validation failed")
                return False

            # 2. 녹화 디렉토리 생성 (날짜별)
            date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            # 3. 녹화 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # ⭐ 중요: splitmuxsink는 location 속성과 format-location 핸들러를 동시에 사용할 수 없음!
            # location 속성을 설정하면 format-location 핸들러가 무시됨
            # → 파일 분할을 위해서는 format-location 핸들러만 사용해야 함

            # 4. 기본 파일명 저장 (로그용 - 실제 파일명은 format-location에서 결정)
            self.current_recording_file = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")
            self._recording_fragment_id = 0  # 프래그먼트 ID 초기화

            logger.debug(f"[RECORDING DEBUG] Recording will start with base file: {self.current_recording_file}")

            # 5. valve 상태 확인
            if self.recording_valve:
                valve_drop = self.recording_valve.get_property("drop")
                if not valve_drop:
                    logger.error("[RECORDING DEBUG] Valve is already open!")
                    return False

            # 6. 상태 업데이트 (valve 열기 전에 설정)
            self._is_recording = True
            self.recording_start_time = time.time()

            logger.info(f"[RECORDING DEBUG] Recording state set, base file: {self.current_recording_file}")

            # 7. splitmuxsink 상태 확인 및 재시작 (EOS 상태에서 복구)
            # 단, 전체 파이프라인이 새로 생성된 경우(재연결 후)는 건너뛰기
            if self.splitmuxsink:
                current_state = self.splitmuxsink.get_state(0)[1]
                logger.debug(f"[RECORDING DEBUG] splitmuxsink current state: {current_state.value_nick}")

                # splitmuxsink를 READY로 전환 후 다시 PLAYING으로 전환 (EOS 상태 초기화)
                self.splitmuxsink.set_state(Gst.State.READY)
                time.sleep(0.1)

                # ⭐ 중요: READY 상태에서 설정이 초기화되므로 max-size-time 다시 설정
                self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
                logger.debug(f"[RECORDING DEBUG] Re-applied max-size-time: {self.file_duration_ns / Gst.SECOND}s")

                self.splitmuxsink.set_state(Gst.State.PLAYING)
                logger.debug("[RECORDING DEBUG] splitmuxsink restarted (READY -> PLAYING)")

            # 8. 짧은 대기 후 Valve 열기 (splitmuxsink 초기화 완료 대기)
            time.sleep(0.2)

            # 9. Valve 열기 (녹화 시작 - 데이터 흐름 시작)
            if self.recording_valve:
                self.recording_valve.set_property("drop", False)
                logger.debug("[RECORDING DEBUG] Recording valve opened")

            logger.success(f"Recording started: {self.current_recording_file}")
            logger.info(f"Files will be split every {self.file_duration_ns / Gst.SECOND}s, using format-location handler")

            # 녹화 시작 콜백 호출 (UI 동기화)
            self._notify_recording_state_change(True)

            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def stop_recording(self, storage_error: bool = False) -> bool:
        """
        녹화 정지 (splitmuxsink + valve 사용)

        Args:
            storage_error: 저장소 에러로 인한 중지인 경우 True (split-now 신호 건너뛰기)
        """
        if not self._is_recording:
            logger.warning(f"Not recording: {self.camera_name}")
            return False

        try:
            logger.info(f"Stopping recording for {self.camera_name}...")

            # 1. splitmuxsink 파일 finalize 처리
            if self.splitmuxsink and not storage_error:
                try:
                    # 방법: split-after 신호와 valve 조합 사용
                    # split-after는 다음 키프레임 후 파일을 분할하고 중지

                    # 현재 시간을 기준으로 split-after 설정 (0 = 즉시)
                    self.splitmuxsink.emit("split-after")
                    logger.debug("[RECORDING DEBUG] Emitted split-after signal to finalize current file")

                    # 파일 finalization을 위한 짧은 대기
                    time.sleep(0.3)

                except Exception as e:
                    logger.warning(f"[RECORDING DEBUG] Failed with split-after, trying split-now: {e}")
                    # split-after 실패 시 split-now 시도
                    try:
                        self.splitmuxsink.emit("split-now")
                        logger.debug("[RECORDING DEBUG] Emitted split-now signal as fallback")
                        time.sleep(0.5)
                    except Exception as e2:
                        logger.warning(f"[RECORDING DEBUG] Both split signals failed: {e2}")
            elif storage_error:
                logger.debug("[RECORDING DEBUG] Skipping finalization due to storage error")

                # storage_error인 경우 현재 파일 경로 기록 (USB 재연결 시 정리용)
                if self.current_recording_file:
                    self._last_corrupted_file = self.current_recording_file
                    logger.warning(f"[STORAGE] File may be corrupted: {self._last_corrupted_file}")

            # 2. Valve 닫기 (녹화 데이터 흐름 차단)
            if self.recording_valve:
                self.recording_valve.set_property("drop", True)
                logger.debug("[RECORDING DEBUG] Recording valve closed")

            # 녹화 상태 업데이트
            self._is_recording = False
            self.recording_start_time = None
            saved_file = self.current_recording_file
            self.current_recording_file = None  # 파일 경로 초기화

            logger.info(f"Recording stopped: {saved_file}")

            # 사용자가 수동으로 녹화를 중지한 경우 (storage_error=False)
            # 자동 재개 플래그 초기화 및 재시도 타이머 취소
            if not storage_error:
                self._cancel_recording_retry()

            # 녹화 정지 콜백 호출 (UI 동기화)
            self._notify_recording_state_change(False)

            return True

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            # 에러 발생 시에도 상태 업데이트
            self._is_recording = False
            self.recording_start_time = None
            self.current_recording_file = None
            return False

    def _on_format_location(self, splitmux, fragment_id):
        """
        splitmuxsink의 format-location 시그널 핸들러
        새 파일이 생성될 때마다 호출됨

        Args:
            splitmux: splitmuxsink 엘리먼트 (사용되지 않음)
            fragment_id: 현재 프래그먼트 인덱스

        Returns:
            str: 생성할 파일 경로 (형식: {camera_id}_{timestamp}.{format})
        """
        try:
            if not self._is_recording:
                # 녹화 중이 아니면 기본 경로 반환
                date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
                date_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                return str(date_dir / f"{self.camera_id}_temp_{timestamp}.{self.file_format}")

            # 매 fragment마다 새로운 timestamp로 파일 생성
            # 형식: cam_01_20251028_143000.mp4 (기존 형식과 동일)
            date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
            date_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")

            logger.info(f"[RECORDING DEBUG] Creating recording file: {file_path} (fragment #{fragment_id})")
            self._recording_fragment_id = fragment_id

            return file_path

        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.error(f"[STORAGE] USB disconnected during file rotation: {e}")

            # GLib 메인 루프에서 에러 핸들러 호출
            # 직접 _handle_storage_error()를 호출하면 안 됨 (GStreamer 콜백 스레드에서 호출되므로)
            from gi.repository import GLib
            GLib.idle_add(self._handle_storage_error_from_callback, str(e))

            # 임시 경로 반환 (크래시 방지)
            # splitmuxsink는 이 경로로 파일을 열려고 시도하고 실패하겠지만,
            # 최소한 예외로 인한 크래시는 방지됨
            return "/tmp/fallback_recording.mp4"

    def _handle_storage_error_from_callback(self, err_msg):
        """
        콜백에서 호출되는 storage 에러 핸들러
        GLib.idle_add를 통해 메인 루프에서 안전하게 호출됨

        Args:
            err_msg: 에러 메시지 문자열

        Returns:
            bool: False (GLib.idle_add는 False 반환 시 1회만 실행)
        """
        self._handle_storage_error(Exception(err_msg))
        return False  # 1회만 실행

    def _handle_storage_error_from_ui(self):
        """
        UI 위젯에서 호출되는 storage 에러 핸들러
        RecordingControlWidget._notify_storage_error()에서 호출됨

        UI 타이머 (5초 주기)가 스토리지 문제를 감지하면
        이 메서드를 통해 녹화를 미리 중지하고 재시도 모드로 전환
        """
        logger.warning(f"[STORAGE] Storage error detected by UI monitoring (camera: {self.camera_id})")

        # _handle_storage_error()와 동일한 로직 호출
        self._handle_storage_error(Exception("Storage unavailable (detected by UI)"))

    def get_storage_error_callback(self):
        """
        UI에 등록할 스토리지 에러 콜백 함수 반환

        Returns:
            callable: _handle_storage_error_from_ui 메서드
        """
        return self._handle_storage_error_from_ui

    def _validate_recording_path(self) -> bool:
        """
        녹화 시작 전 저장 경로 검증

        검증 항목:
        1. USB 마운트 상태 확인
        2. 상위 디렉토리 존재 여부
        3. 디렉토리 접근 권한
        4. 디스크 공간 확인
        5. 파일 생성 가능 여부 (테스트 파일 생성)

        Returns:
            bool: 경로가 유효하면 True, 아니면 False
        """
        try:
            # 1. USB 마운트 상태 확인
            # /media/itlog/NVR_MAIN 같은 경로에서 마운트 포인트 확인
            recording_path_str = str(self.recording_dir)

            # 마운트 포인트 경로 추출 (예: /media/itlog/NVR_MAIN)
            # recording_dir이 /media/itlog/NVR_MAIN/Recordings/cam_01 형태일 때
            # 상위 경로들을 확인하여 마운트 포인트 찾기
            if recording_path_str.startswith('/media/'):
                # /media/USER/DEVICE 형태의 마운트 포인트 추출
                path_parts = Path(recording_path_str).parts
                if len(path_parts) >= 4:  # ['/', 'media', 'user', 'device', ...]
                    mount_point = Path(*path_parts[:4])  # /media/user/device

                    # 마운트 포인트가 존재하는지 확인
                    if not mount_point.exists():
                        logger.error(f"[STORAGE] USB mount point does not exist: {mount_point}")
                        logger.error(f"[STORAGE] USB device may be disconnected or not mounted")
                        return False

                    # 마운트 포인트가 실제로 마운트되어 있는지 확인
                    if not os.path.ismount(str(mount_point)):
                        logger.error(f"[STORAGE] Path is not a mount point: {mount_point}")
                        logger.error(f"[STORAGE] USB device is not mounted")
                        return False

                    # 마운트 포인트 접근 권한 확인 (USB 재연결 시 권한 문제 방지)
                    try:
                        if not os.access(str(mount_point), os.R_OK | os.X_OK):
                            logger.error(f"[STORAGE] No read permission for mount point: {mount_point}")
                            logger.error(f"[STORAGE] USB may have permission issues after reconnection")
                            return False
                    except PermissionError as e:
                        logger.error(f"[STORAGE] Permission denied accessing mount point: {e}")
                        logger.error(f"[STORAGE] USB may have permission issues after reconnection")
                        return False

                    logger.debug(f"[STORAGE] USB mount point verified: {mount_point}")

            # 2. 상위 디렉토리 존재 여부 확인
            if not self.recording_dir.exists():
                logger.warning(f"[STORAGE] Recording directory does not exist: {self.recording_dir}")
                # 생성 시도
                try:
                    self.recording_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"[STORAGE] Created recording directory: {self.recording_dir}")
                except PermissionError as e:
                    logger.error(f"[STORAGE] Permission denied creating directory: {e}")
                    logger.error(f"[STORAGE] USB device may be read-only or disconnected")
                    return False
                except FileNotFoundError as e:
                    logger.error(f"[STORAGE] Parent directory not found: {e}")
                    logger.error(f"[STORAGE] USB device may be disconnected")
                    return False
                except OSError as e:
                    logger.error(f"[STORAGE] I/O error creating directory: {e}")
                    logger.error(f"[STORAGE] USB device may have I/O errors or be disconnected")
                    return False
                except Exception as e:
                    logger.error(f"[STORAGE] Failed to create directory: {e}")
                    return False

            # 3. 디렉토리 접근 권한 확인 (읽기, 쓰기, 실행)
            if not os.access(str(self.recording_dir), os.R_OK | os.W_OK | os.X_OK):
                logger.error(f"[STORAGE] No read/write permission for: {self.recording_dir}")
                logger.error(f"[STORAGE] USB device may be read-only or disconnected")
                return False

            # 4. 디스크 공간 확인 (최소 1GB 필요)
            try:
                import shutil
                stat = shutil.disk_usage(str(self.recording_dir))
                free_gb = stat.free / (1024**3)

                if free_gb < 1.0:
                    logger.error(f"[STORAGE] Insufficient disk space: {free_gb:.2f}GB (minimum 1GB required)")
                    return False

                logger.debug(f"[STORAGE] Disk space available: {free_gb:.2f}GB")
            except OSError as e:
                logger.error(f"[STORAGE] Failed to check disk space: {e}")
                logger.error(f"[STORAGE] USB device may be disconnected")
                return False

            # 5. 파일 생성 테스트 (임시 파일 생성 후 삭제)
            test_file = self.recording_dir / f".test_{self.camera_id}.tmp"
            try:
                test_file.touch()
                test_file.unlink()
                logger.debug(f"[STORAGE] Write test successful: {self.recording_dir}")
            except OSError as e:
                logger.error(f"[STORAGE] Failed to write test file (I/O error): {e}")
                logger.error(f"[STORAGE] USB device may be disconnected or have I/O errors")
                return False
            except Exception as e:
                logger.error(f"[STORAGE] Failed to write test file: {e}")
                return False

            logger.info(f"[STORAGE] Recording path validated: {self.recording_dir}")
            return True

        except Exception as e:
            logger.error(f"[STORAGE] Path validation failed: {e}")
            logger.error(f"[STORAGE] This may indicate USB disconnection or system error")
            return False

    def _get_camera_config(self) -> Optional[Dict]:
        """
        현재 카메라의 설정 가져오기

        Returns:
            dict or None: 카메라 설정 딕셔너리
        """
        try:
            config = ConfigManager.get_instance()
            cameras = config.config.get("cameras", [])

            for cam in cameras:
                if cam.get("camera_id") == self.camera_id:
                    return cam

            logger.warning(f"Camera config not found for {self.camera_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get camera config: {e}")
            return None

    def _get_videoflip_method(self, flip_mode: str, rotation: int) -> Optional[int]:
        """
        flip과 rotation 설정을 videoflip method로 변환

        Args:
            flip_mode: "none", "horizontal", "vertical", "both"
            rotation: 0, 90, 180, 270

        Returns:
            int or None: videoflip method 값
                0 = none (identity)
                1 = clockwise (90도)
                2 = rotate-180
                3 = counterclockwise (270도)
                4 = horizontal-flip
                5 = vertical-flip
                6 = upper-left-diagonal
                7 = upper-right-diagonal
        """
        # 회전이 우선 (90, 270도는 flip과 조합 불가)
        if rotation == 90:
            return 1  # clockwise
        elif rotation == 270:
            return 3  # counterclockwise
        elif rotation == 180:
            if flip_mode == "horizontal":
                return 5  # vertical-flip (180도 + 좌우반전 = 상하반전)
            elif flip_mode == "vertical":
                return 4  # horizontal-flip (180도 + 상하반전 = 좌우반전)
            else:
                return 2  # rotate-180

        # 회전 없음 - flip만 적용
        if flip_mode == "horizontal":
            return 4  # horizontal-flip
        elif flip_mode == "vertical":
            return 5  # vertical-flip
        elif flip_mode == "both":
            return 2  # rotate-180 (좌우+상하 = 180도 회전)

        return None  # none (변환 없음)

    def _delayed_valve_open(self):
        """지연된 valve 열기 (키프레임 대기 후) - 이제 사용되지 않음"""
        # 이 메서드는 더 이상 사용되지 않지만 호환성을 위해 유지
        logger.debug("[KEYFRAME] _delayed_valve_open called but no longer used")





    def _run_main_loop(self):
        """메인 루프 실행"""
        try:
            self._main_loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")

    def set_window_handle(self, window_handle):
        """윈도우 핸들 설정"""
        self.window_handle = window_handle
        if self.video_sink and self._is_playing:
            try:
                GstVideo.VideoOverlay.set_window_handle(self.video_sink, window_handle)
                logger.debug(f"Window handle updated: {window_handle}")
            except Exception as e:
                logger.error(f"Failed to update window handle: {e}")

    def _verify_pipeline_elements(self) -> bool:
        """파이프라인 엘리먼트 검증"""
        try:
            # 기본 필수 엘리먼트 (모든 모드 공통)
            basic_elements = [
                ("source", "rtspsrc"),
                ("depay", "rtph264depay"),
                ("parse", "h264parse"),
                ("tee", "tee")
            ]

            for name, description in basic_elements:
                element = self.pipeline.get_by_name(name)
                if not element:
                    logger.error(f"Basic element '{name}' ({description}) not found in pipeline")
                    return False
                logger.debug(f"Verified element: {name} ({element.get_factory().get_name()})")

            # 스트리밍 브랜치 엘리먼트 (항상 존재)
            streaming_elements = [
                ("stream_queue", "streaming queue"),
                ("streaming_valve", "streaming valve"),
                ("decoder", "decoder"),
                ("convert", "videoconvert"),
                ("scale", "videoscale")
            ]
            for name, description in streaming_elements:
                element = self.pipeline.get_by_name(name)
                if not element:
                    logger.error(f"Streaming element '{name}' ({description}) not found")
                    return False
                logger.debug(f"Verified element: {name} ({element.get_factory().get_name()})")

            # videosink 체크 (이름이 다를 수 있음)
            if not self.video_sink:
                logger.error("Video sink not found")
                return False

            # 녹화 브랜치 엘리먼트 (항상 존재)
            recording_elements = [
                ("record_queue", "recording queue"),
                ("recording_valve", "recording valve"),
                ("record_parse", "recording h264parse"),
                ("splitmuxsink", "splitmuxsink")
            ]
            for name, description in recording_elements:
                element = self.pipeline.get_by_name(name)
                if not element:
                    logger.error(f"Recording element '{name}' ({description}) not found")
                    return False
                logger.debug(f"Verified element: {name} ({element.get_factory().get_name()})")

            logger.debug("Pipeline element verification successful - all branches present with splitmuxsink")
            return True

        except Exception as e:
            logger.error(f"Error during pipeline verification: {e}")
            return False

    def _apply_mode_settings(self):
        """현재 모드에 따라 Valve 설정 적용"""

        # 모든 모드에서 두 브랜치 모두 존재하므로 valve 체크만 수행
        if not self.streaming_valve or not self.recording_valve:
            logger.error("Valves not initialized - cannot apply mode settings")
            return

        # 현재 valve 상태 확인
        current_stream_drop = self.streaming_valve.get_property("drop")
        current_record_drop = self.recording_valve.get_property("drop")
        logger.info(f"[VALVE DEBUG] Current valve states before mode change - Streaming: drop={current_stream_drop}, Recording: drop={current_record_drop}")
        logger.info(f"[VALVE DEBUG] Applying mode settings for: {self.mode.value}")

        if self.mode == PipelineMode.STREAMING_ONLY:
            # 스트리밍만: streaming valve 열림, recording valve 닫힘
            self.streaming_valve.set_property("drop", False)
            self.recording_valve.set_property("drop", True)
            logger.info(f"[VALVE DEBUG] Mode: STREAMING_ONLY - Setting Streaming valve drop=False (open), Recording valve drop=True (closed)")

        elif self.mode == PipelineMode.RECORDING_ONLY:
            # 녹화만 모드: streaming valve 닫힘, recording valve도 닫힘 (수동 시작 필요)
            self.streaming_valve.set_property("drop", True)
            self.recording_valve.set_property("drop", True)
            logger.info(f"[VALVE DEBUG] Mode: RECORDING_ONLY - Both valves closed, recording must be started via start_recording()")

        elif self.mode == PipelineMode.BOTH:
            # 스트리밍 + 녹화 준비 모드: streaming valve 열림, recording valve는 닫힘 (수동 시작 필요)
            self.streaming_valve.set_property("drop", False)
            self.recording_valve.set_property("drop", True)
            logger.info(f"[VALVE DEBUG] Mode: BOTH - Streaming valve open, Recording valve closed (recording must be started via start_recording())")

        # 실제 설정값 확인
        actual_stream_drop = self.streaming_valve.get_property("drop")
        actual_record_drop = self.recording_valve.get_property("drop")
        logger.info(f"[VALVE DEBUG] Valve states after mode change - Streaming: drop={actual_stream_drop}, Recording: drop={actual_record_drop}")

        # 변경 사항 확인 (올바른 검증 로직)
        # Streaming valve: RECORDING_ONLY 모드에서만 닫힘(drop=True)
        expected_stream_drop = (self.mode == PipelineMode.RECORDING_ONLY)
        # Recording valve: 모든 모드에서 초기에는 닫혀있음(drop=True), start_recording()으로 수동 시작 필요
        expected_record_drop = True

        if actual_stream_drop != expected_stream_drop:
            logger.warning(f"[VALVE DEBUG] Streaming valve state mismatch! Expected drop={expected_stream_drop}, Actual={actual_stream_drop}")
        if actual_record_drop != expected_record_drop:
            logger.warning(f"[VALVE DEBUG] Recording valve state mismatch! Expected drop={expected_record_drop}, Actual={actual_record_drop}")

    def set_mode(self, mode: PipelineMode):
        """파이프라인 모드 변경 (런타임 중 변경 가능)"""
        old_mode = self.mode
        self.mode = mode

        # 파이프라인이 실행 중이면 즉시 적용
        if self._is_playing:
            self._apply_mode_settings()
            logger.info(f"Pipeline mode changed from {old_mode.value} to {mode.value} (runtime)")
        else:
            logger.info(f"Pipeline mode changed to {mode.value} (will apply on start)")

        return True

    def get_status(self) -> Dict:
        """파이프라인 상태 정보 반환"""
        status = {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "mode": self.mode.value,
            "is_playing": self._is_playing,
            "is_recording": self._is_recording
        }

        if self._is_recording:
            status["current_file"] = self.current_recording_file
            if self.recording_start_time:
                status["recording_duration"] = int(time.time() - self.recording_start_time)

        return status

    def _start_timestamp_update(self):
        """타임스탬프 업데이트 타이머 시작"""
        def update_timestamp():
            if self._is_playing and self.text_overlay:
                config = ConfigManager.get_instance()
                streaming_config = config.get_streaming_config()

                show_camera_name = streaming_config.get("show_camera_name", True)
                show_timestamp = streaming_config.get("show_timestamp", True)

                text_parts = []
                if show_camera_name:
                    text_parts.append(self.camera_name)
                if show_timestamp:
                    text_parts.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                new_text = " | ".join(text_parts)
                self.text_overlay.set_property("text", new_text)

                # 다음 업데이트 스케줄 (1초마다)
                if self._is_playing:
                    self._timestamp_update_timer = threading.Timer(1.0, update_timestamp)
                    self._timestamp_update_timer.daemon = True
                    self._timestamp_update_timer.start()

        # 첫 업데이트 시작
        self._timestamp_update_timer = threading.Timer(1.0, update_timestamp)
        self._timestamp_update_timer.daemon = True
        self._timestamp_update_timer.start()
        logger.debug("OSD timestamp update started")

    def _stop_timestamp_update(self):
        """타임스탬프 업데이트 타이머 정지"""
        if self._timestamp_update_timer:
            self._timestamp_update_timer.cancel()
            self._timestamp_update_timer = None
            logger.debug("OSD timestamp update stopped")