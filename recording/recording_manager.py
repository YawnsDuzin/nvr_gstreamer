"""
녹화 관리자
연속 녹화 기능을 관리하는 모듈
"""

import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass
from loguru import logger

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# GStreamer 초기화
Gst.init(None)


class RecordingStatus(Enum):
    """녹화 상태"""
    STOPPED = "stopped"
    RECORDING = "recording"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class RecordingConfig:
    """녹화 설정"""
    camera_id: str
    camera_name: str
    output_dir: str = "recordings"
    file_duration: int = 600  # 10분 단위로 파일 분할 (초)
    file_format: str = "mp4"  # mp4, mkv, avi
    video_codec: str = "h264"  # h264, h265
    enable_audio: bool = False
    max_file_size: int = 1024  # MB 단위
    retention_days: int = 7  # 보관 기간 (일)


class RecordingPipeline:
    """개별 카메라 녹화 파이프라인"""

    def __init__(self, rtsp_url: str, config: RecordingConfig):
        """
        녹화 파이프라인 초기화

        Args:
            rtsp_url: RTSP 스트림 URL
            config: 녹화 설정
        """
        self.rtsp_url = rtsp_url
        self.config = config
        self.pipeline = None
        self.bus = None
        self.status = RecordingStatus.STOPPED
        self.current_filename = None
        self.start_time = None
        self._thread = None
        self._main_loop = None
        self._rotation_timer = None  # 파일 회전 타이머 추적

        # 녹화 디렉토리 생성
        self._create_recording_dir()

    def _create_recording_dir(self):
        """녹화 디렉토리 생성"""
        # 카메라별 디렉토리 생성
        camera_dir = Path(self.config.output_dir) / self.config.camera_id
        camera_dir.mkdir(parents=True, exist_ok=True)

        # 날짜별 디렉토리
        date_dir = camera_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True)

        self.recording_path = date_dir
        logger.info(f"Recording directory: {self.recording_path}")

    def _generate_filename(self) -> str:
        """녹화 파일명 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.camera_id}_{timestamp}.{self.config.file_format}"
        return str(self.recording_path / filename)

    def create_pipeline(self) -> bool:
        """
        녹화 파이프라인 생성

        Returns:
            성공 여부
        """
        try:
            self.current_filename = self._generate_filename()

            # 파이프라인 문자열 생성
            if self.config.file_format == "mp4":
                # MP4 컨테이너 사용
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} protocols=tcp latency=200 ! "
                    "queue ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    "mp4mux name=mux ! "
                    f"filesink location={self.current_filename}"
                )
            elif self.config.file_format == "mkv":
                # MKV 컨테이너 사용
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} protocols=tcp latency=200 ! "
                    "queue ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    "matroskamux name=mux ! "
                    f"filesink location={self.current_filename}"
                )
            else:
                # AVI 컨테이너 사용
                pipeline_str = (
                    f"rtspsrc location={self.rtsp_url} protocols=tcp latency=200 ! "
                    "queue ! "
                    "rtph264depay ! "
                    "h264parse ! "
                    "avimux name=mux ! "
                    f"filesink location={self.current_filename}"
                )

            logger.debug(f"Creating recording pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            logger.info(f"Recording pipeline created for {self.config.camera_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create recording pipeline: {e}")
            self.status = RecordingStatus.ERROR
            return False

    def start_recording(self) -> bool:
        """
        녹화 시작

        Returns:
            성공 여부
        """
        if self.status == RecordingStatus.RECORDING:
            logger.warning(f"Already recording: {self.config.camera_name}")
            return False

        # 파이프라인 생성
        if not self.create_pipeline():
            return False

        try:
            # 파이프라인 시작
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error(f"Failed to start recording pipeline: {self.config.camera_name}")
                return False

            self.status = RecordingStatus.RECORDING
            self.start_time = time.time()

            # 메인 루프 시작
            self._main_loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._run_main_loop)
            self._thread.daemon = True
            self._thread.start()

            logger.success(f"Recording started: {self.current_filename}")

            # 파일 분할 타이머 시작 (기존 타이머가 있으면 정지)
            self._stop_rotation_timer()
            self._schedule_file_rotation()

            return True

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.status = RecordingStatus.ERROR
            return False

    def stop_recording(self):
        """녹화 정지"""
        if self.status != RecordingStatus.RECORDING:
            return

        logger.info(f"Stopping recording: {self.config.camera_name}")

        # 먼저 상태를 STOPPED로 변경 (타이머 중지를 위해)
        self.status = RecordingStatus.STOPPED
        
        # 파일 회전 타이머 정지
        self._stop_rotation_timer()

        if self.pipeline:
            # EOS 신호 보내기
            self.pipeline.send_event(Gst.Event.new_eos())
            # 잠시 대기
            time.sleep(0.5)
            # 파이프라인 정지
            self.pipeline.set_state(Gst.State.NULL)

        # 메인 루프 정지
        if self._main_loop:
            self._main_loop.quit()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info(f"Recording stopped: {self.current_filename}")

    def pause_recording(self):
        """녹화 일시정지"""
        if self.status == RecordingStatus.RECORDING and self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.status = RecordingStatus.PAUSED
            logger.info(f"Recording paused: {self.config.camera_name}")

    def resume_recording(self):
        """녹화 재개"""
        if self.status == RecordingStatus.PAUSED and self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.status = RecordingStatus.RECORDING
            logger.info(f"Recording resumed: {self.config.camera_name}")

    def _run_main_loop(self):
        """메인 루프 실행"""
        try:
            self._main_loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.EOS:
            logger.info("End of stream reached")
            self._handle_eos()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Recording error: {err}, {debug}")
            self.status = RecordingStatus.ERROR
            self.stop_recording()

    def _handle_eos(self):
        """EOS 처리 - 새 파일로 전환"""
        logger.info("Handling EOS - rotating file")

        # 현재 파이프라인 정지
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        # 메인 루프 정지
        if self._main_loop:
            self._main_loop.quit()

        # 새 파일로 재시작
        if self.status == RecordingStatus.RECORDING:
            time.sleep(0.5)  # 짧은 대기
            self.create_pipeline()
            self.pipeline.set_state(Gst.State.PLAYING)

            # 새 메인 루프 시작
            self._main_loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._run_main_loop)
            self._thread.daemon = True
            self._thread.start()

    def _schedule_file_rotation(self):
        """파일 분할 스케줄링"""
        def rotate_file():
            if self.status == RecordingStatus.RECORDING:
                elapsed = time.time() - self.start_time
                if elapsed >= self.config.file_duration:
                    logger.info(f"Rotating recording file: {self.config.camera_name}")
                    # EOS 이벤트 전송하여 파일 회전
                    if self.pipeline:
                        self.pipeline.send_event(Gst.Event.new_eos())
                    self.start_time = time.time()

                # 다음 체크 스케줄 (녹화 중일 때만)
                if self.status == RecordingStatus.RECORDING:
                    self._rotation_timer = threading.Timer(10.0, rotate_file)  # 10초마다 체크
                    self._rotation_timer.daemon = True
                    self._rotation_timer.start()

        # 첫 체크 스케줄
        self._rotation_timer = threading.Timer(10.0, rotate_file)
        self._rotation_timer.daemon = True
        self._rotation_timer.start()
        
    def _stop_rotation_timer(self):
        """파일 회전 타이머 정지"""
        if self._rotation_timer:
            self._rotation_timer.cancel()
            self._rotation_timer = None
            logger.debug(f"File rotation timer stopped for {self.config.camera_name}")

    def get_recording_info(self) -> Dict:
        """녹화 정보 반환"""
        info = {
            "camera_id": self.config.camera_id,
            "camera_name": self.config.camera_name,
            "status": self.status.value,
            "current_file": self.current_filename,
            "recording_path": str(self.recording_path)
        }

        if self.start_time and self.status == RecordingStatus.RECORDING:
            info["duration"] = int(time.time() - self.start_time)
            info["file_size"] = self._get_file_size()

        return info

    def _get_file_size(self) -> int:
        """현재 녹화 파일 크기 반환 (bytes)"""
        if self.current_filename and os.path.exists(self.current_filename):
            return os.path.getsize(self.current_filename)
        return 0


class RecordingManager:
    """전체 녹화 관리자"""

    def __init__(self, output_dir: str = "recordings"):
        """
        녹화 관리자 초기화

        Args:
            output_dir: 녹화 파일 저장 디렉토리
        """
        self.output_dir = output_dir
        self.recording_pipelines: Dict[str, RecordingPipeline] = {}
        self._ensure_output_dir()

        logger.info(f"Recording manager initialized: {self.output_dir}")

    def _ensure_output_dir(self):
        """출력 디렉토리 확인 및 생성"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def start_recording(self, camera_id: str, camera_name: str, rtsp_url: str,
                       file_format: str = "mp4", file_duration: int = 600) -> bool:
        """
        카메라 녹화 시작

        Args:
            camera_id: 카메라 ID
            camera_name: 카메라 이름
            rtsp_url: RTSP URL
            file_format: 파일 포맷
            file_duration: 파일 분할 시간 (초)

        Returns:
            성공 여부
        """
        # 이미 녹화 중인지 확인
        if camera_id in self.recording_pipelines:
            pipeline = self.recording_pipelines[camera_id]
            if pipeline.status == RecordingStatus.RECORDING:
                logger.warning(f"Camera {camera_id} is already recording")
                return False

        # 녹화 설정 생성
        config = RecordingConfig(
            camera_id=camera_id,
            camera_name=camera_name,
            output_dir=self.output_dir,
            file_format=file_format,
            file_duration=file_duration
        )

        # 녹화 파이프라인 생성
        pipeline = RecordingPipeline(rtsp_url, config)

        # 녹화 시작
        if pipeline.start_recording():
            self.recording_pipelines[camera_id] = pipeline
            logger.success(f"Started recording for {camera_name}")
            return True
        else:
            logger.error(f"Failed to start recording for {camera_name}")
            return False

    def stop_recording(self, camera_id: str) -> bool:
        """
        카메라 녹화 정지

        Args:
            camera_id: 카메라 ID

        Returns:
            성공 여부
        """
        if camera_id not in self.recording_pipelines:
            logger.warning(f"Camera {camera_id} is not recording")
            return False

        pipeline = self.recording_pipelines[camera_id]
        pipeline.stop_recording()

        # 파이프라인 제거
        del self.recording_pipelines[camera_id]

        logger.info(f"Stopped recording for camera {camera_id}")
        return True

    def stop_all_recordings(self):
        """모든 녹화 정지"""
        logger.info("Stopping all recordings...")

        for camera_id in list(self.recording_pipelines.keys()):
            self.stop_recording(camera_id)

        logger.info("All recordings stopped")

    def pause_recording(self, camera_id: str) -> bool:
        """녹화 일시정지"""
        if camera_id in self.recording_pipelines:
            self.recording_pipelines[camera_id].pause_recording()
            return True
        return False

    def resume_recording(self, camera_id: str) -> bool:
        """녹화 재개"""
        if camera_id in self.recording_pipelines:
            self.recording_pipelines[camera_id].resume_recording()
            return True
        return False

    def get_recording_status(self, camera_id: str) -> RecordingStatus:
        """녹화 상태 반환"""
        if camera_id in self.recording_pipelines:
            return self.recording_pipelines[camera_id].status
        return RecordingStatus.STOPPED

    def get_all_recording_info(self) -> Dict:
        """모든 녹화 정보 반환"""
        info = {}
        for camera_id, pipeline in self.recording_pipelines.items():
            info[camera_id] = pipeline.get_recording_info()
        return info

    def is_recording(self, camera_id: str) -> bool:
        """특정 카메라가 녹화 중인지 확인"""
        return (camera_id in self.recording_pipelines and
                self.recording_pipelines[camera_id].status == RecordingStatus.RECORDING)

    def cleanup_old_recordings(self, retention_days: int = 7):
        """오래된 녹화 파일 정리"""
        logger.info(f"Cleaning up recordings older than {retention_days} days")

        cutoff_time = time.time() - (retention_days * 24 * 3600)
        recordings_dir = Path(self.output_dir)

        deleted_count = 0
        deleted_size = 0

        for camera_dir in recordings_dir.iterdir():
            if camera_dir.is_dir():
                for date_dir in camera_dir.iterdir():
                    if date_dir.is_dir():
                        for file_path in date_dir.glob("*.*"):
                            if file_path.stat().st_mtime < cutoff_time:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                deleted_count += 1
                                deleted_size += file_size

                        # 빈 날짜 디렉토리 삭제
                        if not any(date_dir.iterdir()):
                            date_dir.rmdir()

        logger.info(f"Deleted {deleted_count} files, freed {deleted_size / (1024*1024):.2f} MB")

    def get_disk_usage(self) -> Dict:
        """디스크 사용량 정보 반환"""
        recordings_dir = Path(self.output_dir)
        total_size = 0
        file_count = 0

        for path in recordings_dir.rglob("*.*"):
            if path.is_file():
                total_size += path.stat().st_size
                file_count += 1

        return {
            "total_size_mb": total_size / (1024 * 1024),
            "file_count": file_count,
            "recording_dir": str(recordings_dir)
        }