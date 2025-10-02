#!/usr/bin/env python3
"""
Recording Test
녹화 기능 테스트
"""

import sys
import time
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from recording.recording_manager import RecordingManager
from config.config_manager import ConfigManager
from loguru import logger

def setup_logging():
    """로깅 설정"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True
    )

def test_recording():
    """녹화 기능 테스트"""
    setup_logging()

    logger.info("===== 녹화 기능 테스트 시작 =====")

    # 설정 불러오기
    config_manager = ConfigManager()
    cameras = config_manager.get_enabled_cameras()

    if not cameras:
        logger.error("활성화된 카메라가 없습니다")
        return

    # 녹화 매니저 생성
    recording_manager = RecordingManager()

    # 첫 번째 카메라로 테스트
    camera = cameras[0]
    logger.info(f"테스트 카메라: {camera.name}")

    # 녹화 시작
    logger.info("녹화 시작...")
    success = recording_manager.start_recording(
        camera_id=camera.camera_id,
        camera_name=camera.name,
        rtsp_url=camera.rtsp_url,
        file_format="mp4",
        file_duration=30  # 30초 단위로 파일 분할
    )

    if not success:
        logger.error("녹화 시작 실패")
        return

    logger.success("녹화 시작 성공")

    # 10초 동안 녹화
    for i in range(10):
        time.sleep(1)
        info = recording_manager.get_all_recording_info()
        if camera.camera_id in info:
            rec_info = info[camera.camera_id]
            if 'duration' in rec_info:
                logger.info(f"녹화 중... {rec_info['duration']}초")

    # 녹화 일시정지
    logger.info("녹화 일시정지...")
    recording_manager.pause_recording(camera.camera_id)
    time.sleep(2)

    # 녹화 재개
    logger.info("녹화 재개...")
    recording_manager.resume_recording(camera.camera_id)
    time.sleep(3)

    # 녹화 정지
    logger.info("녹화 정지...")
    recording_manager.stop_recording(camera.camera_id)

    # 디스크 사용량 확인
    disk_info = recording_manager.get_disk_usage()
    logger.info(f"디스크 사용량: {disk_info['total_size_mb']:.2f} MB ({disk_info['file_count']} 파일)")

    logger.info("===== 녹화 기능 테스트 완료 =====")

if __name__ == "__main__":
    try:
        test_recording()
    except KeyboardInterrupt:
        logger.info("\n테스트 중단됨")
    except Exception as e:
        logger.exception(f"오류 발생: {e}")