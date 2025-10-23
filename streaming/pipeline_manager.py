"""
GStreamer Pipeline Manager for RTSP streaming
Handles creation and management of GStreamer pipelines for video streaming
Now uses UnifiedPipeline exclusively for better performance and consistency
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst
from typing import Dict
from loguru import logger
from .unified_pipeline import UnifiedPipeline, PipelineMode

# Initialize GStreamer
Gst.init(None)


class PipelineManager:
    """Manages GStreamer pipeline for RTSP streaming using UnifiedPipeline"""

    def __init__(self, rtsp_url: str, window_handle=None,
                 camera_id: str = None, camera_name: str = None):
        """
        Initialize Pipeline Manager

        Args:
            rtsp_url: RTSP stream URL
            window_handle: Window handle for video rendering (optional)
            camera_id: Camera ID
            camera_name: Camera name
        """
        self.rtsp_url = rtsp_url
        self.window_handle = window_handle
        self.unified_pipeline = None
        self.camera_id = camera_id or "default"
        self.camera_name = camera_name or "Camera"

        logger.info(f"Pipeline manager initialized for URL: {rtsp_url} (UnifiedPipeline)")

    def set_window_handle(self, window_handle):
        """
        Set the window handle for video rendering

        Args:
            window_handle: Platform-specific window handle
        """
        if self.unified_pipeline:
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
        else:
            logger.warning("Unified pipeline not created yet")

    def start(self) -> bool:
        """
        Start the pipeline

        Returns:
            True if started successfully
        """
        if not self.unified_pipeline:
            logger.error("Pipeline not created. Call create_unified_pipeline first.")
            return False

        return self.unified_pipeline.start()

    def stop(self):
        """Stop the pipeline"""
        if self.unified_pipeline:
            self.unified_pipeline.stop()
            self.unified_pipeline = None

    def is_playing(self) -> bool:
        """Check if pipeline is playing"""
        if self.unified_pipeline:
            return self.unified_pipeline._is_playing
        return False

    def create_unified_pipeline(self, mode: PipelineMode = PipelineMode.STREAMING_ONLY) -> bool:
        """
        Create unified pipeline for streaming and recording

        Args:
            mode: Pipeline operation mode (STREAMING_ONLY, RECORDING_ONLY, BOTH)

        Returns:
            True if pipeline created successfully
        """
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

    def start_recording(self) -> bool:
        """
        Start recording

        Returns:
            True if recording started successfully
        """
        if not self.unified_pipeline:
            logger.error("Unified pipeline not available for recording")
            return False

        return self.unified_pipeline.start_recording()

    def stop_recording(self) -> bool:
        """
        Stop recording

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
        Set pipeline mode

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
            self.stop()
