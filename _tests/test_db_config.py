"""
DB 기반 ConfigManager 테스트
JSON → DB 마이그레이션 및 CRUD 테스트
"""

import sys
import os
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from loguru import logger
from core.config import ConfigManager, CameraConfigData

# Configure simple logging
logger.remove()
logger.add(sys.stdout, level="DEBUG")


def test_json_to_db_migration():
    """JSON → DB 자동 마이그레이션 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 1: JSON → DB 자동 마이그레이션")
    logger.info("=" * 60)

    # 테스트용 DB 파일 경로
    test_db = "test_migration.db"

    # 기존 테스트 DB 삭제
    if Path(test_db).exists():
        Path(test_db).unlink()
        logger.info(f"기존 테스트 DB 삭제: {test_db}")

    # ConfigManager 초기화 (JSON 파일이 있으면 자동 마이그레이션)
    try:
        ConfigManager.reset_instance()
        config = ConfigManager.get_instance(db_path=test_db)

        # 설정 확인
        logger.success(f"ConfigManager 초기화 성공 (DB: {test_db})")
        logger.info(f"앱 이름: {config.app_config.app_name}")
        logger.info(f"버전: {config.app_config.version}")
        logger.info(f"카메라 수: {len(config.cameras)}")

        # 카메라 정보 출력
        for cam in config.cameras:
            logger.info(f"  - {cam.camera_id}: {cam.name} ({cam.rtsp_url})")

        # Storage config 확인
        storage = config.config.get("storage", {})
        logger.info(f"녹화 경로: {storage.get('recording_path')}")

        # Streaming config 확인
        streaming = config.streaming_config
        logger.info(f"OSD 폰트 색상: {streaming.get('osd_font_color')}")
        logger.info(f"디코더 우선순위: {streaming.get('decoder_preference')}")

        return True

    except Exception as e:
        logger.error(f"마이그레이션 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ConfigManager.reset_instance()


def test_db_read_write():
    """DB 읽기/쓰기 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 2: DB 읽기/쓰기")
    logger.info("=" * 60)

    test_db = "test_rw.db"

    # 기존 테스트 DB 삭제
    if Path(test_db).exists():
        Path(test_db).unlink()

    try:
        ConfigManager.reset_instance()
        config = ConfigManager.get_instance(db_path=test_db)

        # 카메라 추가 테스트
        new_camera = CameraConfigData(
            camera_id="cam_test",
            name="Test Camera",
            rtsp_url="rtsp://192.168.0.100:554/test",
            enabled=True,
            streaming_enabled_start=True,
            recording_enabled_start=False
        )

        config.add_camera(new_camera)
        logger.info(f"카메라 추가: {new_camera.camera_id}")

        # DB에 저장
        config.save_config()
        logger.success("설정 DB 저장 완료")

        # ConfigManager 재시작하여 로드 테스트
        ConfigManager.reset_instance()
        config2 = ConfigManager.get_instance(db_path=test_db)

        # 저장된 카메라 확인
        test_cam = config2.get_camera("cam_test")
        if test_cam:
            logger.success(f"카메라 로드 성공: {test_cam.name}")
            logger.info(f"  RTSP URL: {test_cam.rtsp_url}")
            logger.info(f"  Enabled: {test_cam.enabled}")
        else:
            logger.error("카메라 로드 실패")
            return False

        return True

    except Exception as e:
        logger.error(f"읽기/쓰기 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ConfigManager.reset_instance()


def test_video_transform():
    """Video Transform 필드 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 3: Video Transform 필드")
    logger.info("=" * 60)

    test_db = "test_video_transform.db"

    if Path(test_db).exists():
        Path(test_db).unlink()

    try:
        ConfigManager.reset_instance()
        config = ConfigManager.get_instance(db_path=test_db)

        # video_transform가 있는 카메라 추가
        camera_with_transform = CameraConfigData(
            camera_id="cam_transform",
            name="Transform Camera",
            rtsp_url="rtsp://192.168.0.200:554/test",
            video_transform={
                "enabled": True,
                "flip": "vertical",
                "rotation": 90
            }
        )

        config.add_camera(camera_with_transform)
        config.save_config()
        logger.info("Video transform 카메라 저장")

        # 재로드 테스트
        ConfigManager.reset_instance()
        config2 = ConfigManager.get_instance(db_path=test_db)

        cam = config2.get_camera("cam_transform")
        if cam and cam.video_transform:
            logger.success("Video transform 로드 성공:")
            logger.info(f"  Enabled: {cam.video_transform.get('enabled')}")
            logger.info(f"  Flip: {cam.video_transform.get('flip')}")
            logger.info(f"  Rotation: {cam.video_transform.get('rotation')}")
            return True
        else:
            logger.error("Video transform 로드 실패")
            return False

    except Exception as e:
        logger.error(f"Video transform 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ConfigManager.reset_instance()


def test_ui_config():
    """UI 설정 저장/로드 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 4: UI 설정 저장/로드")
    logger.info("=" * 60)

    test_db = "test_ui_config.db"

    if Path(test_db).exists():
        Path(test_db).unlink()

    try:
        ConfigManager.reset_instance()
        config = ConfigManager.get_instance(db_path=test_db)

        # UI 설정 변경
        config.update_ui_window_state(100, 200, 1280, 720)
        config.update_ui_dock_state(
            camera_visible=False,
            recording_visible=True,
            playback_visible=False
        )

        # UI 설정 저장
        config.save_ui_config()
        logger.info("UI 설정 저장")

        # 재로드 테스트
        ConfigManager.reset_instance()
        config2 = ConfigManager.get_instance(db_path=test_db)

        # 검증
        ws = config2.ui_config.window_state
        ds = config2.ui_config.dock_state

        logger.info(f"Window state: x={ws['x']}, y={ws['y']}, w={ws['width']}, h={ws['height']}")
        logger.info(f"Dock state: camera={ds['camera_visible']}, recording={ds['recording_visible']}, playback={ds['playback_visible']}")

        if ws['x'] == 100 and ws['y'] == 200 and ws['width'] == 1280 and ws['height'] == 720:
            if ds['camera_visible'] == False and ds['recording_visible'] == True:
                logger.success("UI 설정 저장/로드 성공")
                return True

        logger.error("UI 설정 값이 일치하지 않음")
        return False

    except Exception as e:
        logger.error(f"UI 설정 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ConfigManager.reset_instance()


def cleanup_test_files():
    """테스트 파일 정리"""
    test_files = [
        "test_migration.db",
        "test_rw.db",
        "test_video_transform.db",
        "test_ui_config.db"
    ]

    for file in test_files:
        path = Path(file)
        if path.exists():
            path.unlink()
            logger.debug(f"삭제: {file}")


def main():
    """테스트 실행"""
    logger.info("DB 기반 ConfigManager 테스트 시작")
    logger.info("")

    results = []

    # 테스트 1: JSON → DB 마이그레이션
    results.append(("JSON → DB 마이그레이션", test_json_to_db_migration()))

    # 테스트 2: DB 읽기/쓰기
    results.append(("DB 읽기/쓰기", test_db_read_write()))

    # 테스트 3: Video Transform
    results.append(("Video Transform", test_video_transform()))

    # 테스트 4: UI Config
    results.append(("UI 설정", test_ui_config()))

    # 테스트 파일 정리
    logger.info("")
    logger.info("=" * 60)
    logger.info("테스트 파일 정리")
    logger.info("=" * 60)
    cleanup_test_files()

    # 결과 요약
    logger.info("")
    logger.info("=" * 60)
    logger.info("테스트 결과 요약")
    logger.info("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    logger.info("")
    if all_passed:
        logger.success("모든 테스트 통과!")
        return 0
    else:
        logger.error("일부 테스트 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
