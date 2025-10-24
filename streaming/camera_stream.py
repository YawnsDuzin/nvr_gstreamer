"""
Camera Stream Handler
Manages individual camera streams with connection management and error handling
"""

import time
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from loguru import logger
from .pipeline import UnifiedPipeline, PipelineMode


class StreamStatus(Enum):
    """Stream connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class CameraConfig:
    """Camera configuration"""
    camera_id: str
    name: str
    rtsp_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    use_hardware_decode: bool = False
    reconnect_attempts: int = 3
    reconnect_delay: int = 5


class CameraStream:
    """Handles individual camera stream"""

    def __init__(self, config: CameraConfig):
        """
        Initialize camera stream

        Args:
            config: Camera configuration
        """
        self.config = config
        self.pipeline: Optional[UnifiedPipeline] = None
        self.status = StreamStatus.DISCONNECTED
        self._reconnect_count = 0
        self._last_frame_time = 0
        self._stats = {
            "frames_received": 0,
            "connection_time": 0,
            "last_error": None
        }
        self.window_handle = None  # 미리 할당될 윈도우 핸들 저장

        # Build RTSP URL with credentials if provided
        self._build_rtsp_url()

        logger.info(f"Camera stream initialized: {self.config.name} ({self.config.camera_id})")

    def _build_rtsp_url(self):
        """Build RTSP URL with credentials"""
        if self.config.username and self.config.password:
            # Parse URL and insert credentials
            url_parts = self.config.rtsp_url.split("://")
            if len(url_parts) == 2:
                protocol = url_parts[0]
                rest = url_parts[1]
                self.rtsp_url = f"{protocol}://{self.config.username}:{self.config.password}@{rest}"
            else:
                self.rtsp_url = self.config.rtsp_url
        else:
            self.rtsp_url = self.config.rtsp_url

    def connect(self, frame_callback=None, window_handle=None, enable_recording=False) -> bool:
        """
        Connect to camera stream

        Args:
            frame_callback: Callback for frame processing
            window_handle: Window handle for video rendering
            enable_recording: Enable recording support

        Returns:
            True if connected successfully
        """
        logger.info(f"Connecting to camera: {self.config.name} (ID: {self.config.camera_id})")
        self.status = StreamStatus.CONNECTING

        # 미리 할당된 윈도우 핸들이 있으면 사용, 없으면 매개변수 사용
        handle_to_use = self.window_handle if self.window_handle else window_handle
        if handle_to_use:
            logger.info(f"Using window handle for {self.config.name} (ID: {self.config.camera_id}): {handle_to_use}")
        else:
            logger.warning(f"No window handle available for {self.config.name} (ID: {self.config.camera_id})")

        try:
            # Frame callback은 UnifiedPipeline에서 지원하지 않음
            if frame_callback:
                logger.error(f"Frame callback not supported with UnifiedPipeline for {self.config.name}")
                raise Exception("Frame callback not supported in UnifiedPipeline")

            # Create pipeline directly (녹화 지원 여부에 따라 모드 결정)
            mode = PipelineMode.BOTH if enable_recording else PipelineMode.STREAMING_ONLY

            self.pipeline = UnifiedPipeline(
                rtsp_url=self.rtsp_url,
                camera_id=self.config.camera_id,
                camera_name=self.config.name,
                window_handle=handle_to_use,
                mode=mode
            )

            if not self.pipeline.create_pipeline():
                raise Exception("Failed to create pipeline")

            if not self.pipeline.start():
                raise Exception("Failed to start pipeline")

            self.status = StreamStatus.CONNECTED
            self._reconnect_count = 0
            self._stats["connection_time"] = time.time()

            logger.success(f"Connected to camera: {self.config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to camera {self.config.name}: {e}")
            self.status = StreamStatus.ERROR
            self._stats["last_error"] = str(e)
            self._handle_connection_error()
            return False

    def disconnect(self):
        """Disconnect from camera stream"""
        logger.info(f"Disconnecting camera: {self.config.name}")

        if self.pipeline:
            self.pipeline.stop()
            self.pipeline = None

        self.status = StreamStatus.DISCONNECTED
        logger.info(f"Camera disconnected: {self.config.name}")

    def reconnect(self, frame_callback=None, enable_recording=False) -> bool:
        """
        Attempt to reconnect to camera

        Args:
            frame_callback: Callback for frame processing
            enable_recording: Enable recording support

        Returns:
            True if reconnected successfully
        """
        self.status = StreamStatus.RECONNECTING
        logger.info(f"Attempting to reconnect to camera: {self.config.name}")

        # Disconnect first
        self.disconnect()

        # Wait before reconnecting
        time.sleep(self.config.reconnect_delay)

        # Try to connect
        return self.connect(frame_callback, enable_recording=enable_recording)

    def _handle_connection_error(self):
        """Handle connection errors with reconnection logic"""
        self._reconnect_count += 1

        if self._reconnect_count >= self.config.reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for camera: {self.config.name}")
            self.status = StreamStatus.ERROR
            self._reconnect_count = 0
        else:
            logger.warning(f"Reconnection attempt {self._reconnect_count}/{self.config.reconnect_attempts} for camera: {self.config.name}")

    def is_connected(self) -> bool:
        """Check if stream is connected"""
        return self.status == StreamStatus.CONNECTED and self.pipeline and self.pipeline._is_playing

    def get_stats(self) -> Dict[str, Any]:
        """
        Get stream statistics

        Returns:
            Dictionary with stream stats
        """
        stats = self._stats.copy()
        stats["status"] = self.status.value
        stats["camera_id"] = self.config.camera_id
        stats["camera_name"] = self.config.name

        if self.status == StreamStatus.CONNECTED and self._stats["connection_time"] > 0:
            stats["uptime"] = time.time() - self._stats["connection_time"]

        return stats

    def update_frame_stats(self):
        """Update frame statistics"""
        self._stats["frames_received"] += 1
        self._last_frame_time = time.time()

    def check_stream_health(self, timeout: float = 10.0) -> bool:
        """
        Check if stream is healthy

        Args:
            timeout: Timeout in seconds to consider stream unhealthy

        Returns:
            True if stream is healthy
        """
        if not self.is_connected():
            return False

        # Check if we're receiving frames (if applicable)
        if self._last_frame_time > 0:
            time_since_last_frame = time.time() - self._last_frame_time
            if time_since_last_frame > timeout:
                logger.warning(f"No frames received for {time_since_last_frame:.1f}s from camera: {self.config.name}")
                return False

        return True

    def __str__(self) -> str:
        """String representation"""
        return f"CameraStream({self.config.name}, {self.status.value})"

    def __repr__(self) -> str:
        """Detailed representation"""
        return f"CameraStream(id={self.config.camera_id}, name={self.config.name}, status={self.status.value})"