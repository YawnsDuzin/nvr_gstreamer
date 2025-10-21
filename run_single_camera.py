#!/usr/bin/env python3
"""
단일 카메라 NVR 실행 스크립트
간단한 명령으로 단일 카메라 녹화 시스템을 시작
"""

import sys
import os
import argparse
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from loguru import logger

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from ui.main_window_enhanced import EnhancedMainWindow
from config.config_manager import ConfigManager


def setup_logging(debug: bool = False):
    """로깅 설정"""
    logger.remove()

    # 콘솔 로깅
    log_level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # 파일 로깅
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "single_camera_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="1 day",
        retention="7 days"
    )


def check_configuration():
    """설정 확인"""
    config_manager = ConfigManager()
    cameras = config_manager.get_enabled_cameras()

    if not cameras:
        logger.error("활성화된 카메라가 없습니다!")
        logger.error("config.yaml 파일을 확인하세요.")
        return False

    if len(cameras) > 1:
        logger.warning(f"{len(cameras)}개의 카메라가 설정되어 있습니다.")
        logger.warning("단일 카메라 모드에서는 첫 번째 카메라만 사용됩니다.")

    camera = cameras[0]
    logger.info(f"카메라 설정 확인:")
    logger.info(f"  - ID: {camera.camera_id}")
    logger.info(f"  - 이름: {camera.name}")
    logger.info(f"  - RTSP URL: {camera.rtsp_url}")
    logger.info(f"  - 녹화: {'활성화' if camera.recording_enabled else '비활성화'}")

    return True


def check_dependencies():
    """의존성 확인"""
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        logger.success("✓ GStreamer 초기화 성공")
        return True
    except Exception as e:
        logger.error(f"✗ GStreamer 초기화 실패: {e}")
        logger.error("GStreamer를 설치하세요:")
        logger.error("  Windows: https://gstreamer.freedesktop.org/download/")
        logger.error("  Linux: sudo apt-get install gstreamer1.0-tools")
        return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="단일 카메라 NVR 시스템")
    parser.add_argument("--debug", action="store_true", help="디버그 모드 활성화")
    parser.add_argument("--recording", action="store_true", help="시작 시 자동 녹화")
    parser.add_argument("--headless", action="store_true", help="GUI 없이 녹화만 실행")
    args = parser.parse_args()

    # 로깅 설정
    setup_logging(debug=args.debug)

    logger.info("=" * 60)
    logger.info("단일 카메라 NVR 시스템 시작")
    logger.info("=" * 60)

    # 의존성 확인
    if not check_dependencies():
        logger.error("의존성 확인 실패. 프로그램을 종료합니다.")
        return 1

    # 설정 확인
    if not check_configuration():
        logger.error("설정 확인 실패. 프로그램을 종료합니다.")
        return 1

    if args.headless:
        # GUI 없이 녹화만 실행
        logger.info("헤드리스 모드: GUI 없이 녹화만 실행")

        from recording.recording_manager import RecordingManager
        from config.config_manager import ConfigManager
        import time

        config_manager = ConfigManager()
        camera = config_manager.get_enabled_cameras()[0]
        recording_manager = RecordingManager()

        logger.info("녹화 시작...")
        if recording_manager.start_recording(
            camera.camera_id,
            camera.name,
            camera.rtsp_url,
            file_format="mp4",
            file_duration=600  # 10분 단위
        ):
            logger.success("✓ 녹화 시작됨")
            logger.info("Ctrl+C를 눌러 종료하세요...")

            try:
                while True:
                    time.sleep(10)
                    info = recording_manager.get_all_recording_info()
                    if camera.camera_id in info:
                        rec_info = info[camera.camera_id]
                        if 'duration' in rec_info:
                            logger.info(f"녹화 중... {rec_info['duration']}초")
            except KeyboardInterrupt:
                logger.info("\n녹화 종료 중...")
                recording_manager.stop_all_recordings()
                logger.success("✓ 녹화 종료됨")
        else:
            logger.error("✗ 녹화 시작 실패")
            return 1
    else:
        # GUI 모드
        logger.info("GUI 모드 시작")

        # Qt 애플리케이션 생성
        app = QApplication(sys.argv)
        app.setApplicationName("Single Camera NVR")
        app.setOrganizationName("PyNVR")

        # High DPI 스케일링 활성화
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        try:
            # 메인 윈도우 생성 및 표시
            window = EnhancedMainWindow()
            window.show()

            logger.success("✓ 단일 카메라 NVR 시작됨")

            # 자동 녹화 시작 옵션
            if args.recording:
                logger.info("자동 녹화 모드 활성화")
                # 잠시 대기 후 녹화 시작
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(2000, lambda: start_auto_recording(window))

            # 애플리케이션 실행
            return app.exec_()

        except Exception as e:
            logger.exception(f"치명적 오류: {e}")
            return 1

    return 0


def start_auto_recording(window):
    """자동 녹화 시작"""
    try:
        config_manager = ConfigManager()
        camera = config_manager.get_enabled_cameras()[0]

        # 카메라 연결
        window._connect_all_cameras()

        # 녹화 시작
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, lambda: window.recording_control.start_recording(camera.camera_id))

        logger.success("✓ 자동 녹화 시작됨")
    except Exception as e:
        logger.error(f"자동 녹화 시작 실패: {e}")


if __name__ == "__main__":
    sys.exit(main())