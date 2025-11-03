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
from camera.gst_utils import get_video_sink, get_available_h264_decoder, get_available_decoder, create_video_sink_with_properties

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

        # 녹화 디렉토리 설정
        base_path = recording_config.get('base_path', './recordings')
        self.recording_dir = Path(base_path) / camera_id

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


        logger.debug(f"Recording config loaded: base_path={base_path}, rotation={rotation_minutes}min, format={self.file_format}, codec={self.video_codec}")

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

            # connection_timeout 설정 (기본값: 10초)
            # rtspsrc의 timeout 속성은 초 단위
            connection_timeout = streaming_config.get("connection_timeout", 10)
            rtspsrc.set_property("timeout", connection_timeout * 1000000)  # microseconds
            logger.debug(f"Connection timeout set to {connection_timeout}s")

            rtspsrc.set_property("retry", 5)

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
            self.pipeline.add(rtspsrc)
            self.pipeline.add(depay)
            self.pipeline.add(parse)
            self.pipeline.add(self.tee)

            # 기본 체인 연결 (소스는 나중에 pad-added 시그널로 연결)
            depay.link(parse)
            parse.link(self.tee)

            # RTSP 소스의 동적 패드 연결
            rtspsrc.connect("pad-added", self._on_pad_added, depay)

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

            if not self.streaming_valve.link(decoder):
                raise Exception("Failed to link streaming_valve → decoder")
            logger.debug("[STREAMING DEBUG] Linked: streaming_valve → decoder")

            if not decoder.link(convert):
                raise Exception("Failed to link decoder → convert")
            logger.debug("[STREAMING DEBUG] Linked: decoder → convert")

            # OSD가 활성화된 경우 convert → textoverlay → scale
            # OSD가 비활성화된 경우 convert → scale
            if self.text_overlay:
                if not convert.link(self.text_overlay):
                    raise Exception("Failed to link convert → text_overlay")
                logger.debug("[STREAMING DEBUG] Linked: convert → text_overlay")

                if not self.text_overlay.link(scale):
                    raise Exception("Failed to link text_overlay → scale")
                logger.debug("[STREAMING DEBUG] Linked: text_overlay → scale")
            else:
                if not convert.link(scale):
                    raise Exception("Failed to link convert → scale")
                logger.debug("[STREAMING DEBUG] Linked: convert → scale")

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
            tee_pad = self.tee.request_pad_simple("src_%u")
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
                # mp4mux 속성 설정을 위한 문자열
                self.splitmuxsink.set_property("muxer-properties", "fragment-duration=1000,streamable=true")

            # splitmuxsink 설정
            self.splitmuxsink.set_property("async-handling", True)  # 비동기 처리
            self.splitmuxsink.set_property("send-keyframe-requests", True)  # 키프레임 요청

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
            tee_pad = self.tee.request_pad_simple("src_%u")
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
        """RTSP 소스의 동적 패드 연결"""
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
                self._handle_rtsp_error(err)
            # - 저장소 분리
            elif error_type == ErrorType.STORAGE_DISCONNECTED:
                self._handle_storage_error(err)
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
                logger.debug(f"Pipeline state: {old_state.value_nick} -> {new_state.value_nick}")
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            src_name = message.src.get_name() if message.src else "unknown"
            logger.warning(f"Pipeline warning from {src_name}: {warn}")
            if src_name in ["splitmuxsink", "record_parse", "recording_valve"]:
                logger.warning(f"[RECORDING DEBUG] Recording branch warning: {warn}")

    def _classify_error(self, src_name, err, debug, error_code):
        """에러 타입 분류"""
        error_str = str(err).lower()
        debug_str = str(debug).lower() if debug else ""

        # RTSP 네트워크 에러 (확장)
        if src_name == "source":
            # error_code 9: Could not read
            # error_code 10: Could not write (파이프라인 정지 중)
            # error_code 7: Could not open (재연결 타임아웃)
            # error_code 1: Internal data stream error
            if error_code in [1, 7, 9, 10]:
                return ErrorType.RTSP_NETWORK

        # 저장소 분리
        if (src_name in ["splitmuxsink", "sink"] and
            error_code == 10 and
            "could not write" in error_str and
            ("permission denied" in debug_str or
             "file descriptor" in debug_str)):
            return ErrorType.STORAGE_DISCONNECTED

        # 디스크 Full
        if ("space" in error_str or
            "no space" in error_str):
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

    def _async_stop_and_reconnect(self):
        """비동기로 파이프라인 정지 및 재연결"""
        self.stop()
        self._schedule_reconnect()

    def _handle_storage_error(self, err):
        """저장소 에러 처리 - Recording Branch만 중지"""
        logger.critical(f"[STORAGE] USB disconnected: {err}")

        # 1. 녹화 중지 (storage_error 플래그로 split-now 신호 건너뛰기)
        self.stop_recording(storage_error=True)

        # 2. 에러 플래그 설정
        self._recording_branch_error = True
        self._last_error_time["recording"] = time.time()

        logger.info("[STREAMING] Streaming continues")

    def _handle_disk_full_error(self, err):
        """디스크 Full 처리 - 자동 정리"""
        logger.critical(f"[DISK] Disk full: {err}")
        self._handle_disk_full()

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



    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프, 중복 방지)"""
        # 이미 재연결 타이머가 실행 중이면 무시
        if self.reconnect_timer and self.reconnect_timer.is_alive():
            logger.debug("Reconnect already scheduled, skipping duplicate")
            return

        if self.retry_count >= self.max_retries:
            logger.error(f"Max retries ({self.max_retries}) reached")
            return

        # 지수 백오프
        delay = min(5 * (2 ** self.retry_count), 60)
        self.retry_count += 1

        logger.info(f"Reconnecting in {delay}s (attempt {self.retry_count}/{self.max_retries})")

        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

    def _reconnect(self):
        """재연결 수행 (중복 실행 방지)"""
        # 이미 연결된 상태면 무시
        if self._is_playing:
            logger.debug(f"Pipeline already running for {self.camera_name}, skipping reconnect")
            self.retry_count = 0  # retry count 초기화
            return

        logger.info("Attempting to reconnect...")

        success = self.start()

        if success:
            logger.success("Reconnected successfully")
            self.retry_count = 0
        else:
            logger.error("Reconnect failed")
            self._schedule_reconnect()



    def start(self) -> bool:
        """파이프라인 시작"""
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

            # 녹화 파일명 설정 (READY 상태에서 안전하게 설정)
            # splitmuxsink는 location 패턴을 사용하여 자동으로 파일을 생성
            if self.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                # recording_valve의 drop 속성 확인
                valve_drop = self.recording_valve.get_property("drop")
                logger.debug(f"[RECORDING DEBUG] Mode: {self.mode.value}, recording_valve drop: {valve_drop}")

                if not valve_drop:  # drop=False면 녹화 예정
                    # 녹화 파일명 패턴 생성 (아직 설정되지 않은 경우)
                    if not self.current_recording_file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
                        date_dir.mkdir(exist_ok=True)
                        # splitmuxsink용 파일명 패턴 (%05d는 파일 인덱스)
                        location_pattern = str(date_dir / f"{self.camera_id}_{timestamp}_%05d.{self.file_format}")

                        # splitmuxsink location 설정
                        if self.splitmuxsink:
                            self.splitmuxsink.set_property("location", location_pattern)

                        self.current_recording_file = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")
                        logger.info(f"[RECORDING DEBUG] Initial recording pattern set: {location_pattern}")
                else:
                    logger.debug(f"[RECORDING DEBUG] Recording valve is closed (drop=True), skipping file setup")

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

            logger.info(f"Pipeline started for {self.camera_name} (mode: {self.mode.value}, recording: {self._is_recording})")

            # 연결 상태 콜백 호출 (UI 동기화)
            self._notify_connection_state_change(True)

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

            # 녹화 중이면 먼저 정지
            if self._is_recording:
                self.stop_recording()

            self.pipeline.set_state(Gst.State.NULL)

            if self._main_loop:
                self._main_loop.quit()

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            logger.info(f"Pipeline stopped for {self.camera_name}")

            # 연결 끊김 상태 콜백 호출 (UI 동기화) - 한 번만 호출됨
            self._notify_connection_state_change(False)

        except Exception as e:
            logger.error(f"Error during pipeline stop: {e}")

    def start_recording(self) -> bool:
        """녹화 시작"""
        # 파이프라인 실행 여부 확인
        if not self._is_playing:
            logger.error("Pipeline is not running")
            return False

        # 이미 녹화 중인지 확인
        if self._is_recording:
            logger.warning(f"Already recording: {self.camera_name}")
            return False

        try:
            # 1. 저장 경로 검증 (녹화 시작 전 필수!)
            if not self._validate_recording_path():
                logger.error("[STORAGE] Recording path validation failed")
                return False

            # 2. 녹화 디렉토리 생성 (날짜별)
            date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            # 녹화 파일명 생성 (format-location 핸들러에서 사용)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_recording_file = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")
            self._recording_fragment_id = 0  # 프래그먼트 ID 초기화

            # valve 상태 확인
            if self.recording_valve:
                valve_drop = self.recording_valve.get_property("drop")
                if not valve_drop:
                    logger.error("[RECORDING DEBUG] Valve is already open!")
                    return False

            # 상태 업데이트 (valve 열기 전에 설정)
            self._is_recording = True
            self.recording_start_time = time.time()

            logger.info(f"[RECORDING DEBUG] Recording state set, base file: {self.current_recording_file}")

            # 짧은 대기 후 Valve 열기 (location 설정이 완료되도록)
            time.sleep(0.1)

            # Valve 열기 (녹화 시작)
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

            # Valve 닫기 (녹화 중지)
            if self.recording_valve:
                self.recording_valve.set_property("drop", True)
                logger.debug("[RECORDING DEBUG] Recording valve closed")

            # splitmuxsink에 EOS 이벤트 전송 (현재 파일을 깔끔하게 종료)
            # 단, 저장소 에러인 경우 split-now 신호를 보내지 않음 (seek 에러 방지)
            if self.splitmuxsink and not storage_error:
                # splitmuxsink의 split-now 신호를 발생시켜 현재 파일을 마무리하고 새 파일 시작
                try:
                    self.splitmuxsink.emit("split-now")
                    logger.debug("[RECORDING DEBUG] Emitted split-now signal to splitmuxsink")
                except:
                    # split-now가 실패하면 sink pad에 EOS 전송
                    pad = self.splitmuxsink.get_static_pad("video")
                    if not pad:
                        # video pad가 없으면 sink pad 시도
                        pad = self.splitmuxsink.get_static_pad("sink")

                    if pad:
                        pad.send_event(Gst.Event.new_eos())
                        logger.debug("[RECORDING DEBUG] Sent EOS event to splitmuxsink pad")
            elif storage_error:
                logger.debug("[RECORDING DEBUG] Skipping split-now due to storage error")

            # 짧은 대기 시간 (EOS 처리 및 파일 완료 대기)
            time.sleep(0.5)  # 0.2초에서 0.5초로 증가

            # 녹화 상태 업데이트
            self._is_recording = False
            self.recording_start_time = None
            saved_file = self.current_recording_file
            self.current_recording_file = None  # 파일 경로 초기화

            logger.info(f"Recording stopped: {saved_file}")

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

    def _validate_recording_path(self) -> bool:
        """
        녹화 시작 전 저장 경로 검증

        검증 항목:
        1. 상위 디렉토리 존재 여부
        2. 디렉토리 접근 권한
        3. 디스크 공간 확인
        4. 파일 생성 가능 여부 (테스트 파일 생성)

        Returns:
            bool: 경로가 유효하면 True, 아니면 False
        """
        try:
            # 1. 상위 디렉토리 존재 여부 확인
            if not self.recording_dir.exists():
                logger.warning(f"[STORAGE] Recording directory does not exist: {self.recording_dir}")
                # 생성 시도
                try:
                    self.recording_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"[STORAGE] Created recording directory: {self.recording_dir}")
                except Exception as e:
                    logger.error(f"[STORAGE] Failed to create directory: {e}")
                    return False

            # 2. 디렉토리 접근 권한 확인 (읽기, 쓰기, 실행)
            if not os.access(str(self.recording_dir), os.R_OK | os.W_OK | os.X_OK):
                logger.error(f"[STORAGE] No read/write permission for: {self.recording_dir}")
                return False

            # 3. 디스크 공간 확인 (최소 1GB 필요)
            import shutil
            stat = shutil.disk_usage(str(self.recording_dir))
            free_gb = stat.free / (1024**3)

            if free_gb < 1.0:
                logger.error(f"[STORAGE] Insufficient disk space: {free_gb:.2f}GB (minimum 1GB required)")
                return False

            logger.debug(f"[STORAGE] Disk space available: {free_gb:.2f}GB")

            # 4. 파일 생성 테스트 (임시 파일 생성 후 삭제)
            test_file = self.recording_dir / f".test_{self.camera_id}.tmp"
            try:
                test_file.touch()
                test_file.unlink()
                logger.debug(f"[STORAGE] Write test successful: {self.recording_dir}")
            except Exception as e:
                logger.error(f"[STORAGE] Failed to write test file: {e}")
                return False

            logger.info(f"[STORAGE] Recording path validated: {self.recording_dir}")
            return True

        except Exception as e:
            logger.error(f"[STORAGE] Path validation failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

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

        # 변경 사항 확인
        if actual_stream_drop != (self.mode == PipelineMode.RECORDING_ONLY):
            logger.warning(f"[VALVE DEBUG] Streaming valve state mismatch! Expected drop={self.mode == PipelineMode.RECORDING_ONLY}, Actual={actual_stream_drop}")
        if actual_record_drop != (self.mode == PipelineMode.STREAMING_ONLY):
            logger.warning(f"[VALVE DEBUG] Recording valve state mismatch! Expected drop={self.mode == PipelineMode.STREAMING_ONLY}, Actual={actual_record_drop}")

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