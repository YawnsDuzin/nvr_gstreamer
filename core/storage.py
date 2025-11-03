"""
스토리지 관리 서비스

디스크 공간 관리, 녹화 파일 정리, 백업 등 스토리지 관련 기능
"""
import os
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from loguru import logger

from .models import StorageInfo, Recording
from .exceptions import StorageError


class StorageService:
    """스토리지 관리 서비스"""

    def __init__(self, recordings_path: str = None):
        """
        Initialize storage service

        Args:
            recordings_path: 녹화 파일 저장 경로 (None이면 설정에서 로드)
        """
        # 설정 로드
        from core.config import ConfigManager
        config_manager = ConfigManager.get_instance()
        recording_config = config_manager.get_recording_config()

        # 녹화 경로 설정
        if recordings_path is None:
            recordings_path = recording_config.get('base_path', './recordings')
            logger.debug(f"Using recordings base_path from config: {recordings_path}")

        # 경로 검증 (Fallback 없음 - 오류 시 경고만 표시)
        self.recordings_path = Path(recordings_path)
        self._path_available = self._validate_storage_path()

        # 설정에서 임계값 로드
        self.auto_cleanup_enabled = recording_config.get('auto_cleanup_enabled', True)
        self.cleanup_interval_hours = recording_config.get('cleanup_interval_hours', 6)
        self.min_free_space_gb = recording_config.get('min_free_space_gb', 10)
        self.max_storage_days = recording_config.get('retention_days', 30)
        self.cleanup_threshold_percent = recording_config.get('cleanup_threshold_percent', 90)

        if self._path_available:
            logger.info(f"Storage service initialized: path={self.recordings_path}, "
                       f"retention={self.max_storage_days}days, "
                       f"threshold={self.cleanup_threshold_percent}%, "
                       f"min_free={self.min_free_space_gb}GB, "
                       f"auto_cleanup={self.auto_cleanup_enabled}")
        else:
            logger.error(f"Storage service initialized with UNAVAILABLE path: {self.recordings_path}")
            logger.error("[STORAGE] Recording will be DISABLED until the storage path becomes available!")

    def get_storage_info(self) -> StorageInfo:
        """
        현재 스토리지 정보 조회

        Returns:
            StorageInfo 객체
        """
        try:
            # 디스크 사용량 조회
            stat = shutil.disk_usage(self.recordings_path)

            # 녹화 파일 정보 수집
            recordings_count = 0
            recordings_size = 0
            oldest_file = None
            newest_file = None

            for camera_dir in self.recordings_path.iterdir():
                if not camera_dir.is_dir():
                    continue

                for date_dir in camera_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    for file in date_dir.glob("*.mp4"):
                        recordings_count += 1
                        file_size = file.stat().st_size
                        recordings_size += file_size

                        file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
                        if oldest_file is None or file_mtime < oldest_file:
                            oldest_file = file_mtime
                        if newest_file is None or file_mtime > newest_file:
                            newest_file = file_mtime

            return StorageInfo(
                total_space=stat.total,
                used_space=stat.used,
                free_space=stat.free,
                recordings_count=recordings_count,
                recordings_size=recordings_size,
                oldest_recording=oldest_file,
                newest_recording=newest_file
            )

        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            raise StorageError(f"Failed to get storage info: {e}")

    def check_disk_space(self) -> Tuple[float, bool]:
        """
        디스크 공간 확인

        Returns:
            (여유 공간 GB, 충분한지 여부)
        """
        try:
            stat = shutil.disk_usage(self.recordings_path)
            free_gb = stat.free / (1024 ** 3)
            is_sufficient = free_gb >= self.min_free_space_gb

            if not is_sufficient:
                logger.warning(f"Low disk space: {free_gb:.1f}GB (minimum: {self.min_free_space_gb}GB)")

            return free_gb, is_sufficient

        except Exception as e:
            logger.error(f"Failed to check disk space: {e}")
            return 0.0, False

    def cleanup_old_recordings(self, days: Optional[int] = None, force: bool = False) -> int:
        """
        오래된 녹화 파일 정리

        Args:
            days: 보관 기간 (일), None이면 기본값 사용
            force: 강제 정리 여부

        Returns:
            삭제된 파일 수
        """
        if days is None:
            days = self.max_storage_days

        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            deleted_size = 0

            logger.info(f"Starting cleanup of recordings older than {days} days (cutoff: {cutoff_date.date()})")

            for camera_dir in self.recordings_path.iterdir():
                if not camera_dir.is_dir():
                    continue

                for date_dir in camera_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    # 날짜 디렉토리 이름에서 날짜 추출 (YYYY-MM-DD 형식)
                    try:
                        dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                        if dir_date < cutoff_date:
                            # 전체 날짜 디렉토리 삭제
                            if force or self._confirm_deletion(date_dir):
                                dir_size = self._get_directory_size(date_dir)
                                shutil.rmtree(date_dir)
                                deleted_count += len(list(date_dir.glob("*.mp4")))
                                deleted_size += dir_size
                                logger.info(f"Deleted old recordings: {date_dir}")
                    except ValueError:
                        # 날짜 형식이 맞지 않는 디렉토리는 건너뜀
                        logger.debug(f"Skipping non-date directory: {date_dir}")
                        continue

                # 빈 카메라 디렉토리 제거
                if not any(camera_dir.iterdir()):
                    camera_dir.rmdir()
                    logger.debug(f"Removed empty camera directory: {camera_dir}")

            if deleted_count > 0:
                logger.success(f"Cleanup completed: {deleted_count} files deleted, {deleted_size / (1024**3):.2f}GB freed")
            else:
                logger.info("No old recordings found to delete")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old recordings: {e}")
            raise StorageError(f"Failed to cleanup old recordings: {e}")

    def cleanup_by_space(self, target_free_gb: Optional[float] = None) -> int:
        """
        공간 확보를 위한 정리 (오래된 파일부터 삭제)

        Args:
            target_free_gb: 목표 여유 공간 (GB), None이면 기본값 사용

        Returns:
            삭제된 파일 수
        """
        if target_free_gb is None:
            target_free_gb = self.min_free_space_gb * 2  # 여유있게 2배

        try:
            deleted_count = 0
            current_free_gb, _ = self.check_disk_space()

            if current_free_gb >= target_free_gb:
                logger.info(f"Sufficient disk space available: {current_free_gb:.1f}GB")
                return 0

            logger.info(f"Starting space-based cleanup (current: {current_free_gb:.1f}GB, target: {target_free_gb}GB)")

            # 모든 녹화 파일을 날짜순으로 정렬
            all_files = []
            for camera_dir in self.recordings_path.iterdir():
                if not camera_dir.is_dir():
                    continue
                for date_dir in camera_dir.iterdir():
                    if not date_dir.is_dir():
                        continue
                    for file in date_dir.glob("*.mp4"):
                        all_files.append((file, file.stat().st_mtime))

            # 오래된 파일부터 정렬
            all_files.sort(key=lambda x: x[1])

            # 필요한 공간만큼 파일 삭제
            for file_path, _ in all_files:
                if current_free_gb >= target_free_gb:
                    break

                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_count += 1
                    current_free_gb += file_size / (1024 ** 3)
                    logger.debug(f"Deleted: {file_path.name} ({file_size / (1024**2):.1f}MB)")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")

            # 빈 디렉토리 정리
            self._cleanup_empty_directories()

            logger.success(f"Space cleanup completed: {deleted_count} files deleted, {current_free_gb:.1f}GB free")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup by space: {e}")
            raise StorageError(f"Failed to cleanup by space: {e}")

    def auto_cleanup(self) -> int:
        """
        자동 정리 (정책에 따라)

        Returns:
            삭제된 파일 수
        """
        total_deleted = 0

        try:
            storage_info = self.get_storage_info()

            # 1. 공간 부족 체크
            if storage_info.needs_cleanup(self.cleanup_threshold_percent):
                logger.info(f"Storage usage {storage_info.usage_percent:.1f}% exceeds threshold {self.cleanup_threshold_percent}%")
                total_deleted += self.cleanup_by_space()

            # 2. 오래된 파일 체크
            if storage_info.oldest_recording:
                age_days = (datetime.now() - storage_info.oldest_recording).days
                if age_days > self.max_storage_days:
                    logger.info(f"Found recordings older than {self.max_storage_days} days")
                    total_deleted += self.cleanup_old_recordings()

            # 3. 여유 공간 체크
            free_gb, is_sufficient = self.check_disk_space()
            if not is_sufficient:
                logger.warning(f"Insufficient disk space: {free_gb:.1f}GB")
                total_deleted += self.cleanup_by_space()

            return total_deleted

        except Exception as e:
            logger.error(f"Auto cleanup failed: {e}")
            return total_deleted

    def get_recordings_for_camera(self, camera_id: str) -> List[Dict[str, any]]:
        """
        특정 카메라의 녹화 파일 목록 조회

        Args:
            camera_id: 카메라 ID

        Returns:
            녹화 파일 정보 리스트
        """
        recordings = []
        camera_path = self.recordings_path / camera_id

        if not camera_path.exists():
            return recordings

        try:
            for date_dir in sorted(camera_path.iterdir(), reverse=True):
                if not date_dir.is_dir():
                    continue

                for file in sorted(date_dir.glob("*.mp4"), reverse=True):
                    stat = file.stat()
                    recordings.append({
                        'file_path': str(file),
                        'file_name': file.name,
                        'date': date_dir.name,
                        'size_mb': stat.st_size / (1024 ** 2),
                        'created': datetime.fromtimestamp(stat.st_ctime),
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'camera_id': camera_id
                    })

            return recordings

        except Exception as e:
            logger.error(f"Failed to get recordings for camera {camera_id}: {e}")
            return recordings

    def get_all_recordings(self) -> List[Dict[str, any]]:
        """
        모든 녹화 파일 목록 조회

        Returns:
            모든 녹화 파일 정보 리스트
        """
        all_recordings = []

        try:
            for camera_dir in self.recordings_path.iterdir():
                if not camera_dir.is_dir():
                    continue

                camera_id = camera_dir.name
                camera_recordings = self.get_recordings_for_camera(camera_id)
                all_recordings.extend(camera_recordings)

            # 날짜순 정렬 (최신 순)
            all_recordings.sort(key=lambda x: x['modified'], reverse=True)
            return all_recordings

        except Exception as e:
            logger.error(f"Failed to get all recordings: {e}")
            return all_recordings

    def calculate_retention_policy(self) -> Dict[str, any]:
        """
        보관 정책 계산 (공간과 기간 기반)

        Returns:
            보관 정책 정보
        """
        storage_info = self.get_storage_info()
        free_gb, _ = self.check_disk_space()

        # 일일 평균 사용량 계산
        if storage_info.oldest_recording and storage_info.newest_recording:
            days = (storage_info.newest_recording - storage_info.oldest_recording).days or 1
            daily_usage_gb = (storage_info.recordings_size / (1024 ** 3)) / days
        else:
            daily_usage_gb = 0

        # 예상 보관 가능 기간
        if daily_usage_gb > 0:
            estimated_days = int(free_gb / daily_usage_gb)
        else:
            estimated_days = self.max_storage_days

        return {
            'current_usage_gb': storage_info.recordings_size / (1024 ** 3),
            'free_space_gb': free_gb,
            'daily_usage_gb': daily_usage_gb,
            'max_retention_days': self.max_storage_days,
            'estimated_retention_days': min(estimated_days, self.max_storage_days),
            'cleanup_threshold_percent': self.cleanup_threshold_percent,
            'needs_cleanup': storage_info.needs_cleanup(self.cleanup_threshold_percent)
        }

    def _validate_storage_path(self) -> bool:
        """
        저장 경로 검증 (Fallback 없이 오류만 로깅)

        Returns:
            bool: 경로가 유효하면 True, 아니면 False
        """
        try:
            # 1. Windows: 드라이브 존재 여부 확인
            if os.name == 'nt':  # Windows
                drive = os.path.splitdrive(str(self.recordings_path))[0]
                if drive and not os.path.exists(drive + os.sep):
                    logger.error(f"[STORAGE] Drive not found: {drive}")
                    logger.error(f"[STORAGE] Please check if the USB drive is connected: {self.recordings_path}")
                    return False

            # 2. 디렉토리 생성 시도
            try:
                self.recordings_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[STORAGE] Failed to create directory: {e}")
                logger.error(f"[STORAGE] Path: {self.recordings_path}")
                return False

            # 3. 쓰기 권한 테스트
            test_file = self.recordings_path / ".write_test.tmp"
            try:
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                logger.error(f"[STORAGE] No write permission: {e}")
                logger.error(f"[STORAGE] Path: {self.recordings_path}")
                return False

            # 4. 디스크 공간 확인 (경고만, 실패는 아님)
            try:
                stat = shutil.disk_usage(str(self.recordings_path))
                free_gb = stat.free / (1024 ** 3)
                if free_gb < 1.0:
                    logger.warning(f"[STORAGE] Low disk space: {free_gb:.2f}GB")
            except Exception:
                pass  # 디스크 공간 체크 실패는 무시

            logger.debug(f"[STORAGE] Path validated successfully: {self.recordings_path}")
            return True

        except Exception as e:
            logger.error(f"[STORAGE] Path validation failed: {e}")
            logger.error(f"[STORAGE] Path: {self.recordings_path}")
            return False

    def is_path_available(self) -> bool:
        """
        저장 경로 사용 가능 여부 확인

        Returns:
            bool: 경로가 사용 가능하면 True
        """
        return self._path_available

    def _get_directory_size(self, path: Path) -> int:
        """디렉토리 크기 계산"""
        total_size = 0
        for file in path.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
        return total_size

    def _confirm_deletion(self, path: Path) -> bool:
        """삭제 확인 (현재는 항상 True)"""
        # 향후 UI 확인이나 정책 체크 추가 가능
        return True

    def _cleanup_empty_directories(self):
        """빈 디렉토리 정리"""
        for camera_dir in self.recordings_path.iterdir():
            if not camera_dir.is_dir():
                continue

            # 빈 날짜 디렉토리 제거
            for date_dir in camera_dir.iterdir():
                if date_dir.is_dir() and not any(date_dir.iterdir()):
                    date_dir.rmdir()
                    logger.debug(f"Removed empty date directory: {date_dir}")

            # 빈 카메라 디렉토리 제거
            if not any(camera_dir.iterdir()):
                camera_dir.rmdir()
                logger.debug(f"Removed empty camera directory: {camera_dir}")