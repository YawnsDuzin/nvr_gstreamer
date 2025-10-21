#!/usr/bin/env python3
"""
단일 카메라 연결 및 녹화 테스트 스크립트
Single camera connection and recording test
"""

import sys
import time
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from config.config_manager import ConfigManager
from streaming.camera_stream import CameraStream
from recording.recording_manager import RecordingManager


def setup_logging():
    """Setup logging"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True
    )


def test_streaming_only():
    """스트리밍만 테스트 (녹화 없이)"""
    logger.info("=" * 60)
    logger.info("테스트 1: 스트리밍만 테스트")
    logger.info("=" * 60)

    # 설정 로드
    config_manager = ConfigManager()
    cameras = config_manager.get_enabled_cameras()

    if not cameras:
        logger.error("활성화된 카메라가 없습니다. config.yaml을 확인하세요.")
        return False

    camera = cameras[0]
    logger.info(f"카메라 발견: {camera.name} ({camera.camera_id})")
    logger.info(f"RTSP URL: {camera.rtsp_url}")

    # 카메라 스트림 생성 및 연결
    stream = CameraStream(camera.camera_id, camera.rtsp_url)

    logger.info("카메라 연결 시도 중...")
    if stream.connect():
        logger.success("✓ 카메라 연결 성공!")
        logger.info("10초 동안 스트리밍 테스트...")
        time.sleep(10)

        stream.disconnect()
        logger.info("✓ 스트리밍 테스트 완료")
        return True
    else:
        logger.error("✗ 카메라 연결 실패")
        return False


def test_recording_only():
    """녹화만 테스트 (디스플레이 없이)"""
    logger.info("=" * 60)
    logger.info("테스트 2: 녹화만 테스트")
    logger.info("=" * 60)

    # 설정 로드
    config_manager = ConfigManager()
    cameras = config_manager.get_enabled_cameras()

    if not cameras:
        logger.error("활성화된 카메라가 없습니다.")
        return False

    camera = cameras[0]
    logger.info(f"카메라: {camera.name}")

    # 녹화 관리자 생성
    recording_manager = RecordingManager()

    logger.info("녹화 시작...")
    if recording_manager.start_recording(
        camera.camera_id,
        camera.name,
        camera.rtsp_url,
        file_format="mp4",
        file_duration=60  # 1분 단위로 파일 분할
    ):
        logger.success("✓ 녹화 시작됨!")

        # 20초 동안 녹화
        for i in range(20):
            time.sleep(1)
            info = recording_manager.get_all_recording_info()
            if camera.camera_id in info:
                rec_info = info[camera.camera_id]
                logger.info(f"녹화 중... {i+1}초 | 파일: {Path(rec_info['current_file']).name}")

        # 녹화 중지
        recording_manager.stop_recording(camera.camera_id)
        logger.success("✓ 녹화 완료")

        # 디스크 사용량 확인
        disk_usage = recording_manager.get_disk_usage()
        logger.info(f"녹화 파일 크기: {disk_usage['total_size_mb']:.2f} MB")
        logger.info(f"녹화 파일 개수: {disk_usage['file_count']}")

        return True
    else:
        logger.error("✗ 녹화 시작 실패")
        return False


def test_streaming_and_recording():
    """스트리밍과 녹화 동시 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 3: 스트리밍 + 녹화 동시 테스트")
    logger.info("=" * 60)

    # 설정 로드
    config_manager = ConfigManager()
    cameras = config_manager.get_enabled_cameras()

    if not cameras:
        logger.error("활성화된 카메라가 없습니다.")
        return False

    camera = cameras[0]
    logger.info(f"카메라: {camera.name}")

    # 통합 파이프라인 사용 (unified_pipeline.py)
    from streaming.unified_pipeline import UnifiedPipeline, PipelineMode

    pipeline = UnifiedPipeline(camera.camera_id, camera.rtsp_url)

    # 스트리밍과 녹화 모두 활성화
    logger.info("통합 파이프라인으로 스트리밍과 녹화 시작...")
    if pipeline.start(mode=PipelineMode.BOTH):
        logger.success("✓ 스트리밍 + 녹화 시작됨!")

        # 15초 동안 실행
        for i in range(15):
            time.sleep(1)
            status = pipeline.get_status()
            logger.info(f"실행 중... {i+1}초 | 모드: {status['mode']} | 상태: {status['state']}")

        # 파이프라인 중지
        pipeline.stop()
        logger.success("✓ 스트리밍 + 녹화 완료")

        return True
    else:
        logger.error("✗ 파이프라인 시작 실패")
        return False


def main():
    """메인 테스트 함수"""
    setup_logging()

    # GStreamer 초기화
    Gst.init(None)

    logger.info("단일 카메라 테스트 시작")
    logger.info("설정 파일: config.yaml")

    # 각 테스트 실행
    tests = [
        ("스트리밍만", test_streaming_only),
        ("녹화만", test_recording_only),
        ("스트리밍+녹화", test_streaming_and_recording)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\n테스트: {test_name}")
            success = test_func()
            results.append((test_name, success))
            time.sleep(2)  # 테스트 간 대기
        except Exception as e:
            logger.error(f"테스트 실패: {e}")
            results.append((test_name, False))

    # 결과 요약
    logger.info("\n" + "=" * 60)
    logger.info("테스트 결과 요약")
    logger.info("=" * 60)
    for test_name, success in results:
        status = "✓ 성공" if success else "✗ 실패"
        logger.info(f"{test_name}: {status}")

    # 모든 테스트 성공 여부
    all_passed = all(success for _, success in results)
    if all_passed:
        logger.success("\n모든 테스트 통과!")
    else:
        logger.error("\n일부 테스트 실패")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())