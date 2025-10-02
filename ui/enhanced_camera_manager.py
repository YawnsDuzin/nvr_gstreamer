"""
Enhanced Camera Manager
Manages camera connections with proper window handle assignment
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, Optional
from loguru import logger

from streaming.camera_stream import CameraStream, CameraConfig
from config.config_manager import CameraConfigData


class EnhancedCameraManager(QObject):
    """Manages camera streams and window assignments"""

    # Signals
    camera_connected = pyqtSignal(str)  # camera_id
    camera_disconnected = pyqtSignal(str)  # camera_id
    camera_error = pyqtSignal(str, str)  # camera_id, error_message

    def __init__(self):
        super().__init__()
        self.camera_streams: Dict[str, CameraStream] = {}
        self.window_handles: Dict[str, int] = {}  # camera_id -> window_handle

    def add_camera(self, config: CameraConfigData) -> bool:
        """
        Add a camera to management

        Args:
            config: Camera configuration

        Returns:
            True if added successfully
        """
        if config.camera_id in self.camera_streams:
            logger.warning(f"Camera {config.camera_id} already exists")
            return False

        # Create camera stream
        stream_config = CameraConfig(
            camera_id=config.camera_id,
            name=config.name,
            rtsp_url=config.rtsp_url,
            username=config.username,
            password=config.password,
            use_hardware_decode=config.use_hardware_decode
        )

        stream = CameraStream(stream_config)
        self.camera_streams[config.camera_id] = stream

        logger.info(f"Added camera to manager: {config.name}")
        return True

    def remove_camera(self, camera_id: str) -> bool:
        """
        Remove a camera from management

        Args:
            camera_id: Camera ID

        Returns:
            True if removed successfully
        """
        if camera_id not in self.camera_streams:
            return False

        # Disconnect if connected
        stream = self.camera_streams[camera_id]
        if stream.is_connected():
            stream.disconnect()

        # Remove from management
        del self.camera_streams[camera_id]
        if camera_id in self.window_handles:
            del self.window_handles[camera_id]

        logger.info(f"Removed camera from manager: {camera_id}")
        return True

    def set_window_handle(self, camera_id: str, window_handle: int):
        """
        Set window handle for a camera

        Args:
            camera_id: Camera ID
            window_handle: Window handle for rendering
        """
        self.window_handles[camera_id] = window_handle
        logger.debug(f"Set window handle for {camera_id}: {window_handle}")

        # If camera is already connected, update the window handle
        stream = self.camera_streams.get(camera_id)
        if stream and stream.is_connected() and stream.pipeline_manager:
            stream.pipeline_manager.set_window_handle(window_handle)

    def connect_camera(self, camera_id: str, window_handle: Optional[int] = None) -> bool:
        """
        Connect to a camera stream

        Args:
            camera_id: Camera ID
            window_handle: Optional window handle for rendering

        Returns:
            True if connected successfully
        """
        if camera_id not in self.camera_streams:
            logger.error(f"Camera {camera_id} not found")
            return False

        stream = self.camera_streams[camera_id]

        # Use stored window handle if not provided
        if window_handle is None:
            window_handle = self.window_handles.get(camera_id)

        # Connect with window handle
        if stream.connect(window_handle=window_handle):
            logger.success(f"Connected to camera: {camera_id}")
            self.camera_connected.emit(camera_id)
            return True
        else:
            logger.error(f"Failed to connect to camera: {camera_id}")
            self.camera_error.emit(camera_id, "Connection failed")
            return False

    def disconnect_camera(self, camera_id: str) -> bool:
        """
        Disconnect from a camera stream

        Args:
            camera_id: Camera ID

        Returns:
            True if disconnected successfully
        """
        if camera_id not in self.camera_streams:
            return False

        stream = self.camera_streams[camera_id]
        if stream.is_connected():
            stream.disconnect()
            self.camera_disconnected.emit(camera_id)
            logger.info(f"Disconnected camera: {camera_id}")
            return True

        return False

    def connect_all(self):
        """Connect all cameras with assigned window handles"""
        for camera_id, stream in self.camera_streams.items():
            if not stream.is_connected():
                window_handle = self.window_handles.get(camera_id)
                self.connect_camera(camera_id, window_handle)

    def disconnect_all(self):
        """Disconnect all cameras"""
        for camera_id, stream in self.camera_streams.items():
            if stream.is_connected():
                self.disconnect_camera(camera_id)

    def get_camera_stream(self, camera_id: str) -> Optional[CameraStream]:
        """
        Get camera stream by ID

        Args:
            camera_id: Camera ID

        Returns:
            CameraStream or None
        """
        return self.camera_streams.get(camera_id)

    def is_connected(self, camera_id: str) -> bool:
        """
        Check if camera is connected

        Args:
            camera_id: Camera ID

        Returns:
            True if connected
        """
        stream = self.camera_streams.get(camera_id)
        return stream.is_connected() if stream else False

    def assign_camera_to_channel(self, camera_id: str, channel_index: int, window_handle: int):
        """
        Assign a camera to a specific channel with window handle

        Args:
            camera_id: Camera ID
            channel_index: Channel index in grid
            window_handle: Window handle for rendering
        """
        # Store window handle
        self.set_window_handle(camera_id, window_handle)

        # If camera is connected, update the rendering
        stream = self.camera_streams.get(camera_id)
        if stream and stream.is_connected():
            if stream.pipeline_manager:
                stream.pipeline_manager.set_window_handle(window_handle)
                logger.info(f"Updated window handle for connected camera {camera_id}")

    def get_stats(self, camera_id: str) -> Dict:
        """
        Get camera statistics

        Args:
            camera_id: Camera ID

        Returns:
            Statistics dictionary
        """
        stream = self.camera_streams.get(camera_id)
        if stream:
            return stream.get_stats()
        return {}