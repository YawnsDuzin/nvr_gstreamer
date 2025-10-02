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
        self.recording_valve = None
        self.bus = None

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
            # 파이프라인 생성
            self.pipeline = Gst.Pipeline.new("unified-pipeline")

            # RTSP 소스
            rtspsrc = Gst.ElementFactory.make("rtspsrc", "source")
            rtspsrc.set_property("location", self.rtsp_url)
            rtspsrc.set_property("latency", 100)
            rtspsrc.set_property("protocols", "tcp")
            rtspsrc.set_property("tcp-timeout", 5000000)
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

            # 모드에 따라 브랜치 생성
            if self.mode in [PipelineMode.STREAMING_ONLY, PipelineMode.BOTH]:
                self._create_streaming_branch()

            if self.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                self._create_recording_branch()

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # 윈도우 핸들 설정 (스트리밍 모드인 경우)
            if self.window_handle and self.video_sink:
                self.bus.enable_sync_message_emission()
                self.bus.connect("sync-message::element", self._on_sync_message)

            logger.info(f"Unified pipeline created for {self.camera_name} (mode: {self.mode.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to create unified pipeline: {e}")
            return False

    def _create_streaming_branch(self):
        """스트리밍 브랜치 생성"""
        try:
            # 스트리밍 큐
            stream_queue = Gst.ElementFactory.make("queue", "stream_queue")
            stream_queue.set_property("max-size-buffers", 100)
            stream_queue.set_property("max-size-time", 0)
            stream_queue.set_property("max-size-bytes", 0)

            # 디코더
            decoder = Gst.ElementFactory.make("avdec_h264", "decoder")

            # 비디오 변환
            convert = Gst.ElementFactory.make("videoconvert", "convert")
            scale = Gst.ElementFactory.make("videoscale", "scale")

            # 캡슐 필터 (해상도 설정)
            caps_filter = Gst.ElementFactory.make("capsfilter", "caps_filter")
            caps = Gst.Caps.from_string("video/x-raw,width=1280,height=720")
            caps_filter.set_property("caps", caps)

            # 최종 큐
            final_queue = Gst.ElementFactory.make("queue", "final_queue")
            final_queue.set_property("max-size-buffers", 3)
            final_queue.set_property("leaky", 2)  # downstream leaky

            # 비디오 싱크
            if os.name == 'nt':  # Windows
                self.video_sink = Gst.ElementFactory.make("d3dvideosink", "videosink")
            else:  # Linux/Raspberry Pi
                # 라즈베리파이에서는 glimagesink가 더 효율적
                self.video_sink = Gst.ElementFactory.make("glimagesink", "videosink")
                if not self.video_sink:
                    self.video_sink = Gst.ElementFactory.make("xvimagesink", "videosink")

            self.video_sink.set_property("sync", False)
            self.video_sink.set_property("async", False)

            # 엘리먼트를 파이프라인에 추가
            self.pipeline.add(stream_queue)
            self.pipeline.add(decoder)
            self.pipeline.add(convert)
            self.pipeline.add(scale)
            self.pipeline.add(caps_filter)
            self.pipeline.add(final_queue)
            self.pipeline.add(self.video_sink)

            # 엘리먼트 연결
            stream_queue.link(decoder)
            decoder.link(convert)
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
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start pipeline")
                return False

            self._is_playing = True

            # 메인 루프 시작
            self._main_loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._run_main_loop)
            self._thread.daemon = True
            self._thread.start()

            logger.info(f"Pipeline started for {self.camera_name}")
            return True

        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
            return False

    def stop(self):
        """파이프라인 정지"""
        if self.pipeline and self._is_playing:
            logger.info(f"Stopping pipeline for {self.camera_name}")

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

        if self.mode not in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
            logger.error(f"Recording not enabled in current mode: {self.mode.value}")
            return False

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

    def set_mode(self, mode: PipelineMode):
        """파이프라인 모드 변경"""
        if self._is_playing:
            logger.warning("Cannot change mode while pipeline is running")
            return False

        self.mode = mode
        logger.info(f"Pipeline mode changed to: {mode.value}")
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