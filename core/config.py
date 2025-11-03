"""
Configuration Manager
Handles application configuration and camera settings
"""

import json
import yaml
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from loguru import logger


@dataclass
class AppConfig:
    """Application configuration"""
    app_name: str = "IT_RNVR"
    version: str = "1.0.0"


@dataclass
class UIConfig:
    """UI configuration"""
    theme: str = "dark"  # dark, light
    show_status_bar: bool = True
    fullscreen_on_start: bool = False
    fullscreen_auto_hide_enabled: bool = True  # 전체화면 자동 UI 숨김 활성화
    fullscreen_auto_hide_delay_seconds: int = 10  # 자동 UI 숨김 지연 시간 (초)
    window_state: Dict[str, int] = field(default_factory=lambda: {
        "width": 1920,
        "height": 1080,
        "x": 0,
        "y": 0
    })
    dock_state: Dict[str, bool] = field(default_factory=lambda: {
        "camera_visible": True,
        "recording_visible": True,
        "playback_visible": False
    })


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
    streaming_enabled_start: bool = False
    recording_enabled_start: bool = False
    motion_detection: bool = False
    ptz_type: Optional[str] = None  # PTZ 카메라 타입 (예: "HIK", "ONVIF")
    ptz_port: Optional[str] = None  # PTZ 제어 포트
    ptz_channel: Optional[str] = None  # PTZ 채널 번호


