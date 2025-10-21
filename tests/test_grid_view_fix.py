#!/usr/bin/env python3
"""
Grid View 카메라 표시 문제 테스트
모든 카메라가 별도 창이 아닌 Grid View에 표시되는지 확인
"""

import sys
import time
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from loguru import logger

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ui.main_window_enhanced import EnhancedMainWindow


def test_grid_view_cameras():
    """Grid View 카메라 표시 테스트"""

    logger.info("=" * 60)
    logger.info("Grid View 카메라 표시 테스트 시작")
    logger.info("=" * 60)

    # Qt 애플리케이션 생성
    app = QApplication(sys.argv)

    # 메인 윈도우 생성
    window = EnhancedMainWindow()
    window.show()

    logger.info("\n1. 메인 윈도우 생성 완료")
    logger.info(f"   - Grid View 채널 수: {len(window.grid_view.channels)}")
    logger.info(f"   - 설정된 카메라 수: {len(window.config_manager.get_enabled_cameras())}")

    # 카메라 리스트와 그리드 뷰 확인
    logger.info("\n2. 카메라-채널 매핑 확인:")
    cameras = window.config_manager.get_enabled_cameras()
    for i, camera in enumerate(cameras[:4]):  # 최대 4개 카메라
        channel = window.grid_view.get_channel(i)
        if channel:
            logger.info(f"   채널 {i}: {camera.camera_id} -> 윈도우 핸들: {channel.get_window_handle()}")

    # main_window 참조 확인
    logger.info("\n3. Camera List Widget 설정 확인:")
    logger.info(f"   - main_window 참조: {window.camera_list.main_window is not None}")
    logger.info(f"   - grid_view 접근 가능: {hasattr(window.camera_list.main_window, 'grid_view')}")

    # 5초 후 자동으로 모든 카메라 연결
    def connect_all_cameras():
        logger.info("\n4. 모든 카메라 연결 시작...")
        window._connect_all_cameras()

        # 연결 상태 확인
        time.sleep(3)
        connected_count = 0
        for camera_item in window.camera_list.camera_items.values():
            if camera_item.camera_stream and camera_item.camera_stream.is_connected():
                connected_count += 1
                logger.success(f"   ✓ {camera_item.camera_config.name} 연결됨")
            else:
                logger.warning(f"   ✗ {camera_item.camera_config.name} 연결 실패")

        logger.info(f"\n5. 연결 결과: {connected_count}/{len(window.camera_list.camera_items)} 카메라 연결됨")

        # Grid View 표시 확인
        logger.info("\n6. Grid View 표시 상태:")
        for i, channel in enumerate(window.grid_view.channels[:4]):
            if channel.camera_id:
                logger.info(f"   채널 {i}: {channel.camera_id} - 연결: {channel.is_connected}")

    # 타이머로 자동 연결
    from PyQt5.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(connect_all_cameras)
    timer.setSingleShot(True)
    timer.start(2000)  # 2초 후 실행

    logger.info("\n테스트 실행 중... (Ctrl+C로 종료)")

    # 애플리케이션 실행
    sys.exit(app.exec_())


if __name__ == "__main__":
    # 로깅 설정
    logger.remove()
    logger.add(sys.stdout, level="DEBUG", colorize=True)

    try:
        test_grid_view_cameras()
    except KeyboardInterrupt:
        logger.info("\n테스트 중단됨")
    except Exception as e:
        logger.exception(f"테스트 실패: {e}")