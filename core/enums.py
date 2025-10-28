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