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


class RecordingStatus(Enum):
    """녹화 상태"""
    IDLE = "idle"
    PREPARING = "preparing"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


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