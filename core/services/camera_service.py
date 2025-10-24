"""
카메라 관련 비즈니스 로직 서비스
"""
from typing import Optional, List, Dict, Any, Callable
from loguru import logger
from datetime import datetime

from ..models import Camera, StreamStatus, Recording
from ..enums import CameraStatus, RecordingStatus, PipelineMode
from ..exceptions import CameraConnectionError, RecordingError


class CameraService:
    """카메라 관련 비즈니스 로직을 처리하는 서비스"""

    def __init__(self, config_manager):
        """
        Initialize camera service

        Args:
            config_manager: 설정 관리자 인스턴스
        """
        self.config_manager = config_manager
        self.camera_streams: Dict[str, Any] = {}  # camera_id -> stream object
        self.recordings: Dict[str, Recording] = {}  # camera_id -> Recording
        self._callbacks: Dict[str, List[Callable]] = {
            'camera_connected': [],
            'camera_disconnected': [],
            'recording_started': [],
            'recording_stopped': [],
            'error_occurred': []
        }

    def register_callback(self, event_type: str, callback: Callable):
        """이벤트 콜백 등록"""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
            logger.debug(f"Callback registered for event: {event_type}")

    def _trigger_callbacks(self, event_type: str, *args, **kwargs):
        """이벤트 콜백 트리거"""
        if event_type in self._callbacks:
            for callback in self._callbacks[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in callback for {event_type}: {e}")

    def connect_camera(self, camera_id: str, stream_object: Any = None) -> bool:
        """
        카메라 연결 및 자동 녹화 처리

        Args:
            camera_id: 카메라 ID
            stream_object: 카메라 스트림 객체 (Optional)

        Returns:
            bool: 연결 성공 여부
        """
        try:
            # 설정에서 카메라 정보 가져오기
            camera_config = self.config_manager.get_camera(camera_id)
            if not camera_config:
                raise CameraConnectionError(
                    camera_id,
                    f"Camera {camera_id} not found in configuration"
                )

            # Camera 도메인 객체 생성
            camera = Camera(
                camera_id=camera_config.camera_id,
                name=camera_config.name,
                rtsp_url=camera_config.rtsp_url,
                username=getattr(camera_config, 'username', None),
                password=getattr(camera_config, 'password', None),
                recording_enabled=camera_config.recording_enabled,
                status=CameraStatus.CONNECTING
            )

            # 스트림 객체 저장
            if stream_object:
                self.camera_streams[camera_id] = stream_object

            # 연결 성공 시 상태 업데이트
            camera.status = CameraStatus.CONNECTED

            # 자동 녹화 체크
            if camera.recording_enabled:
                logger.info(f"Auto-recording enabled for {camera.name} ({camera_id})")

                # 녹화 시작 로직
                if self._start_auto_recording(camera_id, stream_object):
                    camera.status = CameraStatus.RECORDING
                    logger.success(f"✓ Auto-recording started for {camera.name}")
                else:
                    logger.warning(f"Failed to start auto-recording for {camera.name}")

            # 콜백 트리거
            self._trigger_callbacks('camera_connected', camera_id, camera)

            return True

        except Exception as e:
            logger.error(f"Failed to connect camera {camera_id}: {e}")
            self._trigger_callbacks('error_occurred', camera_id, str(e))
            return False

    def _start_auto_recording(self, camera_id: str, stream_object: Any) -> bool:
        """
        자동 녹화 시작

        Args:
            camera_id: 카메라 ID
            stream_object: 스트림 객체

        Returns:
            bool: 녹화 시작 성공 여부
        """
        try:
            # Recording 도메인 객체 생성
            recording = Recording(
                recording_id=f"{camera_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                camera_id=camera_id,
                camera_name=self.config_manager.get_camera(camera_id).name,
                start_time=datetime.now(),
                status=RecordingStatus.PREPARING
            )

            # 스트림 객체가 있고 파이프라인이 있으면 녹화 시작
            if stream_object and hasattr(stream_object, 'gst_pipeline'):
                pipeline = stream_object.gst_pipeline

                # 녹화 모드 확인 및 설정
                if hasattr(pipeline, 'mode'):
                    if pipeline.mode != PipelineMode.BOTH:
                        # 녹화 모드로 전환
                        logger.info(f"Switching to BOTH mode for recording on {camera_id}")
                        if hasattr(pipeline, 'set_mode'):
                            pipeline.set_mode(PipelineMode.BOTH)

                # 녹화 시작
                if hasattr(pipeline, 'start_recording'):
                    if pipeline.start_recording():
                        recording.status = RecordingStatus.RECORDING
                        recording.file_path = getattr(pipeline, 'current_recording_file', '')
                        self.recordings[camera_id] = recording

                        # 콜백 트리거
                        self._trigger_callbacks('recording_started', camera_id, recording)
                        return True
                else:
                    logger.warning(f"Pipeline does not support recording for {camera_id}")
            else:
                logger.warning(f"No valid stream/pipeline for auto-recording on {camera_id}")

            recording.status = RecordingStatus.ERROR
            recording.error_message = "Failed to start recording"
            return False

        except Exception as e:
            logger.error(f"Error starting auto-recording for {camera_id}: {e}")
            return False

    def disconnect_camera(self, camera_id: str) -> bool:
        """
        카메라 연결 해제

        Args:
            camera_id: 카메라 ID

        Returns:
            bool: 연결 해제 성공 여부
        """
        try:
            # 녹화 중이면 먼저 중지
            if camera_id in self.recordings:
                self.stop_recording(camera_id)

            # 스트림 제거
            if camera_id in self.camera_streams:
                del self.camera_streams[camera_id]

            # 콜백 트리거
            self._trigger_callbacks('camera_disconnected', camera_id)

            logger.info(f"Camera {camera_id} disconnected")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting camera {camera_id}: {e}")
            return False

    def start_recording(self, camera_id: str) -> bool:
        """
        수동 녹화 시작

        Args:
            camera_id: 카메라 ID

        Returns:
            bool: 녹화 시작 성공 여부
        """
        stream_object = self.camera_streams.get(camera_id)
        if not stream_object:
            logger.error(f"No stream found for camera {camera_id}")
            return False

        return self._start_auto_recording(camera_id, stream_object)

    def stop_recording(self, camera_id: str) -> bool:
        """
        녹화 중지

        Args:
            camera_id: 카메라 ID

        Returns:
            bool: 녹화 중지 성공 여부
        """
        try:
            if camera_id not in self.recordings:
                logger.warning(f"No active recording for camera {camera_id}")
                return False

            recording = self.recordings[camera_id]

            # 스트림에서 녹화 중지
            stream_object = self.camera_streams.get(camera_id)
            if stream_object and hasattr(stream_object, 'gst_pipeline'):
                pipeline = stream_object.gst_pipeline
                if hasattr(pipeline, 'stop_recording'):
                    pipeline.stop_recording()

            # Recording 객체 업데이트
            recording.end_time = datetime.now()
            recording.duration_seconds = recording.calculate_duration()
            recording.status = RecordingStatus.IDLE

            # 녹화 제거
            del self.recordings[camera_id]

            # 콜백 트리거
            self._trigger_callbacks('recording_stopped', camera_id, recording)

            logger.info(f"Recording stopped for camera {camera_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping recording for {camera_id}: {e}")
            return False

    def get_camera_status(self, camera_id: str) -> Optional[StreamStatus]:
        """
        카메라 상태 조회

        Args:
            camera_id: 카메라 ID

        Returns:
            StreamStatus 객체 또는 None
        """
        stream_object = self.camera_streams.get(camera_id)
        if not stream_object:
            return None

        camera_config = self.config_manager.get_camera(camera_id)
        if not camera_config:
            return None

        # 상태 결정
        status = CameraStatus.DISCONNECTED
        if hasattr(stream_object, 'is_connected') and stream_object.is_connected():
            if camera_id in self.recordings:
                status = CameraStatus.RECORDING
            else:
                status = CameraStatus.STREAMING
        elif hasattr(stream_object, 'status'):
            # stream_object의 상태 사용
            stream_status = stream_object.status
            if hasattr(stream_status, 'value'):
                status = CameraStatus(stream_status.value)

        return StreamStatus(
            camera_id=camera_id,
            camera_name=camera_config.name,
            status=status,
            frames_received=getattr(stream_object, '_stats', {}).get('frames_received', 0),
            connection_time=getattr(stream_object, '_stats', {}).get('connection_time', 0),
            last_error=getattr(stream_object, '_stats', {}).get('last_error', None),
            reconnect_count=getattr(stream_object, '_reconnect_count', 0),
            last_frame_time=getattr(stream_object, '_last_frame_time', 0)
        )

    def get_all_camera_statuses(self) -> List[StreamStatus]:
        """
        모든 카메라 상태 조회

        Returns:
            StreamStatus 객체 리스트
        """
        statuses = []
        for camera_id in self.camera_streams.keys():
            status = self.get_camera_status(camera_id)
            if status:
                statuses.append(status)
        return statuses

    def is_recording(self, camera_id: str) -> bool:
        """
        녹화 중인지 확인

        Args:
            camera_id: 카메라 ID

        Returns:
            bool: 녹화 중 여부
        """
        return camera_id in self.recordings

    def get_recording_info(self, camera_id: str) -> Optional[Recording]:
        """
        녹화 정보 조회

        Args:
            camera_id: 카메라 ID

        Returns:
            Recording 객체 또는 None
        """
        return self.recordings.get(camera_id)