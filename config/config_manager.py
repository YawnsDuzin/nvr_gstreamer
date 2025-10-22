"""
Configuration Manager
Handles application configuration and camera settings
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class AppConfig:
    """Application configuration"""
    app_name: str = "PyNVR"
    version: str = "0.1.0"
    default_layout: str = "2x2"
    recording_path: str = "recordings"
    log_level: str = "INFO"
    use_hardware_acceleration: bool = True
    max_reconnect_attempts: int = 3
    reconnect_delay: int = 5


@dataclass
class CameraConfigData:
    """Camera configuration data"""
    camera_id: str
    name: str
    rtsp_url: str
    enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    use_hardware_decode: bool = False
    recording_enabled: bool = False
    motion_detection: bool = False


class ConfigManager:
    """Manages application and camera configurations"""

    def __init__(self, config_file: Optional[str] = None, auto_save: bool = False):
        """
        Initialize configuration manager

        Args:
            config_file: Path to configuration file (default: IT_RNVR.yaml)
            auto_save: Automatically save config on changes (default: False for safety)
        """
        self.config_file = Path(config_file) if config_file else Path("IT_RNVR.yaml")
        self.app_config = AppConfig()
        self.cameras: List[CameraConfigData] = []
        self.logging_config: Dict[str, Any] = {}  # 로깅 설정 저장
        self.auto_save = auto_save  # 자동 저장 플래그

        # Create default config directory
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)

        # Load configuration
        self.load_config()

    def load_config(self) -> bool:
        """
        Load configuration from file

        Returns:
            True if loaded successfully
        """
        if not self.config_file.exists():
            logger.warning(f"Config file not found: {self.config_file}")
            self.create_default_config()
            return True

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                if self.config_file.suffix == '.yaml' or self.config_file.suffix == '.yml':
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            # Load app config
            if 'app' in data:
                app_data = data['app']
                self.app_config = AppConfig(**app_data)

            # Load cameras
            if 'cameras' in data:
                self.cameras = []
                logger.debug(f"Raw cameras data from config: {data['cameras']}")
                for camera_data in data['cameras']:
                    logger.debug(f"Processing camera data: {camera_data}")
                    camera = CameraConfigData(**camera_data)
                    self.cameras.append(camera)
                    logger.debug(f"Added camera: {camera.camera_id} - enabled: {camera.enabled}")
            else:
                logger.warning("No 'cameras' section found in configuration!")

            # Load logging configuration
            if 'logging' in data:
                self.logging_config = data['logging']
                logger.debug(f"Loaded logging configuration: {self.logging_config.keys()}")
            else:
                logger.debug("No 'logging' section found in configuration, using defaults")
                self.logging_config = {}

            logger.info(f"Configuration loaded from {self.config_file}")
            logger.info(f"Loaded {len(self.cameras)} camera configurations")

            # 로드된 모든 카메라 정보 출력
            for cam in self.cameras:
                logger.info(f"Loaded camera: {cam.camera_id} - {cam.name} - enabled: {cam.enabled}")
            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False

    def save_config(self) -> bool:
        """
        Save configuration to file

        Returns:
            True if saved successfully
        """
        try:
            # Prepare data
            data = {
                'app': asdict(self.app_config),
                'cameras': [asdict(camera) for camera in self.cameras]
            }

            # Save to file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                if self.config_file.suffix == '.yaml' or self.config_file.suffix == '.yml':
                    # YAML 포맷 개선: 주석은 유지되지 않지만 가독성 향상
                    yaml.dump(
                        data,
                        f,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                        indent=2
                    )
                else:
                    json.dump(data, f, indent=2)

            logger.info(f"Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def create_default_config(self):
        """Create default configuration file (only if not exists)"""
        # 파일이 이미 있으면 덮어쓰지 않음
        if self.config_file.exists():
            logger.warning(f"Config file already exists: {self.config_file}. Skipping creation.")
            return

        logger.info("Creating default configuration...")

        # Default cameras for testing
        self.cameras = [
            CameraConfigData(
                camera_id="cam_01",
                name="Main Camera",
                rtsp_url="rtsp://admin:password@192.168.0.131:554/stream",
                enabled=True,
                recording_enabled=False
            )
        ]

        # Save default config
        self.save_config()
        logger.info(f"Default configuration created at {self.config_file}")

    def add_camera(self, camera: CameraConfigData) -> bool:
        """
        Add new camera configuration

        Args:
            camera: Camera configuration

        Returns:
            True if added successfully
        """
        # Check for duplicate ID
        if any(c.camera_id == camera.camera_id for c in self.cameras):
            logger.error(f"Camera with ID {camera.camera_id} already exists")
            return False

        self.cameras.append(camera)
        logger.info(f"Added camera: {camera.name} ({camera.camera_id})")
        return True

    def remove_camera(self, camera_id: str) -> bool:
        """
        Remove camera configuration

        Args:
            camera_id: Camera ID to remove

        Returns:
            True if removed successfully
        """
        initial_count = len(self.cameras)
        self.cameras = [c for c in self.cameras if c.camera_id != camera_id]

        if len(self.cameras) < initial_count:
            logger.info(f"Removed camera: {camera_id}")
            return True
        else:
            logger.warning(f"Camera not found: {camera_id}")
            return False

    def update_camera(self, camera_id: str, **kwargs) -> bool:
        """
        Update camera configuration

        Args:
            camera_id: Camera ID to update
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        for camera in self.cameras:
            if camera.camera_id == camera_id:
                for key, value in kwargs.items():
                    if hasattr(camera, key):
                        setattr(camera, key, value)
                logger.info(f"Updated camera: {camera_id}")
                return True

        logger.warning(f"Camera not found: {camera_id}")
        return False

    def get_camera(self, camera_id: str) -> Optional[CameraConfigData]:
        """
        Get camera configuration

        Args:
            camera_id: Camera ID

        Returns:
            Camera configuration or None
        """
        for camera in self.cameras:
            if camera.camera_id == camera_id:
                return camera
        return None

    def get_enabled_cameras(self) -> List[CameraConfigData]:
        """
        Get list of enabled cameras

        Returns:
            List of enabled camera configurations
        """
        return [c for c in self.cameras if c.enabled]

    def get_all_cameras(self) -> List[CameraConfigData]:
        """
        Get list of all cameras

        Returns:
            List of all camera configurations
        """
        return self.cameras

    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration

        Returns:
            Logging configuration dictionary
        """
        return self.logging_config

    def export_config(self, file_path: str) -> bool:
        """
        Export configuration to file

        Args:
            file_path: Export file path

        Returns:
            True if exported successfully
        """
        try:
            data = {
                'app': asdict(self.app_config),
                'cameras': [asdict(camera) for camera in self.cameras]
            }

            path = Path(file_path)
            with open(path, 'w') as f:
                if path.suffix == '.yaml' or path.suffix == '.yml':
                    yaml.dump(data, f, default_flow_style=False)
                else:
                    json.dump(data, f, indent=2)

            logger.info(f"Configuration exported to {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """
        Import configuration from file

        Args:
            file_path: Import file path

        Returns:
            True if imported successfully
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"Import file not found: {path}")
                return False

            with open(path, 'r') as f:
                if path.suffix == '.yaml' or path.suffix == '.yml':
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            # Validate and load data
            if 'cameras' in data:
                self.cameras = []
                for camera_data in data['cameras']:
                    camera = CameraConfigData(**camera_data)
                    self.cameras.append(camera)

            if 'app' in data:
                self.app_config = AppConfig(**data['app'])

            logger.info(f"Configuration imported from {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False