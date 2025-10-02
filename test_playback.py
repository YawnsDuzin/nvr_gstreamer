"""
재생 기능 테스트
녹화된 파일의 재생 기능을 테스트
"""

import sys
import time
from pathlib import Path
from loguru import logger
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtCore import Qt

from ui.playback_widget import PlaybackWidget
from playback.playback_manager import PlaybackManager, PlaybackState


def test_playback_manager():
    """재생 관리자 테스트"""
    logger.info("=== Testing Playback Manager ===")

    # 재생 관리자 생성
    manager = PlaybackManager(recordings_dir="recordings")

    # 녹화 파일 스캔
    recordings = manager.scan_recordings()
    logger.info(f"Found {len(recordings)} recording files")

    for rec in recordings[:5]:  # 처음 5개만 표시
        logger.info(f"  - {rec.camera_id}: {rec.file_name} "
                   f"({rec.formatted_duration}, {rec.formatted_size})")

    # 첫 번째 파일 재생 테스트
    if recordings:
        first_file = recordings[0]
        logger.info(f"Testing playback of: {first_file.file_name}")

        # 재생 시작
        if manager.play_file(first_file.file_path):
            logger.success("Playback started")

            # 재생 정보
            pipeline = manager.playback_pipeline
            if pipeline:
                duration = pipeline.get_duration()
                logger.info(f"Duration: {duration:.2f} seconds")

                # 5초 재생
                time.sleep(5)

                # 중간 지점으로 이동
                middle = duration / 2
                if manager.seek(middle):
                    logger.info(f"Seeked to {middle:.2f} seconds")

                # 2초 더 재생
                time.sleep(2)

                # 일시정지
                if manager.pause_playback():
                    logger.info("Playback paused")
                    time.sleep(2)

                # 재개
                if manager.resume_playback():
                    logger.info("Playback resumed")
                    time.sleep(2)

                # 2배속 재생
                if manager.set_playback_rate(2.0):
                    logger.info("Playback rate set to 2.0x")
                    time.sleep(3)

            # 정지
            manager.stop_playback()
            logger.info("Playback stopped")
        else:
            logger.error("Failed to start playback")


class TestPlaybackWindow(QMainWindow):
    """재생 테스트 윈도우"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("NVR Playback Test")
        self.setGeometry(100, 100, 1200, 800)

        # 탭 위젯
        tab_widget = QTabWidget()

        # 재생 탭
        self.playback_widget = PlaybackWidget()
        tab_widget.addTab(self.playback_widget, "재생")

        self.setCentralWidget(tab_widget)

        # 상태바
        self.statusBar().showMessage("재생 테스트 준비 완료")

    def closeEvent(self, event):
        """종료 이벤트"""
        logger.info("Cleaning up...")
        self.playback_widget.cleanup()
        event.accept()


def test_playback_ui():
    """재생 UI 테스트"""
    logger.info("=== Testing Playback UI ===")

    app = QApplication(sys.argv)

    # 스타일 설정
    app.setStyle("Fusion")

    # 메인 윈도우
    window = TestPlaybackWindow()
    window.show()

    sys.exit(app.exec_())


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Test playback functionality")
    parser.add_argument("--mode", choices=["manager", "ui"],
                       default="ui", help="Test mode")
    parser.add_argument("--recordings-dir", type=str,
                       default="recordings",
                       help="Recordings directory")

    args = parser.parse_args()

    # 로거 설정
    logger.remove()
    logger.add(sys.stdout, level="DEBUG",
              format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

    if args.mode == "manager":
        test_playback_manager()
    else:
        test_playback_ui()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()