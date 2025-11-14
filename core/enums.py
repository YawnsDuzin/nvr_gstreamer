"""
NVR 시스템 전체에서 사용되는 열거형 정의
"""
from enum import Enum, auto


class CameraStatus(Enum):
    """카메라 연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    RECORDING = "recording"
    ERROR = "error"
    RECONNECTING = "reconnecting"

    @staticmethod
    def get_status_color(status: 'CameraStatus'):
        """
        상태에 따른 색상 반환

        Returns:
            tuple: (icon, color_hex, color_name)
                - 🟢 녹색 (#00ff00): 정상 연결 및 스트리밍 중
                - 🟡 노란색 (#ffff00): 연결 시도 중
                - 🔴 빨간색 (#ff0000): 연결 실패 또는 오류
                - 🔵 파란색 (#0099ff): 재연결 시도 중
                - ⚫ 회색 (#646464): 비활성화
        """
        color_map = {
            CameraStatus.CONNECTED: ("🟢", "#00ff00", "green"),
            CameraStatus.STREAMING: ("🟢", "#00ff00", "green"),
            CameraStatus.CONNECTING: ("🟡", "#ffff00", "yellow"),
            CameraStatus.ERROR: ("🔴", "#ff0000", "red"),
            CameraStatus.RECONNECTING: ("🔵", "#0099ff", "blue"),
            CameraStatus.DISCONNECTED: ("⚪", "#ffffff", "white"),
        }
        return color_map.get(status, ("⚪", "#ffffff", "white"))


class RecordingStatus(Enum):
    """녹화 상태"""
    IDLE = "idle"
    PREPARING = "preparing"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

    @staticmethod
    def get_status_color(status: 'RecordingStatus'):
        """
        녹화 상태에 따른 색상 반환

        Returns:
            tuple: (icon, color_hex, color_name)
                - 🔴 빨간색 (#ff0000): 녹화 중
                - 🟡 노란색 (#ffff00): 준비 중 또는 중지 중
                - 🔵 파란색 (#0099ff): 일시 정지
                - 🟠 주황색 (#ff9900): 오류
                - ⚪ 흰색 (#ffffff): 대기 중
        """
        color_map = {
            RecordingStatus.RECORDING: ("🔴", "#ff0000", "red"),
            RecordingStatus.PREPARING: ("🟡", "#ffff00", "yellow"),
            RecordingStatus.STOPPING: ("🟡", "#ffff00", "yellow"),
            RecordingStatus.PAUSED: ("🔵", "#0099ff", "blue"),
            RecordingStatus.ERROR: ("🟠", "#ff9900", "orange"),
            RecordingStatus.IDLE: ("⚪", "#ffffff", "white"),
        }
        return color_map.get(status, ("⚪", "#ffffff", "white"))


class PipelineMode(Enum):
    """파이프라인 동작 모드"""
    STREAMING_ONLY = "streaming_only"
    RECORDING_ONLY = "recording_only"
    BOTH = "both"


class ErrorType(Enum):
    """에러 타입 분류"""
    RTSP_NETWORK = auto()          # RTSP 네트워크 끊김
    STORAGE_DISCONNECTED = auto()  # USB/HDD 분리
    DISK_FULL = auto()             # 디스크 공간 부족
    DECODER = auto()               # 디코더 에러
    VIDEO_SINK = auto()            # Video sink 에러
    RECORDING_BRANCH = auto()      # 녹화 브랜치 일반 에러
    STREAMING_BRANCH = auto()      # 스트리밍 브랜치 일반 에러
    UNKNOWN = auto()               # 알 수 없는 에러


class PlaybackState(Enum):
    """재생 상태"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    SEEKING = "seeking"
    ERROR = "error"


# 현재 사용되지 않음
class StreamQuality(Enum):
    """스트림 품질 설정"""
    LOW = "low"      # 480p
    MEDIUM = "medium"  # 720p
    HIGH = "high"     # 1080p
    ULTRA = "ultra"   # 4K


class FileFormat(Enum):
    """녹화 파일 형식"""
    MP4 = "mp4"
    MKV = "mkv"
    AVI = "avi"
    TS = "ts"


class AlertLevel(Enum):
    """시스템 경고 레벨"""
    NORMAL = "normal"      # 정상
    WARNING = "warning"    # 경고 (임계값 근접)
    CRITICAL = "critical"  # 위험 (임계값 초과)