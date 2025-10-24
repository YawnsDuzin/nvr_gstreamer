"""
NVR 시스템 도메인 모델 및 엔티티
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from .enums import CameraStatus, RecordingStatus


@dataclass
class Camera:
    """카메라 도메인 엔티티"""
    camera_id: str
    name: str
    rtsp_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    recording_enabled: bool = False
    use_hardware_decode: bool = False
    reconnect_attempts: int = 3
    reconnect_delay: int = 5
    status: CameraStatus = CameraStatus.DISCONNECTED

    def build_rtsp_url_with_auth(self) -> str:
        """인증 정보를 포함한 RTSP URL 생성"""
        if self.username and self.password:
            # Parse URL and insert credentials
            url_parts = self.rtsp_url.split("://")
            if len(url_parts) == 2:
                protocol = url_parts[0]
                rest = url_parts[1]
                return f"{protocol}://{self.username}:{self.password}@{rest}"
        return self.rtsp_url

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "rtsp_url": self.rtsp_url,
            "username": self.username,
            "password": self.password,
            "recording_enabled": self.recording_enabled,
            "use_hardware_decode": self.use_hardware_decode,
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_delay": self.reconnect_delay,
            "status": self.status.value
        }


@dataclass
class Recording:
    """녹화 세션 도메인 엔티티"""
    recording_id: str
    camera_id: str
    camera_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    file_path: str = ""
    file_size: int = 0
    duration_seconds: float = 0.0
    status: RecordingStatus = RecordingStatus.IDLE
    error_message: Optional[str] = None

    def is_active(self) -> bool:
        """녹화가 활성 상태인지 확인"""
        return self.status == RecordingStatus.RECORDING

    def calculate_duration(self) -> float:
        """녹화 시간 계산 (초)"""
        if self.start_time:
            end = self.end_time if self.end_time else datetime.now()
            return (end - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "recording_id": self.recording_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration_seconds": self.duration_seconds,
            "status": self.status.value,
            "error_message": self.error_message
        }


@dataclass
class StreamStatus:
    """스트림 상태 정보"""
    camera_id: str
    camera_name: str
    status: CameraStatus
    frames_received: int = 0
    connection_time: float = 0
    last_error: Optional[str] = None
    reconnect_count: int = 0
    last_frame_time: float = 0

    def get_uptime(self) -> float:
        """연결 시간 계산 (초)"""
        if self.status == CameraStatus.CONNECTED and self.connection_time > 0:
            from time import time
            return time() - self.connection_time
        return 0.0

    def is_healthy(self, timeout: float = 10.0) -> bool:
        """스트림 건강 상태 확인"""
        from time import time

        if self.status != CameraStatus.CONNECTED:
            return False

        # 프레임 수신 체크
        if self.last_frame_time > 0:
            time_since_last_frame = time() - self.last_frame_time
            if time_since_last_frame > timeout:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "status": self.status.value,
            "frames_received": self.frames_received,
            "connection_time": self.connection_time,
            "last_error": self.last_error,
            "reconnect_count": self.reconnect_count,
            "last_frame_time": self.last_frame_time,
            "uptime": self.get_uptime()
        }


@dataclass
class StorageInfo:
    """스토리지 정보"""
    total_space: int  # bytes
    used_space: int  # bytes
    free_space: int  # bytes
    recordings_count: int
    recordings_size: int  # bytes
    oldest_recording: Optional[datetime] = None
    newest_recording: Optional[datetime] = None

    @property
    def usage_percent(self) -> float:
        """사용률 계산"""
        if self.total_space > 0:
            return (self.used_space / self.total_space) * 100
        return 0.0

    @property
    def available_percent(self) -> float:
        """가용 공간 비율"""
        if self.total_space > 0:
            return (self.free_space / self.total_space) * 100
        return 0.0

    def needs_cleanup(self, threshold_percent: float = 90.0) -> bool:
        """정리 필요 여부"""
        return self.usage_percent >= threshold_percent


@dataclass
class SystemStatus:
    """시스템 전체 상태"""
    cameras_total: int = 0
    cameras_connected: int = 0
    cameras_recording: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    uptime_seconds: float = 0.0
    errors_count: int = 0
    warnings_count: int = 0

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "cameras": {
                "total": self.cameras_total,
                "connected": self.cameras_connected,
                "recording": self.cameras_recording
            },
            "resources": {
                "cpu_usage": self.cpu_usage,
                "memory_usage": self.memory_usage,
                "disk_usage": self.disk_usage
            },
            "system": {
                "uptime_seconds": self.uptime_seconds,
                "errors_count": self.errors_count,
                "warnings_count": self.warnings_count
            }
        }