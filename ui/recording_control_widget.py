"""
녹화 컨트롤 위젯
녹화 시작/정지 및 상태 표시
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox,
    QLabel, QMenu, QAction,
    QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
from loguru import logger

from ui.theme import ThemedWidget
from core.config import ConfigManager


class RecordingStatusItem(QListWidgetItem):
    """녹화 상태 표시 아이템"""

    def __init__(self, camera_id: str, camera_name: str, enabled: bool = True):
        super().__init__()
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.is_recording = False
        self.is_connected = False
        self.enabled = enabled
        self.update_display()

    def update_display(self):
        """표시 텍스트 업데이트"""
        if not self.enabled:
            # 비활성화: ⚫ 검은 원과 동일한 색상
            status_icon = "⚫"
            status_text = "비활성화"
            color = QColor(100, 100, 100)  # 어두운 회색
        elif self.is_recording:
            # 활성화 + 녹화중: 🔴 빨간 원과 동일한 색상
            status_icon = "🔴"
            status_text = "녹화중"
            color = QColor(255, 0, 0)  # 순수 빨간색
        else:
            # 활성화 + 대기중: ⚪ 흰 원과 동일한 색상
            status_icon = "⚪"
            status_text = "대기중"
            color = QColor(255, 255, 255)  # 흰색

        display_text = f"{status_icon} {self.camera_name} ({self.camera_id}) [{status_text}]"
        self.setText(display_text)
        self.setForeground(color)

    def set_recording(self, is_recording: bool):
        """녹화 상태 설정"""
        self.is_recording = is_recording
        self.update_display()

    def set_connected(self, is_connected: bool):
        """연결 상태 설정"""
        self.is_connected = is_connected
        self.update_display()

    def set_enabled(self, enabled: bool):
        """활성화 상태 설정"""
        self.enabled = enabled
        self.update_display()


class RecordingControlWidget(ThemedWidget):
    """녹화 컨트롤 위젯"""

    # 시그널
    recording_started = pyqtSignal(str)  # camera_id
    recording_stopped = pyqtSignal(str)  # camera_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_items = {}  # camera_id -> RecordingStatusItem
        self.cameras = {}  # camera_id -> (name, rtsp_url)
        self.main_window = None  # MainWindow 참조 (나중에 설정됨)

        self._setup_ui()
        self._setup_context_menu()
        self._setup_timer()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Use theme from main window - no hardcoded style

        # 카메라별 상태 그룹
        status_group = QGroupBox("Camera Recording Status")
        status_layout = QVBoxLayout()

        # 카메라 리스트
        self.camera_list = QListWidget()
        # Use theme from main window - no hardcoded style
        self.camera_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.camera_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.camera_list.customContextMenuRequested.connect(self._show_context_menu)
        status_layout.addWidget(self.camera_list)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 녹화 설정 정보 표시
        settings_info_group = QGroupBox("Recording Settings")
        settings_info_layout = QVBoxLayout()

        # 설정 값들 가져오기
        config_manager = ConfigManager.get_instance()
        recording_config = config_manager.get_recording_config()
        storage_config = config_manager.config.get('storage', {})

        # 저장 경로 (storage.recording_path 사용)
        recording_path = storage_config.get('recording_path', './recordings')
        # 경로를 10자리까지만 표시하고 ... 추가
        display_path = recording_path[:10] + '...' if len(recording_path) > 10 else recording_path
        self.path_label = QLabel(f"Storage Path: {display_path}")
        # 전체 경로를 툴팁으로 표시
        self.path_label.setToolTip(recording_path)
        settings_info_layout.addWidget(self.path_label)

        # 파일 포맷
        file_format = recording_config.get('file_format', 'mp4')
        self.format_label = QLabel(f"File Format: {file_format}")
        settings_info_layout.addWidget(self.format_label)

        # 파일 분할 주기
        rotation_minutes = recording_config.get('rotation_minutes', 10)
        self.rotation_label = QLabel(f"File Rotation: {rotation_minutes} minutes")
        settings_info_layout.addWidget(self.rotation_label)

        settings_info_group.setLayout(settings_info_layout)
        layout.addWidget(settings_info_group)

        # 디스크 사용량 표시
        self.disk_label = QLabel("Disk Usage: Calculating...")
        # Use theme from main window - no hardcoded style
        self.disk_label.setStyleSheet("padding: 5px;")  # Keep padding only
        layout.addWidget(self.disk_label)

        self.setLayout(layout)

    def _setup_context_menu(self):
        """Setup context menu for recording items"""
        self.context_menu = QMenu(self)

        # Start/Stop Recording (Dynamic single action)
        self.recording_action = QAction("Start Recording", self)
        self.recording_action.triggered.connect(self._toggle_recording)
        self.context_menu.addAction(self.recording_action)

    def _show_context_menu(self, pos):
        """Show context menu"""
        item = self.camera_list.itemAt(pos)
        if not item:
            return

        # Update menu actions based on recording state
        camera_item = item
        camera_id = camera_item.camera_id

        # Update Start/Stop text based on recording state
        if self.is_recording(camera_id):
            self.recording_action.setText("Stop Recording")
            self.recording_action.setEnabled(True)
        else:
            self.recording_action.setText("Start Recording")
            # Only enable Start if camera is streaming
            self.recording_action.setEnabled(self.is_streaming(camera_id))

        # Show menu
        self.context_menu.exec_(self.camera_list.mapToGlobal(pos))

    def _toggle_recording(self):
        """Toggle recording state of selected camera"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        if self.is_recording(camera_id):
            # Currently recording, so stop
            self.stop_recording(camera_id)
        else:
            # Currently not recording, so start
            # Check if streaming first
            if not self.is_streaming(camera_id):
                camera_name = self.cameras.get(camera_id, ["Unknown"])[0]
                QMessageBox.warning(
                    self,
                    "Cannot Start Recording",
                    f"Camera '{camera_name}' is not streaming.\n\n"
                    "Recording requires an active streaming pipeline.\n"
                    "Please start streaming first."
                )
                return
            self.start_recording(camera_id)

    def _setup_timer(self):
        """업데이트 타이머 설정 (디스크 사용량만)"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_disk_usage)
        self.update_timer.start(5000)  # 5초마다 디스크 사용량 업데이트

    def add_camera(self, camera_id: str, camera_name: str, rtsp_url: str, enabled: bool = True):
        """
        카메라 추가

        Args:
            camera_id: 카메라 ID
            camera_name: 카메라 이름
            rtsp_url: RTSP URL
            enabled: 카메라 활성화 여부
        """
        if camera_id in self.camera_items:
            logger.warning(f"Camera {camera_id} already exists")
            return

        # 카메라 정보 저장
        self.cameras[camera_id] = (camera_name, rtsp_url)

        # 리스트 아이템 생성
        item = RecordingStatusItem(camera_id, camera_name, enabled)
        self.camera_list.addItem(item)
        self.camera_items[camera_id] = item

        logger.debug(f"Added camera to recording control: {camera_name} ({camera_id})")

    def remove_camera(self, camera_id: str):
        """카메라 제거"""
        if camera_id not in self.camera_items:
            return

        # 녹화 중이면 정지
        if self.is_recording(camera_id):
            self.stop_recording(camera_id)

        # 리스트에서 제거
        item = self.camera_items[camera_id]
        row = self.camera_list.row(item)
        self.camera_list.takeItem(row)

        # 딕셔너리에서 제거
        del self.camera_items[camera_id]
        del self.cameras[camera_id]

        logger.debug(f"Removed camera from recording control: {camera_id}")


    def _start_recording(self):
        """선택된 카메라 녹화 시작"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a camera")
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        if camera_id in self.cameras:
            camera_name = self.cameras[camera_id][0]

            # 스트리밍 중인지 먼저 확인
            if not self.is_streaming(camera_id):
                QMessageBox.warning(
                    self,
                    "Cannot Start Recording",
                    f"Camera '{camera_name}' is not streaming.\n\n"
                    "Recording requires an active streaming pipeline.\n"
                    "Please start streaming first."
                )
                return

            # 녹화 시작
            if self.start_recording(camera_id):
                pass  # 성공 처리는 start_recording에서 함
            else:
                QMessageBox.critical(self, "Error", f"Failed to start recording for {camera_name}")

    def _stop_recording(self):
        """선택된 카메라 녹화 정지"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        self.stop_recording(camera_id)

    def _start_all_recording(self):
        """모든 카메라 녹화 시작"""
        started_count = 0
        skipped_count = 0

        for camera_id, (camera_name, rtsp_url) in self.cameras.items():
            # 이미 녹화 중이면 스킵
            if self.is_recording(camera_id):
                continue

            # 스트리밍 중이 아니면 스킵
            if not self.is_streaming(camera_id):
                logger.warning(f"Skipping {camera_name}: Not streaming")
                skipped_count += 1
                continue

            # 녹화 시작
            if self.start_recording(camera_id):
                started_count += 1

        logger.info(f"Started recording for {started_count} cameras (skipped {skipped_count} not streaming)")

    def _stop_all_recording(self):
        """모든 카메라 녹화 정지"""
        for camera_id in list(self.camera_items.keys()):
            self.stop_recording(camera_id)

        logger.info("Stopped all recordings")

    def _on_item_double_clicked(self, item):
        """아이템 더블클릭 시 녹화 토글"""
        camera_item = item
        camera_id = camera_item.camera_id

        if self.is_recording(camera_id):
            self.stop_recording(camera_id)
        else:
            # 스트리밍 중인지 확인
            if not self.is_streaming(camera_id):
                camera_name = self.cameras.get(camera_id, ["Unknown"])[0]
                QMessageBox.warning(
                    self,
                    "Cannot Start Recording",
                    f"Camera '{camera_name}' is not streaming.\n\n"
                    "Recording requires an active streaming pipeline.\n"
                    "Please start streaming first."
                )
                return

            self.start_recording(camera_id)

    def is_streaming(self, camera_id: str) -> bool:
        """
        카메라 스트리밍 상태 확인

        Args:
            camera_id: 카메라 ID

        Returns:
            스트리밍 중 여부
        """
        # MainWindow 참조 확인
        if not self.main_window or not hasattr(self.main_window, 'camera_list'):
            return False

        camera_stream = self.main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.gst_pipeline:
            return False

        # GstPipeline의 재생 상태 확인
        status = camera_stream.gst_pipeline.get_status()
        return status.get('is_playing', False)

    def start_recording(self, camera_id: str) -> bool:
        """
        특정 카메라 녹화 시작 (통합 녹화 함수)

        Args:
            camera_id: 카메라 ID

        Returns:
            성공 여부
        """
        if camera_id not in self.cameras:
            logger.warning(f"Camera {camera_id} not found in recording control")
            return False

        # MainWindow 참조 확인
        if not self.main_window or not hasattr(self.main_window, 'camera_list'):
            logger.error("MainWindow reference not set or camera_list not found")
            return False

        camera_stream = self.main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.gst_pipeline:
            camera_name = self.cameras[camera_id][0]
            logger.error(f"No pipeline found for camera {camera_id}")
            return False

        # 스트리밍 중인지 확인 (필수 요구사항)
        if not self.is_streaming(camera_id):
            camera_name = self.cameras[camera_id][0]
            logger.warning(f"Cannot start recording for {camera_name}: Camera is not streaming")
            return False

        # GstPipeline의 녹화 시작 (콜백이 자동으로 UI 업데이트)
        result = camera_stream.gst_pipeline.start_recording()
        if result:
            camera_name = self.cameras[camera_id][0]
            logger.info(f"Started recording: {camera_name}")
        else:
            camera_name = self.cameras[camera_id][0]
            logger.error(f"Failed to start recording for {camera_name}")
        return result

    def update_settings_display(self):
        """녹화 설정 정보 표시 업데이트"""
        config_manager = ConfigManager.get_instance()
        recording_config = config_manager.get_recording_config()
        storage_config = config_manager.config.get('storage', {})

        # 저장 경로 업데이트 (storage.recording_path 사용)
        recording_path = storage_config.get('recording_path', './recordings')
        # 경로를 10자리까지만 표시하고 ... 추가
        display_path = recording_path[:10] + '...' if len(recording_path) > 10 else recording_path
        self.path_label.setText(f"Storage Path: {display_path}")
        # 전체 경로를 툴팁으로 표시
        self.path_label.setToolTip(recording_path)

        # 파일 포맷 업데이트
        file_format = recording_config.get('file_format', 'mp4')
        self.format_label.setText(f"File Format: {file_format}")

        # 파일 분할 주기 업데이트
        rotation_minutes = recording_config.get('rotation_minutes', 10)
        self.rotation_label.setText(f"File Rotation: {rotation_minutes} minutes")

    def _update_disk_usage(self):
        """디스크 사용량 업데이트 (타이머에서 호출)"""
        from pathlib import Path
        # 설정에서 녹화 디렉토리 가져오기
        config_manager = ConfigManager.get_instance()
        storage_config = config_manager.config.get('storage', {})
        recordings_path = storage_config.get('recording_path', './recordings')
        recordings_dir = Path(recordings_path)

        if recordings_dir.exists():
            total_size = sum(f.stat().st_size for f in recordings_dir.rglob("*.*") if f.is_file())
            file_count = len(list(recordings_dir.rglob("*.*")))
            disk_text = f"Disk Usage: {total_size / (1024*1024):.1f} MB ({file_count} files)"
        else:
            disk_text = "Disk Usage: 0 MB (0 files)"
        self.disk_label.setText(disk_text)

    def update_recording_status(self, camera_id: str, is_recording: bool):
        """
        녹화 상태 업데이트 (콜백에서 호출)

        Args:
            camera_id: 카메라 ID
            is_recording: 녹화 중 여부
        """
        if camera_id in self.camera_items:
            item = self.camera_items[camera_id]
            if item.is_recording != is_recording:
                item.set_recording(is_recording)
                logger.info(f"[RECORDING SYNC] Recording status updated for {camera_id}: {is_recording}")
        else:
            logger.warning(f"Camera {camera_id} not found in recording control items")

    def stop_recording(self, camera_id: str) -> bool:
        """
        특정 카메라 녹화 정지 (통합 녹화 함수)

        Args:
            camera_id: 카메라 ID

        Returns:
            성공 여부
        """
        # MainWindow 참조 확인
        if not self.main_window or not hasattr(self.main_window, 'camera_list'):
            logger.error("MainWindow reference not set or camera_list not found")
            return False

        camera_stream = self.main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.gst_pipeline:
            logger.error(f"No pipeline found for camera {camera_id}")
            return False

        # GstPipeline의 녹화 정지 (콜백이 자동으로 UI 업데이트)
        result = camera_stream.gst_pipeline.stop_recording()
        if result:
            logger.info(f"Stopped recording: {camera_id}")
        return result

    def cleanup_old_recordings(self, days: int = 7):
        """오래된 녹화 파일 정리"""
        import time
        from pathlib import Path

        # 설정에서 녹화 디렉토리 가져오기
        config_manager = ConfigManager.get_instance()
        storage_config = config_manager.config.get('storage', {})
        recordings_path = storage_config.get('recording_path', './recordings')
        recordings_dir = Path(recordings_path)

        if not recordings_dir.exists():
            return

        cutoff_time = time.time() - (days * 24 * 3600)
        deleted_count = 0

        for file_path in recordings_dir.rglob("*.*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old recording files")

    def is_recording(self, camera_id: str) -> bool:
        """
        카메라 녹화 상태 확인 (외부 호출용)

        Args:
            camera_id: 카메라 ID

        Returns:
            녹화 중 여부
        """
        # MainWindow 참조 확인
        if not self.main_window or not hasattr(self.main_window, 'camera_list'):
            return False

        camera_stream = self.main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.gst_pipeline:
            return False

        # GstPipeline의 녹화 상태 확인
        status = camera_stream.gst_pipeline.get_status()
        return status.get('is_recording', False)

    def closeEvent(self, event):
        """종료 시 모든 녹화 정지"""
        # GstPipeline의 녹화 정지는 main_window에서 처리
        super().closeEvent(event)