"""
Simplified pipeline for embedded video rendering
Uses playbin or decodebin for better compatibility
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo
from typing import Optional, Callable
import threading
from loguru import logger

# Initialize GStreamer
Gst.init(None)


class SimplePipeline:
    """Simple GStreamer pipeline for RTSP with embedded rendering"""

    def __init__(self, rtsp_url: str):
        """
        Initialize simple pipeline

        Args:
            rtsp_url: RTSP stream URL
        """
        self.rtsp_url = rtsp_url
        self.pipeline = None
        self.bus = None
        self.window_handle = None
        self._is_playing = False
        self._main_loop = None
        self._thread = None

    def create_pipeline(self) -> bool:
        """
        Create simple pipeline using playbin

        Returns:
            True if created successfully
        """
        try:
            # Use playbin for automatic handling
            self.pipeline = Gst.ElementFactory.make("playbin", "player")
            if not self.pipeline:
                logger.error("Failed to create playbin")
                return False

            # Set the URI
            self.pipeline.set_property("uri", self.rtsp_url)

            # Set video sink to ximagesink for embedding
            video_sink = Gst.ElementFactory.make("ximagesink", "videosink")
            if video_sink:
                video_sink.set_property("force-aspect-ratio", True)
                self.pipeline.set_property("video-sink", video_sink)

            # Setup bus
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # Enable sync message emission for window handle
            self.bus.enable_sync_message_emission()
            self.bus.connect("sync-message::element", self._on_sync_message)

            logger.info("Simple pipeline created with playbin")
            return True

        except Exception as e:
            logger.error(f"Failed to create simple pipeline: {e}")
            return False

    def create_decodebin_pipeline(self) -> bool:
        """
        Alternative: Create pipeline using decodebin

        Returns:
            True if created successfully
        """
        try:
            pipeline_str = (
                f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp ! "
                "decodebin ! "
                "videoconvert ! "
                "videoscale ! "
                "ximagesink name=videosink force-aspect-ratio=true"
            )

            self.pipeline = Gst.parse_launch(pipeline_str)

            # Setup bus
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # Enable sync message emission
            self.bus.enable_sync_message_emission()
            self.bus.connect("sync-message::element", self._on_sync_message)

            logger.info("Pipeline created with decodebin")
            return True

        except Exception as e:
            logger.error(f"Failed to create decodebin pipeline: {e}")
            return False

    def set_window_handle(self, window_handle):
        """
        Set window handle for rendering

        Args:
            window_handle: PyQt window handle
        """
        # Convert to integer
        if hasattr(window_handle, '__int__'):
            self.window_handle = int(window_handle)
        else:
            self.window_handle = window_handle

        logger.debug(f"Window handle set to: {self.window_handle}")

        # If pipeline is already playing, apply immediately
        if self._is_playing and self.pipeline:
            video_sink = self.pipeline.get_property("video-sink")
            if video_sink:
                try:
                    GstVideo.VideoOverlay.set_window_handle(video_sink, self.window_handle)
                    logger.debug("Applied window handle to running pipeline")
                except Exception as e:
                    logger.error(f"Failed to apply window handle: {e}")

    def _on_sync_message(self, bus, message):
        """Handle sync messages from bus"""
        if message.get_structure() is None:
            return

        message_name = message.get_structure().get_name()

        if message_name == "prepare-window-handle":
            # Set window handle when requested
            if self.window_handle:
                video_sink = message.src
                video_sink.set_window_handle(self.window_handle)
                logger.debug(f"Set window handle via sync message: {self.window_handle}")

    def _on_bus_message(self, bus, message):
        """Handle bus messages"""
        t = message.type

        if t == Gst.MessageType.EOS:
            logger.info("End-of-stream")
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err}, {debug}")
            self.stop()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending = message.parse_state_changed()
                logger.debug(f"State changed: {old_state.value_nick} -> {new_state.value_nick}")
        elif t == Gst.MessageType.BUFFERING:
            # Handle buffering
            percent = message.parse_buffering()
            logger.debug(f"Buffering: {percent}%")

    def start(self) -> bool:
        """Start the pipeline"""
        if not self.pipeline:
            logger.error("Pipeline not created")
            return False

        try:
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start pipeline")
                return False

            self._is_playing = True

            # Start main loop in thread
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
        """Run GLib main loop"""
        try:
            self._main_loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")

    def stop(self):
        """Stop the pipeline"""
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
        """Check if pipeline is playing"""
        return self._is_playing