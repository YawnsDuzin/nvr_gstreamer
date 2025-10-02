#!/usr/bin/env python3
"""
NVR 시스템 실행 스크립트
경로 설정 및 환경 초기화
"""

import sys
import os
from pathlib import Path

# 현재 스크립트 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

# 상위 디렉토리도 추가 (필요한 경우)
parent_dir = current_dir.parent
if parent_dir.exists():
    sys.path.insert(0, str(parent_dir))

# 환경 변수 설정
os.environ['GST_DEBUG'] = '2'  # GStreamer 디버그 레벨
os.environ['QT_QPA_PLATFORM'] = 'xcb'  # Linux GUI

def main():
    """메인 함수"""
    try:
        # 로거 설정
        from loguru import logger
        logger.remove()
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
        )

        # 로그 디렉토리 생성
        log_dir = current_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        logger.add(
            str(log_dir / "nvr_{time:YYYY-MM-DD}.log"),
            rotation="1 day",
            retention="30 days",
            level="DEBUG"
        )

        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {current_dir}")

        # PyQt5 import
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import Qt
        except ImportError as e:
            logger.error(f"PyQt5 import error: {e}")
            logger.info("Please install PyQt5: pip install PyQt5")
            return 1

        # GStreamer 확인
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            Gst.init(None)
            logger.info("GStreamer initialized successfully")
        except ImportError as e:
            logger.error(f"GStreamer import error: {e}")
            logger.info("Please install GStreamer Python bindings")
            return 1

        # 메인 애플리케이션 import
        try:
            from main_with_playback import NVRMainWindow
        except ImportError as e:
            logger.error(f"Failed to import main application: {e}")
            logger.info("Trying alternative import...")

            # 대체 import 시도
            import main_with_playback
            NVRMainWindow = main_with_playback.NVRMainWindow

        # Qt 애플리케이션 생성
        app = QApplication(sys.argv)
        app.setApplicationName("NVR System")
        app.setStyle("Fusion")

        # 메인 윈도우 생성 및 표시
        logger.info("Creating main window...")
        window = NVRMainWindow()
        window.show()

        logger.success("NVR System started successfully!")

        # 애플리케이션 실행
        return app.exec_()

    except Exception as e:
        import traceback
        print(f"Fatal error: {e}")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())