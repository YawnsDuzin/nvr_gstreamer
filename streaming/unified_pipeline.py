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
from enum import Enum
from loguru import logger
from utils.gstreamer_utils import get_video_sink, get_available_h264_decoder, create_video_sink_with_properties
from config.config_manager import ConfigManager

# GStreamer 초기화
Gst.init(None)


class PipelineMode(Enum):
    """파이프라인 동작 모드"""
    STREAMING_ONLY = "streaming"
    RECORDING_ONLY = "recording"
    BOTH = "both"


class UnifiedPipeline:
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

        self._is_playing = False
        self._is_recording = False
        self._main_loop = None
        self._thread = None

        # 녹화 설정
        self.recording_dir = Path("recordings") / camera_id
        self.current_recording_file = None
        self.recording_start_time = None
        self.file_duration = 600  # 10분 단위 파일 분할


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

            rtspsrc.set_property("retry", 5)

            # 디페이로드 및 파서
            depay = Gst.ElementFactory.make("rtph264depay", "depay")
            parse = Gst.ElementFactory.make("h264parse", "parse")

            # Tee 엘리먼트 - 스트림 분기점
            self.tee = Gst.ElementFactory.make("tee", "tee")
            self.tee.set_property("allow-not-linked", True)

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

            # 모든 브랜치를 항상 생성 (Valve로 제어)
            self._create_streaming_branch()
            self._create_recording_branch()

            # 초기 모드 설정 적용
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

            # 스트리밍 큐
            stream_queue = Gst.ElementFactory.make("queue", "stream_queue")
            stream_queue.set_property("max-size-buffers", 100)
            stream_queue.set_property("max-size-time", 0)

            # buffer_size 설정 (기본값: 10MB = 10485760 bytes)
            buffer_size = streaming_config.get("buffer_size", 10485760)
            stream_queue.set_property("max-size-bytes", buffer_size)
            logger.debug(f"Stream queue buffer size set to {buffer_size} bytes ({buffer_size / 1024 / 1024:.1f}MB)")

            # Valve 엘리먼트 - 스트리밍 on/off 제어
            self.streaming_valve = Gst.ElementFactory.make("valve", "streaming_valve")
            self.streaming_valve.set_property("drop", False)  # 초기값은 나중에 설정

            # 디코더 - 설정에 따라 선택
            # use_hardware_acceleration 설정 확인
            use_hw_accel = streaming_config.get("use_hardware_acceleration", True)
            decoder_preference = streaming_config.get("decoder_preference", None)

            if use_hw_accel:
                # 하드웨어 가속 사용: 설정된 우선순위 또는 자동 선택
                decoder_name = get_available_h264_decoder(
                    prefer_hardware=True,
                    decoder_preference=decoder_preference
                )
                logger.info(f"Hardware acceleration enabled - selected decoder: {decoder_name}")
            else:
                # 소프트웨어 디코더 강제 사용
                decoder_name = get_available_h264_decoder(
                    prefer_hardware=False,
                    decoder_preference=None
                )
                logger.info(f"Hardware acceleration disabled - using software decoder: {decoder_name}")

            # h264parse는 디코더가 아니므로 avdec_h264를 사용
            if decoder_name == "h264parse":
                logger.warning("No hardware decoder available, using software decoder avdec_h264")
                decoder_name = "avdec_h264"

            decoder = Gst.ElementFactory.make(decoder_name, "decoder")

            if not decoder:
                logger.error(f"Failed to create decoder '{decoder_name}', falling back to avdec_h264")
                decoder = Gst.ElementFactory.make("avdec_h264", "decoder")

            if not decoder:
                raise Exception(f"Failed to create any H.264 decoder (tried: {decoder_name}, avdec_h264)")

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

                # 위치 및 스타일 설정
                self.text_overlay.set_property("valignment", "top")  # 상단 정렬
                self.text_overlay.set_property("halignment", "left")  # 좌측 정렬
                self.text_overlay.set_property("xpad", 10)  # 좌측 패딩
                self.text_overlay.set_property("ypad", 10)  # 상단 패딩

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

            # 최종 큐
            final_queue = Gst.ElementFactory.make("queue", "final_queue")
            final_queue.set_property("max-size-buffers", 3)
            final_queue.set_property("leaky", 2)  # downstream leaky

            # 비디오 싱크 (플랫폼별 자동 선택 - 공통 유틸리티 사용)
            video_sink_name = get_video_sink()
            self.video_sink = create_video_sink_with_properties(
                video_sink_name,
                sync=False,
                force_aspect_ratio=True
            )

            if not self.video_sink:
                logger.error(f"Failed to create video sink: {video_sink_name}")
                # 폴백으로 기본 비디오 싱크 생성
                self.video_sink = Gst.ElementFactory.make("fakesink", "videosink")

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
            stream_queue.link(self.streaming_valve)
            self.streaming_valve.link(decoder)
            decoder.link(convert)

            # OSD가 활성화된 경우 convert → textoverlay → scale
            # OSD가 비활성화된 경우 convert → scale
            if self.text_overlay:
                convert.link(self.text_overlay)
                self.text_overlay.link(scale)
            else:
                convert.link(scale)

            scale.link(caps_filter)
            caps_filter.link(final_queue)
            final_queue.link(self.video_sink)

            # Tee에서 스트리밍 큐로 연결
            tee_pad = self.tee.request_pad_simple("src_%u")
            queue_pad = stream_queue.get_static_pad("sink")
            tee_pad.link(queue_pad)

            logger.debug("Streaming branch created")

        except Exception as e:
            logger.error(f"Failed to create streaming branch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise  # 상위로 예외 전파

    def _create_recording_branch(self):
        """녹화 브랜치 생성"""
        try:
            # 녹화 디렉토리 생성
            self.recording_dir.mkdir(parents=True, exist_ok=True)

            # 녹화 큐
            record_queue = Gst.ElementFactory.make("queue", "record_queue")
            record_queue.set_property("max-size-buffers", 200)
            record_queue.set_property("max-size-time", 0)
            record_queue.set_property("max-size-bytes", 0)

            # Valve 엘리먼트 - 녹화 on/off 제어
            self.recording_valve = Gst.ElementFactory.make("valve", "recording_valve")
            self.recording_valve.set_property("drop", True)  # 초기에는 녹화 중지

            # Muxer (MP4)
            muxer = Gst.ElementFactory.make("mp4mux", "muxer")
            muxer.set_property("fragment-duration", 1000)  # 1초 단위 프래그먼트
            muxer.set_property("streamable", True)

            # 파일 싱크
            self.file_sink = Gst.ElementFactory.make("filesink", "filesink")

            # 엘리먼트를 파이프라인에 추가
            self.pipeline.add(record_queue)
            self.pipeline.add(self.recording_valve)
            self.pipeline.add(muxer)
            self.pipeline.add(self.file_sink)

            # 엘리먼트 연결
            record_queue.link(self.recording_valve)
            self.recording_valve.link(muxer)
            muxer.link(self.file_sink)

            # Tee에서 녹화 큐로 연결
            tee_pad = self.tee.request_pad_simple("src_%u")
            queue_pad = record_queue.get_static_pad("sink")
            tee_pad.link(queue_pad)

            logger.debug("Recording branch created")

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
            logger.error(f"Pipeline error: {err}, {debug}")
            self.stop()
        elif t == Gst.MessageType.EOS:
            logger.info("End of stream")
            if self._is_recording:
                self._rotate_recording_file()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                logger.debug(f"Pipeline state: {old_state.value_nick} -> {new_state.value_nick}")

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

            # PLAYING 상태로 전환
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to set pipeline to PLAYING state")
                bus_msg = self.bus.pop_filtered(Gst.MessageType.ERROR)
                if bus_msg:
                    err, debug = bus_msg.parse_error()
                    logger.error(f"Error detail: {err}, Debug: {debug}")
                return False
            elif ret == Gst.StateChangeReturn.ASYNC:
                logger.debug("Pipeline state change is asynchronous, waiting...")
                # 비동기 상태 변경 대기 (최대 5초)
                ret, current_state, pending_state = self.pipeline.get_state(5 * Gst.SECOND)
                if ret != Gst.StateChangeReturn.SUCCESS:
                    logger.error(f"Pipeline state change failed or timed out: {ret}")
                    logger.error(f"Current state: {current_state.value_nick if current_state else 'None'}, Pending: {pending_state.value_nick if pending_state else 'None'}")
                    bus_msg = self.bus.pop_filtered(Gst.MessageType.ERROR)
                    if bus_msg:
                        err, debug = bus_msg.parse_error()
                        logger.error(f"Error detail: {err}, Debug: {debug}")
                    return False
                else:
                    logger.debug(f"Pipeline state successfully changed to: {current_state.value_nick}")

            self._is_playing = True
            logger.debug(f"Pipeline successfully started for {self.camera_name}")

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

            logger.info(f"Pipeline started for {self.camera_name}")
            return True

        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
            return False

    def stop(self):
        """파이프라인 정지"""
        if self.pipeline and self._is_playing:
            logger.info(f"Stopping pipeline for {self.camera_name}")

            # 타임스탬프 업데이트 타이머 정지
            self._stop_timestamp_update()

            # 녹화 중이면 먼저 정지
            if self._is_recording:
                self.stop_recording()

            self.pipeline.set_state(Gst.State.NULL)
            self._is_playing = False

            if self._main_loop:
                self._main_loop.quit()

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            logger.info(f"Pipeline stopped for {self.camera_name}")

    def start_recording(self) -> bool:
        """녹화 시작"""
        if not self._is_playing:
            logger.error("Pipeline is not running")
            return False

        if self._is_recording:
            logger.warning(f"Already recording: {self.camera_name}")
            return False

        # Valve 기반이므로 모든 모드에서 녹화 가능
        # 단, STREAMING_ONLY 모드에서는 경고 표시
        if self.mode == PipelineMode.STREAMING_ONLY:
            logger.warning(f"Starting recording in STREAMING_ONLY mode - consider changing to BOTH mode")

        try:
            # 녹화 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
            date_dir.mkdir(exist_ok=True)

            self.current_recording_file = str(date_dir / f"{self.camera_id}_{timestamp}.mp4")

            # 파일 싱크 설정
            self.file_sink.set_property("location", self.current_recording_file)

            # Valve 열기 (녹화 시작)
            self.recording_valve.set_property("drop", False)

            self._is_recording = True
            self.recording_start_time = time.time()

            # 파일 회전 타이머 시작
            self._schedule_file_rotation()

            logger.success(f"Recording started: {self.current_recording_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> bool:
        """녹화 정지"""
        if not self._is_recording:
            logger.warning(f"Not recording: {self.camera_name}")
            return False

        try:
            # Valve 닫기 (녹화 중지)
            if self.recording_valve:
                self.recording_valve.set_property("drop", True)

            # EOS 이벤트 전송
            if self.file_sink:
                pad = self.file_sink.get_static_pad("sink")
                if pad:
                    pad.send_event(Gst.Event.new_eos())

            self._is_recording = False

            logger.info(f"Recording stopped: {self.current_recording_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return False

    def _rotate_recording_file(self):
        """녹화 파일 회전"""
        if not self._is_recording:
            return

        logger.info(f"Rotating recording file for {self.camera_name}")

        # 현재 녹화 정지
        self.stop_recording()

        # 짧은 대기
        time.sleep(0.5)

        # 새 파일로 녹화 시작
        self.start_recording()

    def _schedule_file_rotation(self):
        """파일 회전 스케줄링"""
        def check_rotation():
            if self._is_recording and self.recording_start_time:
                elapsed = time.time() - self.recording_start_time
                if elapsed >= self.file_duration:
                    self._rotate_recording_file()
                    self.recording_start_time = time.time()

                # 다음 체크 스케줄
                if self._is_recording:
                    timer = threading.Timer(10.0, check_rotation)
                    timer.daemon = True
                    timer.start()

        # 첫 체크 스케줄
        timer = threading.Timer(10.0, check_rotation)
        timer.daemon = True
        timer.start()

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
            # 필수 엘리먼트 확인
            essential_elements = [
                ("source", "rtspsrc"),
                ("depay", "rtph264depay"),
                ("parse", "h264parse"),
                ("tee", "tee"),
                ("stream_queue", "queue"),
                ("streaming_valve", "valve"),
                ("decoder", "decoder"),
                ("convert", "videoconvert"),
                ("scale", "videoscale"),
                ("videosink", "video sink")
            ]

            for name, description in essential_elements:
                element = self.pipeline.get_by_name(name)
                if not element:
                    # videosink은 이름이 다를 수 있음
                    if name == "videosink" and self.video_sink:
                        continue
                    logger.error(f"Essential element '{name}' ({description}) not found in pipeline")
                    return False
                logger.debug(f"Verified element: {name} ({element.get_factory().get_name()})")

            # 특정 모드에서만 필요한 엘리먼트
            if self.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                recording_elements = [
                    ("record_queue", "recording queue"),
                    ("recording_valve", "recording valve"),
                    ("muxer", "mp4mux"),
                    ("filesink", "file sink")
                ]
                for name, description in recording_elements:
                    element = self.pipeline.get_by_name(name)
                    if not element:
                        logger.error(f"Recording element '{name}' ({description}) not found")
                        return False

            logger.debug("Pipeline element verification successful")
            return True

        except Exception as e:
            logger.error(f"Error during pipeline verification: {e}")
            return False

    def _apply_mode_settings(self):
        """현재 모드에 따라 Valve 설정 적용"""
        if not self.streaming_valve or not self.recording_valve:
            logger.warning("Valves not initialized yet")
            return

        if self.mode == PipelineMode.STREAMING_ONLY:
            self.streaming_valve.set_property("drop", False)
            self.recording_valve.set_property("drop", True)
            logger.debug("Mode: Streaming only - Stream ON, Recording OFF")

        elif self.mode == PipelineMode.RECORDING_ONLY:
            self.streaming_valve.set_property("drop", True)
            self.recording_valve.set_property("drop", True)  # 녹화는 별도로 시작
            logger.debug("Mode: Recording only - Stream OFF, Recording controlled separately")

        elif self.mode == PipelineMode.BOTH:
            self.streaming_valve.set_property("drop", False)
            self.recording_valve.set_property("drop", True)  # 녹화는 별도로 시작
            logger.debug("Mode: Both - Stream ON, Recording controlled separately")

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