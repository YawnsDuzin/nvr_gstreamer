"""
Configuration Manager
SQLite DB 기반 설정 관리
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from loguru import logger

from core.db_manager import DBManager


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
    video_transform: Optional[Dict[str, Any]] = None  # 영상 변환 설정


class ConfigManager:
    """
    Singleton class for managing application and camera configurations (DB-based)

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

    def __init__(self, db_path: str = "IT_RNVR.db"):
        """
        Initialize configuration manager (only once for singleton)

        Args:
            db_path: Path to database file (default: IT_RNVR.db)
        """
        # 이미 초기화되었으면 다시 초기화하지 않음
        if ConfigManager._initialized:
            return

        self.db_path = db_path
        self.db_manager = DBManager(db_path)

        # 기존 속성 초기화 (호환성)
        self.app_config = AppConfig()
        self.ui_config = UIConfig()
        self.cameras: List[CameraConfigData] = []
        self.config: Dict[str, Any] = {}  # 전체 설정 저장 (storage 등)
        self.logging_config: Dict[str, Any] = {}  # 로깅 설정 저장
        self.streaming_config: Dict[str, Any] = {}  # 스트리밍 설정 저장
        self.recording_config: Dict[str, Any] = {}  # 녹화 설정 저장

        # DB에서 설정 로드
        self.load_config()

        # 초기화 완료 플래그 설정
        ConfigManager._initialized = True
        logger.info(f"ConfigManager singleton instance initialized (DB: {db_path})")

    @classmethod
    def get_instance(cls, db_path: str = "IT_RNVR.db") -> 'ConfigManager':
        """
        Get singleton instance of ConfigManager

        Args:
            db_path: Path to database file (only used on first call)

        Returns:
            ConfigManager singleton instance
        """
        if cls._instance is None:
            cls._instance = ConfigManager(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Reset singleton instance (mainly for testing)
        """
        if cls._instance and hasattr(cls._instance, 'db_manager'):
            cls._instance.db_manager.close()
        cls._instance = None
        cls._initialized = False
        logger.debug("ConfigManager singleton instance reset")

    def load_config(self) -> bool:
        """
        DB에서 설정 로드

        Returns:
            True if loaded successfully
        """
        try:
            # 전체 설정을 dict 형태로 메모리 캐시
            self.config = {
                "app": self.db_manager.get_app_config(),
                "ui": self.db_manager.get_ui_config(),
                "streaming": self.db_manager.get_streaming_config(),
                "cameras": self.db_manager.get_cameras(),
                "recording": self.db_manager.get_recording_config(),
                "storage": self.db_manager.get_storage_config(),
                "backup": self.db_manager.get_backup_config(),
                "menu_keys": self.db_manager.get_menu_keys(),
                "ptz_keys": self.db_manager.get_ptz_keys(),
                "logging": self.db_manager.get_logging_config(),
                "performance": self.db_manager.get_performance_config(),
            }

            # 기존 코드 호환을 위해 개별 속성도 유지
            self.app_config = AppConfig(**self.config["app"])
            self.ui_config = UIConfig(**self.config["ui"])
            self.cameras = [CameraConfigData(**cam) for cam in self.config["cameras"]]
            self.logging_config = self.config["logging"]
            self.streaming_config = self.config["streaming"]
            self.recording_config = self.config["recording"]

            logger.info("설정이 DB에서 로드되었습니다")
            logger.info(f"로드된 카메라: {len(self.cameras)}대")

            # 로드된 모든 카메라 정보 출력
            for cam in self.cameras:
                logger.info(f"카메라 로드: {cam.camera_id} - {cam.name} - enabled: {cam.enabled}")

            return True

        except Exception as e:
            logger.error(f"DB 설정 로드 실패: {e}")
            return False

    def save_config(self, save_ui: bool = False) -> bool:
        """
        설정을 DB에 저장 (모든 섹션 포함)

        Args:
            save_ui: Include UI configuration (default: False)

        Returns:
            True if saved successfully
        """
        try:
            # 트랜잭션 없이 개별 저장 (각 save_* 메서드가 자체 커밋)
            # app 저장 (self.app_config 사용)
            logger.debug("Saving app config...")
            self.db_manager.save_app_config(asdict(self.app_config))

            # cameras 저장 (config dict에서 가져옴 - UI에서 업데이트된 데이터)
            if "cameras" in self.config:
                logger.debug("Saving cameras...")
                self.db_manager.save_cameras(self.config["cameras"])
            else:
                # fallback: self.cameras 사용
                logger.debug("Saving cameras (fallback)...")
                self.db_manager.save_cameras([asdict(cam) for cam in self.cameras])

            # UI 설정 저장 여부
            if save_ui:
                logger.debug("Saving UI config...")
                self.db_manager.save_ui_config(asdict(self.ui_config))

            # 모든 섹션 저장 (config dict에서 가져옴)
            if "streaming" in self.config:
                logger.debug("Saving streaming config...")
                self.db_manager.save_streaming_config(self.config["streaming"])

            if "recording" in self.config:
                logger.debug("Saving recording config...")
                self.db_manager.save_recording_config(self.config["recording"])

            if "storage" in self.config:
                logger.debug("Saving storage config...")
                self.db_manager.save_storage_config(self.config["storage"])

            if "backup" in self.config:
                logger.debug("Saving backup config...")
                self.db_manager.save_backup_config(self.config["backup"])

            if "menu_keys" in self.config:
                logger.debug("Saving menu_keys...")
                self.db_manager.save_menu_keys(self.config["menu_keys"])

            if "ptz_keys" in self.config:
                logger.debug("Saving ptz_keys...")
                self.db_manager.save_ptz_keys(self.config["ptz_keys"])

            if "logging" in self.config:
                logger.debug("Saving logging config...")
                self.db_manager.save_logging_config(self.config["logging"])

            if "performance" in self.config:
                logger.debug("Saving performance config...")
                self.db_manager.save_performance_config(self.config["performance"])

            # DB 저장 후 메모리 속성 동기화 (self.cameras, self.app_config 등을 config dict와 일치시킴)
            if "cameras" in self.config:
                # config["cameras"]의 데이터를 self.cameras에 역동기화
                self.cameras = [CameraConfigData(**cam) for cam in self.config["cameras"]]
                logger.debug(f"Synchronized self.cameras: {len(self.cameras)} cameras")

            logger.info("설정이 DB에 저장되었습니다")
            return True

        except Exception as e:
            logger.error(f"DB 설정 저장 실패: {e}")
            return False

    def save_ui_config(self) -> bool:
        """
        UI 설정만 DB에 저장

        Returns:
            True if saved successfully
        """
        try:
            self.db_manager.save_ui_config(asdict(self.ui_config))

            # config dict 업데이트
            self.config["ui"] = asdict(self.ui_config)

            logger.debug("UI 설정이 DB에 저장되었습니다")
            return True
        except Exception as e:
            logger.error(f"UI 설정 저장 실패: {e}")
            return False

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
