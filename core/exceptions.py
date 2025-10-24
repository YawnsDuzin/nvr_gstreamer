"""
NVR 시스템 커스텀 예외 클래스
"""


class NVRException(Exception):
    """NVR 시스템 기본 예외"""
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class CameraConnectionError(NVRException):
    """카메라 연결 실패"""
    def __init__(self, camera_id: str, message: str, error_code: str = "CAM_CONN_ERR"):
        super().__init__(message, error_code)
        self.camera_id = camera_id


class RecordingError(NVRException):
    """녹화 오류"""
    def __init__(self, camera_id: str, message: str, error_code: str = "REC_ERR"):
        super().__init__(message, error_code)
        self.camera_id = camera_id


class PipelineError(NVRException):
    """파이프라인 오류"""
    def __init__(self, pipeline_name: str, message: str, error_code: str = "PIPE_ERR"):
        super().__init__(message, error_code)
        self.pipeline_name = pipeline_name


class StorageError(NVRException):
    """스토리지 관련 오류"""
    def __init__(self, message: str, error_code: str = "STORAGE_ERR"):
        super().__init__(message, error_code)


class ConfigurationError(NVRException):
    """설정 관련 오류"""
    def __init__(self, message: str, error_code: str = "CONFIG_ERR"):
        super().__init__(message, error_code)