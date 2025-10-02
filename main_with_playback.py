"""
메인 애플리케이션 (재생 기능 포함)
통합 NVR 시스템 - 실시간 스트리밍, 녹화, 재생 기능
"""

import sys
from typing import Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QStatusBar, QMessageBox, QToolBar,
    QLabel, QComboBox, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from loguru import logger

# UI 컴포넌트
from ui.grid_view import GridView
from ui.camera_dialog import CameraDialog
from ui.recording_control_widget import RecordingControlWidget
from ui.playback_widget import PlaybackWidget

# 스트리밍 및 녹화
from streaming.pipeline_manager import PipelineManager
from streaming.unified_pipeline import UnifiedPipeline, PipelineMode
from recording.recording_manager import RecordingManager

# 설정
from config.config_manager import ConfigManager


class NVRMainWindow(QMainWindow):
    """NVR 메인 윈도우 (재생 기능 포함)"""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.recording_manager = RecordingManager()
        self.cameras: Dict[str, Dict] = {}
        self.pipelines: Dict[str, PipelineManager] = {}

        self.init_ui()
        self.load_cameras()
        self.setup_timers()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("NVR System - Network Video Recorder")
        self.setGeometry(100, 100, 1400, 900)

        # 메인 위젯
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 메인 레이아웃
        main_layout = QVBoxLayout(main_widget)

        # 툴바 생성
        self.create_toolbar()

        # 탭 위젯
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 라이브 뷰 탭
        self.create_live_tab()

        # 재생 탭
        self.create_playback_tab()

        # 설정 탭
        self.create_settings_tab()

        # 상태바
        self.status_bar = self.statusBar()
        self.update_status("시스템 준비 완료")

    def create_toolbar(self):
        """툴바 생성"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        # 카메라 추가
        add_camera_action = QAction("카메라 추가", self)
        add_camera_action.triggered.connect(self.add_camera)
        toolbar.addAction(add_camera_action)

        toolbar.addSeparator()

        # 전체 녹화 시작/정지
        self.record_all_action = QAction("전체 녹화 시작", self)
        self.record_all_action.triggered.connect(self.toggle_all_recording)
        toolbar.addAction(self.record_all_action)

        toolbar.addSeparator()

        # 새로고침
        refresh_action = QAction("새로고침", self)
        refresh_action.triggered.connect(self.refresh_all)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # 파이프라인 모드 선택
        toolbar.addWidget(QLabel("모드:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["스트리밍", "녹화", "스트리밍+녹화"])
        self.mode_combo.setCurrentText("스트리밍+녹화")
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        toolbar.addWidget(self.mode_combo)

    def create_live_tab(self):
        """라이브 뷰 탭 생성"""
        live_widget = QWidget()
        live_layout = QVBoxLayout(live_widget)

        # 그리드 뷰
        self.grid_view = GridView()
        live_layout.addWidget(self.grid_view)

        # 녹화 컨트롤
        self.recording_control = RecordingControlWidget(self.recording_manager)
        live_layout.addWidget(self.recording_control)

        self.tab_widget.addTab(live_widget, "라이브 뷰")

    def create_playback_tab(self):
        """재생 탭 생성"""
        self.playback_widget = PlaybackWidget()
        self.tab_widget.addTab(self.playback_widget, "재생")

    def create_settings_tab(self):
        """설정 탭 생성"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

        # 카메라 목록
        settings_layout.addWidget(QLabel("등록된 카메라:"))

        # TODO: 카메라 목록 및 설정 UI 추가

        settings_layout.addStretch()

        self.tab_widget.addTab(settings_widget, "설정")

    def setup_timers(self):
        """타이머 설정"""
        # 상태 업데이트 타이머
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_system_status)
        self.status_timer.start(5000)  # 5초마다

        # 녹화 파일 정리 타이머
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_old_recordings)
        self.cleanup_timer.start(3600000)  # 1시간마다

    def load_cameras(self):
        """카메라 목록 로드"""
        cameras = self.config_manager.get_cameras()

        for camera in cameras:
            camera_id = camera['id']
            self.cameras[camera_id] = camera

            # 파이프라인 생성
            self.create_camera_pipeline(camera_id, camera)

    def create_camera_pipeline(self, camera_id: str, camera_info: dict):
        """카메라 파이프라인 생성"""
        try:
            # 현재 모드 가져오기
            mode_text = self.mode_combo.currentText()
            if mode_text == "스트리밍":
                mode = PipelineMode.STREAMING_ONLY
            elif mode_text == "녹화":
                mode = PipelineMode.RECORDING_ONLY
            else:
                mode = PipelineMode.BOTH

            # 통합 파이프라인 사용
            manager = PipelineManager(
                rtsp_url=camera_info['url'],
                use_unified_pipeline=True,
                camera_id=camera_id,
                camera_name=camera_info['name']
            )

            # 파이프라인 생성 및 시작
            if manager.create_unified_pipeline(mode=mode):
                if manager.start_unified():
                    self.pipelines[camera_id] = manager

                    # 그리드 뷰에 추가
                    video_widget = self.grid_view.add_camera(
                        camera_id,
                        camera_info['name']
                    )

                    # 윈도우 핸들 설정
                    if video_widget and manager.unified_pipeline:
                        window_handle = int(video_widget.winId())
                        manager.unified_pipeline.set_window_handle(window_handle)

                    # 녹화 컨트롤에 추가
                    self.recording_control.add_camera(
                        camera_id,
                        camera_info['name'],
                        camera_info['url']
                    )

                    # 자동 녹화 시작 (모드가 녹화 포함인 경우)
                    if mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                        if camera_info.get('auto_record', False):
                            manager.start_recording()

                    logger.success(f"Camera pipeline created: {camera_info['name']}")
                else:
                    logger.error(f"Failed to start pipeline: {camera_info['name']}")
            else:
                logger.error(f"Failed to create pipeline: {camera_info['name']}")

        except Exception as e:
            logger.error(f"Error creating pipeline for {camera_id}: {e}")

    def add_camera(self):
        """카메라 추가"""
        dialog = CameraDialog(self)
        if dialog.exec():
            camera_info = dialog.get_camera_info()

            # 설정에 저장
            self.config_manager.add_camera(camera_info)

            # 카메라 추가
            camera_id = camera_info['id']
            self.cameras[camera_id] = camera_info

            # 파이프라인 생성
            self.create_camera_pipeline(camera_id, camera_info)

            self.update_status(f"카메라 추가됨: {camera_info['name']}")

    def remove_camera(self, camera_id: str):
        """카메라 제거"""
        if camera_id in self.pipelines:
            # 파이프라인 정지
            manager = self.pipelines[camera_id]
            if manager.unified_pipeline:
                manager.stop_unified()
            else:
                manager.stop()

            del self.pipelines[camera_id]

        # 그리드 뷰에서 제거
        self.grid_view.remove_camera(camera_id)

        # 녹화 컨트롤에서 제거
        self.recording_control.remove_camera(camera_id)

        # 설정에서 제거
        if camera_id in self.cameras:
            del self.cameras[camera_id]

        self.config_manager.remove_camera(camera_id)

        self.update_status(f"카메라 제거됨: {camera_id}")

    def toggle_all_recording(self):
        """전체 녹화 시작/정지 토글"""
        # 현재 녹화 중인지 확인
        is_any_recording = any(
            manager.unified_pipeline and manager.unified_pipeline._is_recording
            for manager in self.pipelines.values()
            if manager.unified_pipeline
        )

        if is_any_recording:
            # 전체 녹화 정지
            for camera_id, manager in self.pipelines.items():
                if manager.unified_pipeline and manager.unified_pipeline._is_recording:
                    manager.stop_recording()

            self.record_all_action.setText("전체 녹화 시작")
            self.update_status("전체 녹화 정지됨")
        else:
            # 전체 녹화 시작
            for camera_id, manager in self.pipelines.items():
                if manager.unified_pipeline and not manager.unified_pipeline._is_recording:
                    if manager.unified_pipeline.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                        manager.start_recording()

            self.record_all_action.setText("전체 녹화 정지")
            self.update_status("전체 녹화 시작됨")

    def on_mode_changed(self, mode_text: str):
        """파이프라인 모드 변경"""
        if mode_text == "스트리밍":
            new_mode = PipelineMode.STREAMING_ONLY
        elif mode_text == "녹화":
            new_mode = PipelineMode.RECORDING_ONLY
        else:
            new_mode = PipelineMode.BOTH

        # 모든 파이프라인 모드 변경
        for manager in self.pipelines.values():
            if manager.unified_pipeline:
                # 재시작 필요
                logger.info(f"Changing pipeline mode to: {new_mode.value}")
                # TODO: 실행 중 모드 변경 구현

        self.update_status(f"모드 변경됨: {mode_text}")

    def refresh_all(self):
        """전체 새로고침"""
        # 파이프라인 재시작
        for camera_id, manager in self.pipelines.items():
            if manager.unified_pipeline:
                manager.stop_unified()
                manager.start_unified()

        # 재생 목록 새로고침
        self.playback_widget.scan_recordings()

        self.update_status("시스템 새로고침 완료")

    def update_system_status(self):
        """시스템 상태 업데이트"""
        # 활성 카메라 수
        active_cameras = len(self.pipelines)

        # 녹화 중인 카메라 수
        recording_cameras = sum(
            1 for manager in self.pipelines.values()
            if manager.unified_pipeline and manager.unified_pipeline._is_recording
        )

        # 디스크 사용량
        disk_info = self.recording_manager.get_disk_usage()
        disk_usage = disk_info.get('total_size_mb', 0)

        status_text = (
            f"카메라: {active_cameras} | "
            f"녹화중: {recording_cameras} | "
            f"디스크: {disk_usage:.1f} MB"
        )

        self.update_status(status_text)

    def cleanup_old_recordings(self):
        """오래된 녹화 파일 정리"""
        try:
            retention_days = self.config_manager.get_setting('retention_days', 7)
            self.recording_manager.cleanup_old_recordings(retention_days)
            logger.info(f"Cleaned up recordings older than {retention_days} days")
        except Exception as e:
            logger.error(f"Error cleaning up recordings: {e}")

    def update_status(self, message: str):
        """상태바 업데이트"""
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        """종료 이벤트"""
        reply = QMessageBox.question(
            self,
            "종료 확인",
            "프로그램을 종료하시겠습니까?\n진행 중인 녹화가 중지됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            logger.info("Shutting down NVR system...")

            # 모든 파이프라인 정지
            for manager in self.pipelines.values():
                if manager.unified_pipeline:
                    manager.stop_unified()
                else:
                    manager.stop()

            # 재생 정리
            self.playback_widget.cleanup()

            # 설정 저장
            self.config_manager.save_config()

            event.accept()
        else:
            event.ignore()


def main():
    """메인 함수"""
    # 로거 설정
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    logger.add(
        "logs/nvr_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )

    # Qt 애플리케이션
    app = QApplication(sys.argv)
    app.setApplicationName("NVR System")
    app.setStyle("Fusion")

    # 메인 윈도우
    window = NVRMainWindow()
    window.show()

    logger.info("NVR System started")

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        import traceback
        traceback.print_exc()