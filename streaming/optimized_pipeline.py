"""
최적화된 파이프라인 설정
깜빡임 없는 부드러운 재생을 위한 파이프라인
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo
import threading
from typing import Optional
from loguru import logger

# GStreamer 초기화
Gst.init(None)


class OptimizedPipeline:
    """깜빡임 없는 최적화된 파이프라인"""

    def __init__(self, rtsp_url: str, window_handle=None):
        """
        파이프라인 초기화

        Args:
            rtsp_url: RTSP 스트림 URL
            window_handle: 윈도우 핸들
        """
        self.rtsp_url = rtsp_url
        self.window_handle = window_handle
        self.pipeline = None
        self.video_sink = None
        self.bus = None
        self._is_playing = False
        self._main_loop = None
        self._thread = None

    def create_smooth_pipeline(self) -> bool:
        """
        부드러운 재생을 위한 파이프라인 생성

        Returns:
            True if successful
        """
        try:
            # 더블 버퍼링과 최적화된 설정을 사용하는 파이프라인
            pipeline_str = (
                f"rtspsrc location={self.rtsp_url} "
                "latency=100 "  # 레이턴시 감소
                "protocols=tcp "
                "tcp-timeout=5000000 "
                "retry=5 "
                "do-rtcp=true "
                "ntp-sync=false ! "  # NTP 동기화 비활성화로 깜빡임 감소

                # 첫 번째 큐 - RTSP 버퍼링
                "queue "
                "max-size-buffers=200 "
                "max-size-time=0 "
                "max-size-bytes=0 "
                "min-threshold-buffers=50 ! "

                # 디페이로드 및 파싱
                "rtph264depay ! "
                "h264parse ! "

                # 디코더 (자동 선택)
                "avdec_h264 "
                "lowres=1 "  # 빠른 디코딩
                "skip-frame=0 ! "

                # 두 번째 큐 - 디코딩 후 버퍼링
                "queue2 "
                "max-size-buffers=0 "
                "max-size-time=0 "
                "max-size-bytes=10485760 "  # 10MB 버퍼
                "use-buffering=true ! "

                # 비디오 변환
                "videoconvert ! "
                "videoscale method=1 ! "  # 빠른 스케일링
                "video/x-raw,width=1280,height=720 ! "

                # 최종 큐
                "queue "
                "max-size-buffers=3 "
                "max-size-time=0 "
                "max-size-bytes=0 "
                "leaky=downstream ! "  # 오래된 프레임 드롭

                # 비디오 싱크
                "xvimagesink "
                "name=videosink "
                "sync=false "  # 동기화 비활성화
                "async=false "  # 비동기 비활성화
                "qos=false "  # QoS 비활성화로 깜빡임 방지
                "force-aspect-ratio=true"
            )

            logger.debug(f"Creating optimized pipeline")
            self.pipeline = Gst.parse_launch(pipeline_str)

            # 비디오 싱크 가져오기
            self.video_sink = self.pipeline.get_by_name("videosink")

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # 윈도우 핸들 설정
            if self.window_handle:
                self.bus.enable_sync_message_emission()
                self.bus.connect("sync-message::element", self._on_sync_message)

            logger.info("Optimized pipeline created")
            return True

        except Exception as e:
            logger.error(f"Failed to create optimized pipeline: {e}")
            return False

    def create_simple_pipeline(self) -> bool:
        """
        간단한 파이프라인 (대체용)

        Returns:
            True if successful
        """
        try:
            # 가장 간단한 형태의 파이프라인
            pipeline_str = (
                f"rtspsrc location={self.rtsp_url} latency=0 ! "
                "decodebin ! "
                "videoconvert ! "
                "autovideosink"
            )

            self.pipeline = Gst.parse_launch(pipeline_str)

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            logger.info("Simple pipeline created")
            return True

        except Exception as e:
            logger.error(f"Failed to create simple pipeline: {e}")
            return False

    def set_window_handle(self, window_handle):
        """윈도우 핸들 설정"""
        if hasattr(window_handle, '__int__'):
            self.window_handle = int(window_handle)
        else:
            self.window_handle = window_handle

        if self.video_sink:
            try:
                GstVideo.VideoOverlay.set_window_handle(self.video_sink, self.window_handle)
                logger.debug(f"Set window handle: {self.window_handle}")
            except Exception as e:
                logger.error(f"Failed to set window handle: {e}")

    def _on_sync_message(self, bus, message):
        """동기 메시지 처리"""
        if message.get_structure() is None:
            return

        if message.get_structure().get_name() == 'prepare-window-handle':
            if self.window_handle:
                sink = message.src
                # 여러 방법 시도
                try:
                    if hasattr(sink, 'set_window_handle'):
                        sink.set_window_handle(self.window_handle)
                    elif hasattr(sink, 'set_xwindow_id'):
                        sink.set_xwindow_id(self.window_handle)
                    else:
                        GstVideo.VideoOverlay.set_window_handle(sink, self.window_handle)
                    logger.debug(f"Window handle set via sync message")
                except Exception as e:
                    logger.error(f"Failed to set window handle in sync: {e}")

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err}")
            self.stop()
        elif t == Gst.MessageType.EOS:
            logger.info("End of stream")
            self.stop()
        elif t == Gst.MessageType.BUFFERING:
            # 버퍼링 처리
            percent = message.parse_buffering()
            if percent < 100:
                # 버퍼링 중이면 일시 정지
                self.pipeline.set_state(Gst.State.PAUSED)
            else:
                # 버퍼링 완료되면 재생
                self.pipeline.set_state(Gst.State.PLAYING)

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

            logger.info("Pipeline started")
            return True

        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
            return False

    def _run_main_loop(self):
        """메인 루프 실행"""
        try:
            self._main_loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")

    def stop(self):
        """파이프라인 정지"""
        if self.pipeline and self._is_playing:
            logger.info("Stopping pipeline...")

            self.pipeline.set_state(Gst.State.NULL)
            self._is_playing = False

            if self._main_loop:
                self._main_loop.quit()

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            logger.info("Pipeline stopped")

    def is_playing(self) -> bool:
        """재생 중인지 확인"""
        return self._is_playing