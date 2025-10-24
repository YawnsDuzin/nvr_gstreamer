"""
재생 관리자
녹화된 파일을 재생하는 기능 관리
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from loguru import logger

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo

from utils.gstreamer_utils import get_video_sink

# Core imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.enums import PlaybackState

# Note: GStreamer는 main.py에서 초기화됨


@dataclass
class RecordingFile:
    """녹화 파일 정보"""
    file_path: str
    camera_id: str
    camera_name: str
    timestamp: datetime
    duration: float  # seconds
    file_size: int  # bytes

    @property
    def file_name(self) -> str:
        return Path(self.file_path).name

    @property
    def formatted_size(self) -> str:
        """포맷된 파일 크기"""
        size_mb = self.file_size / (1024 * 1024)
        return f"{size_mb:.2f} MB"

    @property
    def formatted_duration(self) -> str:
        """포맷된 재생 시간"""
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"


class PlaybackPipeline:
    """재생 파이프라인"""

    def __init__(self, file_path: str, window_handle=None):
        """
        재생 파이프라인 초기화

        Args:
            file_path: 재생할 파일 경로
            window_handle: 윈도우 핸들
        """
        self.file_path = file_path
        self.window_handle = window_handle
        self.pipeline = None
        self.video_sink = None
        self.bus = None

        self.state = PlaybackState.STOPPED
        self.duration = 0
        self.current_position = 0

        # 콜백
        self.on_position_changed = None
        self.on_state_changed = None
        self.on_eos = None

        # 타이머
        self._position_timer = None


    def create_pipeline(self) -> bool:
        """
        재생 파이프라인 생성

        Returns:
            성공 여부
        """
        try:
            # 파일 존재 확인
            if not os.path.exists(self.file_path):
                logger.error(f"File not found: {self.file_path}")
                return False

            # 플랫폼별 비디오 싱크 선택 (공통 유틸리티 사용)
            video_sink = get_video_sink()

            # 파이프라인 문자열 생성
            pipeline_str = (
                f"filesrc location=\"{self.file_path}\" ! "
                "decodebin name=decoder ! "
                "videoconvert ! "
                "videoscale ! "
                "video/x-raw,width=1280,height=720 ! "
                f"{video_sink} name=videosink sync=true"
            )

            logger.debug(f"Creating playback pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            # 비디오 싱크 가져오기
            self.video_sink = self.pipeline.get_by_name("videosink")

            # 버스 설정
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self._on_bus_message)

            # 윈도우 핸들 설정
            if self.window_handle:
                self.bus.enable_sync_message_emission()
                self.bus.connect("sync-message::element", self._on_sync_message)

            logger.info(f"Playback pipeline created for: {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create playback pipeline: {e}")
            self.state = PlaybackState.ERROR
            return False

    def play(self) -> bool:
        """재생 시작"""
        if not self.pipeline:
            logger.error("Pipeline not created")
            return False

        try:
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start playback")
                self.state = PlaybackState.ERROR
                return False

            self.state = PlaybackState.PLAYING
            self._start_position_timer()

            # 상태 변경 콜백
            if self.on_state_changed:
                self.on_state_changed(self.state)

            logger.info("Playback started")
            return True

        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            return False

    def pause(self) -> bool:
        """일시정지"""
        if not self.pipeline or self.state != PlaybackState.PLAYING:
            return False

        try:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.state = PlaybackState.PAUSED
            self._stop_position_timer()

            if self.on_state_changed:
                self.on_state_changed(self.state)

            logger.info("Playback paused")
            return True

        except Exception as e:
            logger.error(f"Error pausing playback: {e}")
            return False

    def resume(self) -> bool:
        """재생 재개"""
        if not self.pipeline or self.state != PlaybackState.PAUSED:
            return False

        try:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.state = PlaybackState.PLAYING
            self._start_position_timer()

            if self.on_state_changed:
                self.on_state_changed(self.state)

            logger.info("Playback resumed")
            return True

        except Exception as e:
            logger.error(f"Error resuming playback: {e}")
            return False

    def stop(self):
        """재생 정지"""
        if self.pipeline:
            self._stop_position_timer()
            self.pipeline.set_state(Gst.State.NULL)
            self.state = PlaybackState.STOPPED

            if self.on_state_changed:
                self.on_state_changed(self.state)

            logger.info("Playback stopped")

    def seek(self, position: float) -> bool:
        """
        특정 위치로 이동

        Args:
            position: 이동할 위치 (초)

        Returns:
            성공 여부
        """
        if not self.pipeline:
            return False

        try:
            # nanoseconds로 변환
            position_ns = int(position * Gst.SECOND)

            # Seek 실행
            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                position_ns
            )

            self.current_position = position
            logger.debug(f"Seeked to position: {position:.2f}s")
            return True

        except Exception as e:
            logger.error(f"Error seeking: {e}")
            return False

    def get_duration(self) -> float:
        """
        전체 재생 시간 반환

        Returns:
            재생 시간 (초)
        """
        if not self.pipeline:
            return 0

        try:
            success, duration = self.pipeline.query_duration(Gst.Format.TIME)
            if success:
                self.duration = duration / Gst.SECOND
                return self.duration
            return 0

        except Exception as e:
            logger.error(f"Error getting duration: {e}")
            return 0

    def get_position(self) -> float:
        """
        현재 재생 위치 반환

        Returns:
            현재 위치 (초)
        """
        if not self.pipeline:
            return 0

        try:
            success, position = self.pipeline.query_position(Gst.Format.TIME)
            if success:
                self.current_position = position / Gst.SECOND
                return self.current_position
            return 0

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return 0

    def set_playback_rate(self, rate: float) -> bool:
        """
        재생 속도 설정

        Args:
            rate: 재생 속도 (1.0 = 정상, 2.0 = 2배속)

        Returns:
            성공 여부
        """
        if not self.pipeline:
            return False

        try:
            position = self.get_position()

            # 새로운 속도로 seek
            event = Gst.Event.new_seek(
                rate,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                Gst.SeekType.SET,
                int(position * Gst.SECOND),
                Gst.SeekType.NONE,
                0
            )

            self.pipeline.send_event(event)
            logger.info(f"Playback rate set to: {rate}x")
            return True

        except Exception as e:
            logger.error(f"Error setting playback rate: {e}")
            return False

    def set_window_handle(self, window_handle):
        """윈도우 핸들 설정"""
        self.window_handle = window_handle
        if self.video_sink:
            try:
                GstVideo.VideoOverlay.set_window_handle(self.video_sink, window_handle)
                logger.debug(f"Window handle set: {window_handle}")
            except Exception as e:
                logger.error(f"Failed to set window handle: {e}")

    def _on_sync_message(self, bus, message):
        """동기 메시지 처리"""
        if message.get_structure() is None:
            return

        if message.get_structure().get_name() == 'prepare-window-handle':
            if self.window_handle:
                sink = message.src
                try:
                    GstVideo.VideoOverlay.set_window_handle(sink, self.window_handle)
                    logger.debug("Window handle set via sync message")
                except Exception as e:
                    logger.error(f"Failed to set window handle in sync: {e}")

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Playback error: {err}")
            self.state = PlaybackState.ERROR
            self.stop()

        elif t == Gst.MessageType.EOS:
            logger.info("End of stream")
            if self.on_eos:
                self.on_eos()
            self.stop()

        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending = message.parse_state_changed()
                logger.debug(f"State: {old_state.value_nick} -> {new_state.value_nick}")

    def _start_position_timer(self):
        """위치 업데이트 타이머 시작"""
        def update_position():
            if self.state == PlaybackState.PLAYING:
                position = self.get_position()
                if self.on_position_changed:
                    self.on_position_changed(position, self.duration)
                return True  # Continue timer
            return False  # Stop timer

        if self._position_timer:
            GLib.source_remove(self._position_timer)

        self._position_timer = GLib.timeout_add(100, update_position)  # 100ms interval

    def _stop_position_timer(self):
        """위치 업데이트 타이머 정지"""
        if self._position_timer:
            GLib.source_remove(self._position_timer)
            self._position_timer = None


class PlaybackManager:
    """재생 관리자"""

    def __init__(self, recordings_dir: str = "recordings"):
        """
        재생 관리자 초기화

        Args:
            recordings_dir: 녹화 파일 디렉토리
        """
        self.recordings_dir = Path(recordings_dir)
        self.playback_pipeline = None
        self.recording_files: List[RecordingFile] = []
        self.current_file: Optional[RecordingFile] = None

        # 콜백
        self.on_file_list_updated = None

        logger.info(f"Playback manager initialized: {recordings_dir}")

    def scan_recordings(self) -> List[RecordingFile]:
        """
        녹화 파일 스캔

        Returns:
            녹화 파일 목록
        """
        self.recording_files.clear()

        if not self.recordings_dir.exists():
            logger.warning(f"Recordings directory not found: {self.recordings_dir}")
            return []

        # 지원되는 파일 형식
        supported_formats = ['.mp4', '.mkv', '.avi']

        # 모든 카메라 디렉토리 스캔
        for camera_dir in self.recordings_dir.iterdir():
            if not camera_dir.is_dir():
                continue

            camera_id = camera_dir.name

            # 날짜 디렉토리 스캔
            for date_dir in camera_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                # 녹화 파일 스캔
                for file_path in date_dir.iterdir():
                    if file_path.suffix.lower() not in supported_formats:
                        continue

                    try:
                        # 파일 정보 추출
                        file_stat = file_path.stat()

                        # 파일명에서 타임스탬프 추출 (형식: cam01_20240101_120000.mp4)
                        file_name = file_path.stem
                        parts = file_name.split('_')
                        if len(parts) >= 3:
                            date_str = parts[-2]
                            time_str = parts[-1]
                            timestamp = datetime.strptime(
                                f"{date_str}_{time_str}",
                                "%Y%m%d_%H%M%S"
                            )
                        else:
                            timestamp = datetime.fromtimestamp(file_stat.st_mtime)

                        # 재생 시간 가져오기 (임시로 0)
                        duration = self._get_file_duration(str(file_path))

                        # RecordingFile 객체 생성
                        recording = RecordingFile(
                            file_path=str(file_path),
                            camera_id=camera_id,
                            camera_name=f"Camera {camera_id}",
                            timestamp=timestamp,
                            duration=duration,
                            file_size=file_stat.st_size
                        )

                        self.recording_files.append(recording)

                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")

        # 시간순 정렬 (최신 먼저)
        self.recording_files.sort(key=lambda x: x.timestamp, reverse=True)

        # 콜백 호출
        if self.on_file_list_updated:
            self.on_file_list_updated(self.recording_files)

        logger.info(f"Found {len(self.recording_files)} recording files")
        return self.recording_files

    def _get_file_duration(self, file_path: str) -> float:
        """
        파일 재생 시간 가져오기

        Args:
            file_path: 파일 경로

        Returns:
            재생 시간 (초)
        """
        try:
            # 임시 파이프라인으로 duration 가져오기
            pipeline_str = f"filesrc location=\"{file_path}\" ! decodebin ! fakesink"
            pipeline = Gst.parse_launch(pipeline_str)

            pipeline.set_state(Gst.State.PAUSED)
            pipeline.get_state(Gst.CLOCK_TIME_NONE)

            success, duration = pipeline.query_duration(Gst.Format.TIME)
            pipeline.set_state(Gst.State.NULL)

            if success:
                return duration / Gst.SECOND

        except Exception as e:
            logger.debug(f"Could not get duration for {file_path}: {e}")

        return 0

    def play_file(self, file_path: str, window_handle=None) -> bool:
        """
        파일 재생

        Args:
            file_path: 재생할 파일 경로
            window_handle: 윈도우 핸들

        Returns:
            성공 여부
        """
        # 기존 재생 중지
        if self.playback_pipeline:
            self.stop_playback()

        # 파일 찾기
        for recording in self.recording_files:
            if recording.file_path == file_path:
                self.current_file = recording
                break

        # 재생 파이프라인 생성
        self.playback_pipeline = PlaybackPipeline(file_path, window_handle)

        if self.playback_pipeline.create_pipeline():
            return self.playback_pipeline.play()

        return False

    def stop_playback(self):
        """재생 정지"""
        if self.playback_pipeline:
            self.playback_pipeline.stop()
            self.playback_pipeline = None
            self.current_file = None

    def pause_playback(self) -> bool:
        """일시정지"""
        if self.playback_pipeline:
            return self.playback_pipeline.pause()
        return False

    def resume_playback(self) -> bool:
        """재생 재개"""
        if self.playback_pipeline:
            return self.playback_pipeline.resume()
        return False

    def seek(self, position: float) -> bool:
        """
        특정 위치로 이동

        Args:
            position: 이동할 위치 (초)

        Returns:
            성공 여부
        """
        if self.playback_pipeline:
            return self.playback_pipeline.seek(position)
        return False

    def set_playback_rate(self, rate: float) -> bool:
        """
        재생 속도 설정

        Args:
            rate: 재생 속도

        Returns:
            성공 여부
        """
        if self.playback_pipeline:
            return self.playback_pipeline.set_playback_rate(rate)
        return False

    def get_playback_state(self) -> PlaybackState:
        """재생 상태 반환"""
        if self.playback_pipeline:
            return self.playback_pipeline.state
        return PlaybackState.STOPPED

    def filter_recordings(self, camera_id: str = None,
                         start_date: datetime = None,
                         end_date: datetime = None) -> List[RecordingFile]:
        """
        녹화 파일 필터링

        Args:
            camera_id: 카메라 ID
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            필터링된 파일 목록
        """
        filtered = self.recording_files

        if camera_id:
            filtered = [r for r in filtered if r.camera_id == camera_id]

        if start_date:
            filtered = [r for r in filtered if r.timestamp >= start_date]

        if end_date:
            filtered = [r for r in filtered if r.timestamp <= end_date]

        return filtered

    def delete_recording(self, file_path: str) -> bool:
        """
        녹화 파일 삭제

        Args:
            file_path: 삭제할 파일 경로

        Returns:
            성공 여부
        """
        try:
            # 재생 중인 파일인지 확인
            if self.current_file and self.current_file.file_path == file_path:
                self.stop_playback()

            # 파일 삭제
            Path(file_path).unlink()

            # 목록에서 제거
            self.recording_files = [
                r for r in self.recording_files
                if r.file_path != file_path
            ]

            # 콜백 호출
            if self.on_file_list_updated:
                self.on_file_list_updated(self.recording_files)

            logger.info(f"Recording deleted: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete recording: {e}")
            return False