class ConfigManager:
    """
    Singleton class for managing application and camera configurations

    Usage:
        config_manager = ConfigManager.get_instance()
        # or
        config_manager = ConfigManager()  # Also returns singleton instance
    """
    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls, *_args, **_kwargs):
        """
        Create or return singleton instance
        """
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file: Optional[str] = None, auto_save: bool = False):
        """
        Initialize configuration manager (only once for singleton)

        Args:
            config_file: Path to configuration file (default: IT_RNVR.json)
            auto_save: Automatically save config on changes (default: False for safety)
        """
        # 이미 초기화되었으면 다시 초기화하지 않음
        if ConfigManager._initialized:
            return

        self.config_file = Path(config_file) if config_file else Path("IT_RNVR.json")
        self.app_config = AppConfig()
        self.ui_config = UIConfig()
        self.cameras: List[CameraConfigData] = []
        self.config: Dict[str, Any] = {}  # 전체 설정 저장 (storage 등)
        self.logging_config: Dict[str, Any] = {}  # 로깅 설정 저장
        self.streaming_config: Dict[str, Any] = {}  # 스트리밍 설정 저장
        self.recording_config: Dict[str, Any] = {}  # 녹화 설정 저장
        self.auto_save = auto_save  # 자동 저장 플래그

        # Load configuration
        self.load_config()

        # 초기화 완료 플래그 설정
        ConfigManager._initialized = True
        logger.info("ConfigManager singleton instance initialized")

    @classmethod
    def get_instance(cls, config_file: Optional[str] = None, auto_save: bool = False) -> 'ConfigManager':
        """
        Get singleton instance of ConfigManager

        Args:
            config_file: Path to configuration file (only used on first call)
            auto_save: Automatically save config on changes (only used on first call)

        Returns:
            ConfigManager singleton instance
        """
        if cls._instance is None:
            cls._instance = ConfigManager(config_file=config_file, auto_save=auto_save)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Reset singleton instance (mainly for testing)
        """
        cls._instance = None
        cls._initialized = False
        logger.debug("ConfigManager singleton instance reset")

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

            # 전체 설정 저장
            self.config = data

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

            # Load UI configuration
            if 'ui' in data:
                ui_data = data['ui']
                self.ui_config = UIConfig(**ui_data)
                logger.debug(f"Loaded UI configuration: theme={self.ui_config.theme}")
            else:
                logger.debug("No 'ui' section found in configuration, using defaults")
                self.ui_config = UIConfig()

            # Load streaming configuration
            if 'streaming' in data:
                self.streaming_config = data['streaming']
                logger.debug(f"Loaded streaming configuration: {self.streaming_config.keys()}")
            else:
                logger.debug("No 'streaming' section found in configuration, using defaults")
                self.streaming_config = {}

            # Load recording configuration
            if 'recording' in data:
                self.recording_config = data['recording']
                logger.debug(f"Loaded recording configuration: {self.recording_config.keys()}")
            else:
                logger.debug("No 'recording' section found in configuration, using defaults")
                self.recording_config = {}

            logger.info(f"Configuration loaded from {self.config_file}")
            logger.info(f"Loaded {len(self.cameras)} camera configurations")

            # 로드된 모든 카메라 정보 출력
            for cam in self.cameras:
                logger.info(f"Loaded camera: {cam.camera_id} - {cam.name} - enabled: {cam.enabled}")
            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False

    def save_config(self, save_ui: bool = False) -> bool:
        """
        Save configuration to file

        Args:
            save_ui: Include UI configuration (default: False to preserve YAML comments)

        Returns:
            True if saved successfully
        """
        try:
            # self.config에 저장된 전체 설정을 기반으로 시작
            # 이렇게 하면 기존의 모든 섹션이 보존됨
            data = self.config.copy()

            # app과 cameras는 항상 최신 상태로 업데이트
            data['app'] = asdict(self.app_config)
            data['cameras'] = [asdict(camera) for camera in self.cameras]

            # UI 설정 포함 여부
            if save_ui:
                data['ui'] = asdict(self.ui_config)

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
                    json.dump(data, f, indent=2, ensure_ascii=False)

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
                streaming_enabled_start=False,
                recording_enabled_start=False
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

    def get_streaming_config(self) -> Dict[str, Any]:
        """
        Get streaming configuration

        Returns:
            Streaming configuration dictionary
        """
        return self.streaming_config

    def get_recording_config(self) -> Dict[str, Any]:
        """
        Get recording configuration

        Returns:
            Recording configuration dictionary
        """
        return self.recording_config

    def get_default_layout(self) -> tuple:
        """
        Get default grid layout from streaming configuration

        Returns:
            Tuple of (rows, cols) for grid layout. Defaults to (1, 1)
        """
        layout_str = self.streaming_config.get("default_layout", "1x1")
        try:
            rows, cols = map(int, layout_str.split('x'))
            # Validate layout (max 4x4)
            if rows < 1 or rows > 4 or cols < 1 or cols > 4:
                logger.warning(f"Invalid layout '{layout_str}', using default 1x1")
                return (1, 1)
            return (rows, cols)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse layout '{layout_str}': {e}, using default 1x1")
            return (1, 1)

    def save_ui_config(self) -> bool:
        """
        Save only UI configuration to JSON file
        JSON 파일에서 ui 섹션만 부분 업데이트

        Returns:
            True if saved successfully
        """
        try:
            if not self.config_file.exists():
                logger.error(f"Config file not found: {self.config_file}")
                return False

            # 기존 JSON 파일 로드
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # UI 설정만 업데이트
            data['ui'] = asdict(self.ui_config)

            # JSON 파일에 저장 (들여쓰기 2칸, 가독성 좋게)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"UI configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save UI configuration: {e}")
            return False

    def update_ui_window_state(self, x: int, y: int, width: int, height: int):
        """
        Update window state in UI configuration

        Args:
            x: Window X position
            y: Window Y position
            width: Window width
            height: Window height
        """
        self.ui_config.window_state = {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        logger.debug(f"Updated window state: x={x}, y={y}, w={width}, h={height}")

    def update_ui_dock_state(self, camera_visible: bool, recording_visible: bool, playback_visible: bool):
        """
        Update dock visibility state in UI configuration

        Args:
            camera_visible: Camera dock visibility
            recording_visible: Recording dock visibility
            playback_visible: Playback dock visibility
        """
        self.ui_config.dock_state = {
            "camera_visible": camera_visible,
            "recording_visible": recording_visible,
            "playback_visible": playback_visible
        }
        logger.debug(f"Updated dock state: camera={camera_visible}, recording={recording_visible}, playback={playback_visible}")

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