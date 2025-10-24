"""
NVR Core Module

이 모듈은 NVR 시스템의 핵심 비즈니스 로직과 도메인 모델을 포함합니다.

Modules:
    - models: 도메인 엔티티 및 데이터 모델
    - enums: 시스템 전체에서 사용되는 열거형
    - events: 이벤트 시스템 및 이벤트 클래스
    - exceptions: 커스텀 예외 클래스
    - services: 비즈니스 로직 서비스
"""

from .models import Camera, Recording, StreamStatus
from .enums import CameraStatus, RecordingStatus, PipelineMode
from .exceptions import NVRException, CameraConnectionError, RecordingError, PipelineError

__all__ = [
    'Camera',
    'Recording',
    'StreamStatus',
    'CameraStatus',
    'RecordingStatus',
    'PipelineMode',
    'NVRException',
    'CameraConnectionError',
    'RecordingError',
    'PipelineError'
]