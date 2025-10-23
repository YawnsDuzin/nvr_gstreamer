"""
GStreamer Pipeline Manager for RTSP streaming
Handles creation and management of GStreamer pipelines for video streaming
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GObject, GstVideo
import threading
from typing import Optional, Callable, Dict
from loguru import logger
from .unified_pipeline import UnifiedPipeline, PipelineMode
from utils.gstreamer_utils import get_video_sink, get_available_h264_decoder
from config.config_manager import ConfigManager
from datetime import datetime

# Initialize GStreamer
Gst.init(None)


class PipelineManager:
    """Manages GStreamer pipeline for RTSP streaming"""

    def __init__(self, rtsp_url: str, on_frame_callback: Optional[Callable] = None, window_handle=None,
                 use_unified_pipeline: bool = False, camera_id: str = None, camera_name: str = None):
        """
        Initialize Pipeline Manager

        Args:
            rtsp_url: RTSP stream URL
            on_frame_callback: Callback function for frame processing
            window_handle: Window handle for video rendering (optional)
            use_unified_pipeline: Use unified pipeline for streaming and recording
            camera_id: Camera ID for unified pipeline
            camera_name: Camera name for unified pipeline
        """
        self.rtsp_url = rtsp_url
        self.pipeline = None
        self.bus = None
        self.on_frame_callback = on_frame_callback
        self.window_handle = window_handle
        self.video_sink = None
        self._is_playing = False
        self._main_loop = None
        self._thread = None

        # Unified pipeline support
        self.use_unified_pipeline = use_unified_pipeline
        self.unified_pipeline = None
        self.camera_id = camera_id or "default"
        self.camera_name = camera_name or "Camera"

        logger.info(f"Pipeline manager initialized for URL: {rtsp_url} (unified: {use_unified_pipeline})")


    def create_pipeline(self, use_hardware_decode: bool = False) -> bool:
        """
        Create GStreamer pipeline for RTSP streaming

        Args:
            use_hardware_decode: Use hardware acceleration if available

        Returns:
            True if pipeline created successfully
        """
        try:
            # Get streaming configuration for OSD
            config = ConfigManager.get_instance()
            streaming_config = config.get_streaming_config()

            # OSD 설정
            show_timestamp = streaming_config.get("show_timestamp", True)
            show_camera_name = streaming_config.get("show_camera_name", True)
            osd_enabled = show_timestamp or show_camera_name

            # Get the best available decoder and video sink from utils
            decoder = get_available_h264_decoder()
            video_sink = get_video_sink()

            # OSD textoverlay 파라미터 생성
            osd_element = ""
            if osd_enabled:
                osd_font_size = streaming_config.get("osd_font_size", 14)
                osd_font_color = streaming_config.get("osd_font_color", [255, 255, 255])
                r, g, b = osd_font_color[0], osd_font_color[1], osd_font_color[2]
                color_argb = 0xFF000000 | (r << 16) | (g << 8) | b

                # OSD 텍스트 생성
                text_parts = []
                if show_camera_name:
                    text_parts.append(self.camera_name)
                if show_timestamp:
                    text_parts.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                osd_text = " | ".join(text_parts)

                # textoverlay 엘리먼트 문자열
                osd_element = (
                    f'textoverlay text="{osd_text}" '
                    f'font-desc="Sans Bold {osd_font_size}" '
                    f'color={color_argb} '
                    'shaded-background=true '
                    'valignment=top halignment=left '
                    'xpad=10 ypad=10 '
                    'line-alignment=left draw-shadow=false draw-outline=false ! '
                )
                logger.info(f"OSD enabled: {osd_text}")

            # Build pipeline string with better compatibility and queue for smoother playback
            if decoder == "v4l2h264dec":
                # V4L2 hardware decoder needs specific caps
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp buffer-mode=auto ! "
                    "queue max-size-buffers=100 max-size-time=0 max-size-bytes=0 ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    "video/x-h264,stream-format=byte-stream,alignment=au ! "
                    f"{decoder} ! "
                    "queue ! "
                    "videoconvert ! "
                    f"{osd_element}"  # OSD 추가
                    "videoscale ! "
                    "video/x-raw,width=1280,height=720 ! "
                    "queue ! "
                    f"{video_sink} name=videosink sync=true force-aspect-ratio=true"
                )
            elif decoder == "omxh264dec":
                # OMX decoder pipeline
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp buffer-mode=auto ! "
                    "queue max-size-buffers=100 max-size-time=0 max-size-bytes=0 ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    f"{decoder} ! "
                    "queue ! "
                    "videoconvert ! "
                    f"{osd_element}"  # OSD 추가
                    "videoscale ! "
                    "video/x-raw,width=1280,height=720 ! "
                    "queue ! "
                    f"{video_sink} name=videosink sync=true force-aspect-ratio=true"
                )
            elif decoder == "h264parse":
                # No decoder available, just parse
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp buffer-mode=auto ! "
                    "queue ! "
                    "rtph264depay ! h264parse ! "
                    f"{video_sink} name=videosink sync=true"
                )
            else:
                # Software decoder (avdec_h264, etc)
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp buffer-mode=auto ! "
                    "queue max-size-buffers=100 max-size-time=0 max-size-bytes=0 ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    f"{decoder} ! "
                    "queue ! "
                    "videoconvert ! "
                    f"{osd_element}"  # OSD 추가
                    "videoscale ! "
                    "video/x-raw,width=1280,height=720 ! "
                    "queue ! "
                    f"{video_sink} name=videosink sync=true force-aspect-ratio=true"
                )

            logger.debug(f"Creating pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Get the video sink element
            self.video_sink = self.pipeline.get_by_name("videosink")

            # Enable sync message emission for window handle setup
            if self.window_handle:
                self._setup_window_handle_sync(self.window_handle)

            # Set up bus for message handling
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # Enable sync message emission for window handle setup
            if self.window_handle:
                self.bus.enable_sync_message_emission()
                self.bus.connect('sync-message::element', lambda bus, msg: self._on_sync_message_direct(bus, msg))

            logger.info("Pipeline created successfully")
            return True

        except GLib.Error as e:
            logger.error(f"Failed to create pipeline: {e}")
            return False

    def create_pipeline_with_appsink(self, use_hardware_decode: bool = False) -> bool:
        """
        Create pipeline with appsink for frame capture

        Args:
            use_hardware_decode: Use hardware acceleration if available

        Returns:
            True if pipeline created successfully
        """
        try:
            # Get the best available decoder from utils
            decoder = get_available_h264_decoder()

            # Build pipeline with appsink for frame extraction
            if decoder == "h264parse":
                # No decoder available
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 ! "
                    "rtph264depay ! h264parse ! "
                    "appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
                )
            else:
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} latency=200 ! "
                    "rtph264depay ! h264parse ! "
                    f"{decoder} ! "
                    "videoconvert ! "
                    "video/x-raw,format=RGB ! "
                    "appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
                )

            logger.debug(f"Creating pipeline with appsink: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Get appsink and connect signal
            appsink = self.pipeline.get_by_name("sink")
            if appsink and self.on_frame_callback:
                appsink.connect("new-sample", self._on_new_sample)

            # Set up bus
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            logger.info("Pipeline with appsink created successfully")
            return True

        except GLib.Error as e:
            logger.error(f"Failed to create pipeline with appsink: {e}")
            return False

    def set_window_handle(self, window_handle):
        """
        Set the window handle for video rendering

        Args:
            window_handle: Platform-specific window handle
        """
        # UnifiedPipeline 사용 시 window_handle 업데이트
        if self.use_unified_pipeline and self.unified_pipeline:
            if self.unified_pipeline.video_sink:
                try:
                    # Convert PyQt window handle to integer
                    if hasattr(window_handle, '__int__'):
                        window_id = int(window_handle)
                    else:
                        window_id = window_handle

                    # Use GstVideoOverlay interface method
                    self.unified_pipeline.video_sink.set_window_handle(window_id)
                    logger.debug(f"Set window handle for UnifiedPipeline: {window_id}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to set window handle for UnifiedPipeline: {e}")
            else:
                logger.debug("UnifiedPipeline video_sink not available yet")
            return

        # 일반 파이프라인의 경우
        if self.video_sink:
            try:
                # Convert PyQt window handle to integer
                if hasattr(window_handle, '__int__'):
                    window_id = int(window_handle)
                else:
                    window_id = window_handle

                # Use correct GstVideoOverlay interface method
                try:
                    # GstVideoOverlay.set_window_handle is a method on the element, not the class
                    self.video_sink.set_window_handle(window_id)
                    logger.debug(f"Set window handle directly: {window_id}")
                except AttributeError:
                    try:
                        # Try using set_property for ximagesink/xvimagesink
                        self.video_sink.set_property("force-aspect-ratio", True)
                        # For X11 based sinks
                        self.video_sink.set_xwindow_id(window_id)
                        logger.debug(f"Set window handle using set_xwindow_id: {window_id}")
                    except AttributeError:
                        try:
                            # Alternative method using props
                            self.video_sink.props.window_handle = window_id
                            logger.debug(f"Set window handle using props: {window_id}")
                        except Exception as e:
                            logger.error(f"All window handle methods failed: {e}")

            except Exception as e:
                logger.error(f"Failed to set window handle: {e}")
                # Try one more fallback - sync bus message
                self._setup_window_handle_sync(window_handle)
        else:
            logger.warning("Video sink not available to set window handle")

    def _on_sync_message_direct(self, bus, message):
        """Handle sync message for window handle"""
        if message.get_structure() is None:
            return
        if message.get_structure().get_name() == 'prepare-window-handle':
            if self.window_handle:
                window_id = int(self.window_handle) if hasattr(self.window_handle, '__int__') else self.window_handle
                try:
                    # Get the video sink from the message
                    sink = message.src
                    # Try different methods to set window handle
                    if hasattr(sink, 'set_window_handle'):
                        sink.set_window_handle(window_id)
                    elif hasattr(sink, 'set_xwindow_id'):
                        sink.set_xwindow_id(window_id)
                    else:
                        sink.set_property("window-handle", window_id)
                    logger.debug(f"Set window handle via prepare-window-handle: {window_id}")
                except Exception as e:
                    logger.error(f"Failed in prepare-window-handle: {e}")

    def _setup_window_handle_sync(self, window_handle):
        """
        Setup window handle using sync bus message (fallback method)

        Args:
            window_handle: Window handle
        """
        try:
            if hasattr(window_handle, '__int__'):
                window_id = int(window_handle)
            else:
                window_id = window_handle

            # Connect to sync-message signal on bus
            def on_sync_message(bus, message):
                if message.get_structure() is None:
                    return
                if message.get_structure().get_name() == 'prepare-window-handle':
                    # Set window handle when sink requests it
                    sink = message.src
                    sink.set_window_handle(window_id)
                    logger.debug(f"Set window handle via sync message: {window_id}")

            if self.bus:
                self.bus.enable_sync_message_emission()
                self.bus.connect('sync-message::element', on_sync_message)
                logger.debug("Setup window handle sync message handler")
        except Exception as e:
            logger.error(f"Failed to setup window handle sync: {e}")

    def start(self) -> bool:
        """
        Start the pipeline (automatically detects unified or regular pipeline)

        Returns:
            True if started successfully
        """
        # UnifiedPipeline 사용 중이면 start_unified() 호출
        if self.use_unified_pipeline and self.unified_pipeline:
            return self.start_unified()

        # 일반 파이프라인 시작
        if not self.pipeline:
            logger.error("Pipeline not created. Call create_pipeline first.")
            return False

        try:
            # Start the pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start pipeline")
                return False

            self._is_playing = True

            # Start main loop in separate thread
            self._main_loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._run_main_loop)
            self._thread.daemon = True
            self._thread.start()

            logger.info("Pipeline started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
            return False

    def stop(self):
        """Stop the pipeline (automatically detects unified or regular pipeline)"""
        # UnifiedPipeline 사용 중이면 stop_unified() 호출
        if self.use_unified_pipeline and self.unified_pipeline:
            self.stop_unified()
            return

        # 일반 파이프라인 정지
        if self.pipeline and self._is_playing:
            logger.info("Stopping pipeline...")

            # Stop the pipeline
            self.pipeline.set_state(Gst.State.NULL)
            self._is_playing = False

            # Stop main loop
            if self._main_loop:
                self._main_loop.quit()

            # Wait for thread to finish
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            logger.info("Pipeline stopped")

    def _run_main_loop(self):
        """Run GLib main loop in separate thread"""
        try:
            self._main_loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")

    def _on_bus_message(self, bus, message):
        """
        Handle bus messages

        Args:
            bus: GStreamer bus
            message: Bus message
        """
        t = message.type

        if t == Gst.MessageType.EOS:
            logger.info("End-of-stream reached")
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err}, {debug}")
            self.stop()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {warn}, {debug}")
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                logger.debug(f"Pipeline state changed: {old_state.value_nick} -> {new_state.value_nick}")

    def _on_new_sample(self, sink):
        """
        Handle new sample from appsink

        Args:
            sink: AppSink element

        Returns:
            Gst.FlowReturn.OK
        """
        sample = sink.emit("pull-sample")
        if sample and self.on_frame_callback:
            # Extract buffer and caps
            buffer = sample.get_buffer()
            caps = sample.get_caps()

            # Get video dimensions
            struct = caps.get_structure(0)
            width = struct.get_value("width")
            height = struct.get_value("height")

            # Call callback with frame data
            self.on_frame_callback(buffer, width, height)

        return Gst.FlowReturn.OK

    def get_pipeline_state(self) -> str:
        """
        Get current pipeline state

        Returns:
            State string
        """
        if not self.pipeline:
            return "NULL"

        state, _, _ = self.pipeline.get_state(0)
        return state.value_nick

    def is_playing(self) -> bool:
        """Check if pipeline is playing (automatically detects unified or regular pipeline)"""
        # UnifiedPipeline 사용 중이면 unified pipeline 상태 확인
        if self.use_unified_pipeline and self.unified_pipeline:
            return self.unified_pipeline._is_playing

        # 일반 파이프라인 상태
        return self._is_playing

    def create_unified_pipeline(self, mode: PipelineMode = PipelineMode.BOTH) -> bool:
        """
        Create unified pipeline for streaming and recording

        Args:
            mode: Pipeline operation mode

        Returns:
            True if pipeline created successfully
        """
        if not self.use_unified_pipeline:
            logger.warning("Unified pipeline not enabled. Use create_pipeline() instead.")
            return False

        try:
            # Create unified pipeline instance
            self.unified_pipeline = UnifiedPipeline(
                rtsp_url=self.rtsp_url,
                camera_id=self.camera_id,
                camera_name=self.camera_name,
                window_handle=self.window_handle,
                mode=mode
            )

            # Create the pipeline
            if self.unified_pipeline.create_pipeline():
                logger.info(f"Unified pipeline created successfully (mode: {mode.value})")
                return True
            else:
                logger.error("Failed to create unified pipeline")
                return False

        except Exception as e:
            logger.error(f"Error creating unified pipeline: {e}")
            return False

    def start_unified(self) -> bool:
        """
        Start unified pipeline

        Returns:
            True if started successfully
        """
        if not self.unified_pipeline:
            logger.error("Unified pipeline not created. Call create_unified_pipeline first.")
            return False

        return self.unified_pipeline.start()

    def stop_unified(self):
        """Stop unified pipeline"""
        if self.unified_pipeline:
            self.unified_pipeline.stop()
            self.unified_pipeline = None

    def start_recording(self) -> bool:
        """
        Start recording (unified pipeline only)

        Returns:
            True if recording started successfully
        """
        if not self.unified_pipeline:
            logger.error("Unified pipeline not available for recording")
            return False

        return self.unified_pipeline.start_recording()

    def stop_recording(self) -> bool:
        """
        Stop recording (unified pipeline only)

        Returns:
            True if recording stopped successfully
        """
        if not self.unified_pipeline:
            logger.error("Unified pipeline not available")
            return False

        return self.unified_pipeline.stop_recording()

    def get_unified_status(self) -> Dict:
        """
        Get unified pipeline status

        Returns:
            Status dictionary
        """
        if self.unified_pipeline:
            return self.unified_pipeline.get_status()
        return {}

    def set_pipeline_mode(self, mode: PipelineMode) -> bool:
        """
        Set pipeline mode (unified pipeline only)

        Args:
            mode: New pipeline mode

        Returns:
            True if mode changed successfully
        """
        if not self.unified_pipeline:
            logger.error("Unified pipeline not available")
            return False

        return self.unified_pipeline.set_mode(mode)

    def __del__(self):
        """Cleanup on deletion"""
        if self.unified_pipeline:
            self.stop_unified()
        else:
            self.stop()