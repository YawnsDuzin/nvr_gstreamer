"""
녹화 컨트롤 위젯
녹화 시작/정지 및 상태 표시
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont
from loguru import logger

from recording.recording_manager import RecordingManager, RecordingStatus


class RecordingStatusItem(QListWidgetItem):
    """녹화 상태 표시 아이템"""

    def __init__(self, camera_id: str, camera_name: str):
        super().__init__()
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.is_recording = False
        self.update_display()

    def update_display(self):
        """표시 텍스트 업데이트"""
        status_icon = "🔴" if self.is_recording else "⚫"
        status_text = "REC" if self.is_recording else "STOP"

        display_text = f"{status_icon} {self.camera_name} [{status_text}]"
        self.setText(display_text)

        # 색상 설정
        if self.is_recording:
            self.setForeground(QColor(255, 100, 100))  # 빨간색
        else:
            self.setForeground(QColor(200, 200, 200))  # 회색

    def set_recording(self, is_recording: bool):
        """녹화 상태 설정"""
        self.is_recording = is_recording
        self.update_display()


class RecordingControlWidget(QWidget):
    """녹화 컨트롤 위젯"""

    # 시그널
    recording_started = pyqtSignal(str)  # camera_id
    recording_stopped = pyqtSignal(str)  # camera_id

    def __init__(self, recording_manager: RecordingManager = None, parent=None):
        super().__init__(parent)
        self.recording_manager = recording_manager or RecordingManager()
        self.camera_items = {}  # camera_id -> RecordingStatusItem
        self.cameras = {}  # camera_id -> (name, rtsp_url)

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Use theme from main window - no hardcoded style

        # 전체 컨트롤 그룹
        control_group = QGroupBox("Recording Controls")
        control_layout = QVBoxLayout()

        # 전체 녹화 버튼들
        button_layout = QHBoxLayout()

        self.start_all_btn = QPushButton("▶ Start All")
        self.start_all_btn.clicked.connect(self._start_all_recording)
        button_layout.addWidget(self.start_all_btn)

        self.stop_all_btn = QPushButton("■ Stop All")
        self.stop_all_btn.clicked.connect(self._stop_all_recording)
        button_layout.addWidget(self.stop_all_btn)

        control_layout.addLayout(button_layout)

        # 녹화 설정
        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "avi"])
        settings_layout.addWidget(self.format_combo)

        settings_layout.addWidget(QLabel("Duration:"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["5 min", "10 min", "30 min", "60 min"])
        self.duration_combo.setCurrentIndex(1)  # 기본 10분
        settings_layout.addWidget(self.duration_combo)

        settings_layout.addStretch()

        control_layout.addLayout(settings_layout)

        # 연속 녹화 체크박스
        self.continuous_cb = QCheckBox("Continuous Recording")
        self.continuous_cb.setToolTip("자동으로 파일을 분할하며 계속 녹화")
        control_layout.addWidget(self.continuous_cb)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 카메라별 상태 그룹
        status_group = QGroupBox("Camera Recording Status")
        status_layout = QVBoxLayout()

        # 카메라 리스트
        self.camera_list = QListWidget()
        # Use theme from main window - no hardcoded style
        self.camera_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        status_layout.addWidget(self.camera_list)

        # 개별 컨트롤 버튼
        individual_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.clicked.connect(self._start_recording)
        individual_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._stop_recording)
        individual_layout.addWidget(self.stop_btn)

        self.pause_btn = QPushButton("❚❚ Pause")
        self.pause_btn.clicked.connect(self._pause_recording)
        individual_layout.addWidget(self.pause_btn)

        status_layout.addLayout(individual_layout)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 디스크 사용량 표시
        self.disk_label = QLabel("Disk Usage: Calculating...")
        # Use theme from main window - no hardcoded style
        self.disk_label.setStyleSheet("padding: 5px;")  # Keep padding only
        layout.addWidget(self.disk_label)

        self.setLayout(layout)

    def _setup_timer(self):
        """업데이트 타이머 설정"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(2000)  # 2초마다 업데이트

    def add_camera(self, camera_id: str, camera_name: str, rtsp_url: str):
        """
        카메라 추가

        Args:
            camera_id: 카메라 ID
            camera_name: 카메라 이름
            rtsp_url: RTSP URL
        """
        if camera_id in self.camera_items:
            logger.warning(f"Camera {camera_id} already exists")
            return

        # 카메라 정보 저장
        self.cameras[camera_id] = (camera_name, rtsp_url)

        # 리스트 아이템 생성
        item = RecordingStatusItem(camera_id, camera_name)
        self.camera_list.addItem(item)
        self.camera_items[camera_id] = item

        logger.debug(f"Added camera to recording control: {camera_name} ({camera_id})")

    def remove_camera(self, camera_id: str):
        """카메라 제거"""
        if camera_id not in self.camera_items:
            return

        # 녹화 중이면 정지
        if self.recording_manager.is_recording(camera_id):
            self.recording_manager.stop_recording(camera_id)

        # 리스트에서 제거
        item = self.camera_items[camera_id]
        row = self.camera_list.row(item)
        self.camera_list.takeItem(row)

        # 딕셔너리에서 제거
        del self.camera_items[camera_id]
        del self.cameras[camera_id]
        
        logger.debug(f"Removed camera from recording control: {camera_id}")

    def _get_duration_seconds(self) -> int:
        """선택된 녹화 시간 반환 (초)"""
        duration_text = self.duration_combo.currentText()
        if "5 min" in duration_text:
            return 300
        elif "10 min" in duration_text:
            return 600
        elif "30 min" in duration_text:
            return 1800
        elif "60 min" in duration_text:
            return 3600
        return 600  # 기본 10분

    def _start_recording(self):
        """선택된 카메라 녹화 시작"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a camera")
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        if camera_id in self.cameras:
            if self.start_recording(camera_id):
                pass  # 성공 처리는 start_recording에서 함
            else:
                camera_name = self.cameras[camera_id][0]
                QMessageBox.error(self, "Error", f"Failed to start recording for {camera_name}")

    def _stop_recording(self):
        """선택된 카메라 녹화 정지"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        self.stop_recording(camera_id)

    def _pause_recording(self):
        """선택된 카메라 녹화 일시정지"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            return

        camera_id = current_item.camera_id
        status = self.recording_manager.get_recording_status(camera_id)

        if status == RecordingStatus.RECORDING:
            self.recording_manager.pause_recording(camera_id)
            self.pause_btn.setText("▶ Resume")
        elif status == RecordingStatus.PAUSED:
            self.recording_manager.resume_recording(camera_id)
            self.pause_btn.setText("❚❚ Pause")

    def _start_all_recording(self):
        """모든 카메라 녹화 시작"""
        file_format = self.format_combo.currentText()
        duration = self._get_duration_seconds()

        started_count = 0
        for camera_id, (camera_name, rtsp_url) in self.cameras.items():
            if not self.recording_manager.is_recording(camera_id):
                if self.start_recording(camera_id):
                    started_count += 1

        logger.info(f"Started recording for {started_count} cameras")

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
            self.start_recording(camera_id)

    def start_recording(self, camera_id: str) -> bool:
        """
        특정 카메라 녹화 시작 (외부 호출용)
        
        Args:
            camera_id: 카메라 ID
            
        Returns:
            성공 여부
        """
        if camera_id not in self.cameras:
            logger.warning(f"Camera {camera_id} not found in recording control")
            return False
            
        # UnifiedPipeline을 사용하는 카메라 스트림 찾기
        from ui.main_window import MainWindow
        main_window = None
        for widget in self.parent().parent().children():
            if hasattr(widget, 'camera_list'):
                main_window = widget
                break
        
        if not main_window or not hasattr(main_window, 'camera_list'):
            logger.error("Cannot find main window or camera list")
            return False
            
        camera_stream = main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.pipeline_manager:
            logger.error(f"No pipeline manager found for camera {camera_id}")
            return False
            
        # UnifiedPipeline의 녹화 시작
        if camera_stream.pipeline_manager.start_recording():
            if camera_id in self.camera_items:
                self.camera_items[camera_id].set_recording(True)
            self.recording_started.emit(camera_id)
            camera_name = self.cameras[camera_id][0]
            logger.info(f"Started recording: {camera_name}")
            return True
        else:
            camera_name = self.cameras[camera_id][0]
            logger.error(f"Failed to start recording for {camera_name}")
            return False

    def _update_status(self):
        """상태 업데이트"""
        # 녹화 상태 업데이트
        for camera_id, item in self.camera_items.items():
            is_recording = self.is_recording(camera_id)
            item.set_recording(is_recording)

        # 디스크 사용량 업데이트 (기본값 표시)
        from pathlib import Path
        recordings_dir = Path("recordings")
        if recordings_dir.exists():
            total_size = sum(f.stat().st_size for f in recordings_dir.rglob("*.*") if f.is_file())
            file_count = len(list(recordings_dir.rglob("*.*")))
            disk_text = f"Disk Usage: {total_size / (1024*1024):.1f} MB ({file_count} files)"
        else:
            disk_text = "Disk Usage: 0 MB (0 files)"
        self.disk_label.setText(disk_text)

        # 일시정지 버튼 텍스트 업데이트 (기본값)
        self.pause_btn.setText("❚❚ Pause")

    def stop_recording(self, camera_id: str) -> bool:
        """
        특정 카메라 녹화 정지 (외부 호출용)
        
        Args:
            camera_id: 카메라 ID
            
        Returns:
            성공 여부
        """
        # UnifiedPipeline을 사용하는 카메라 스트림 찾기
        from ui.main_window import MainWindow
        main_window = None
        for widget in self.parent().parent().children():
            if hasattr(widget, 'camera_list'):
                main_window = widget
                break
        
        if not main_window or not hasattr(main_window, 'camera_list'):
            logger.error("Cannot find main window or camera list")
            return False
            
        camera_stream = main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.pipeline_manager:
            logger.error(f"No pipeline manager found for camera {camera_id}")
            return False
            
        # UnifiedPipeline의 녹화 정지
        if camera_stream.pipeline_manager.stop_recording():
            if camera_id in self.camera_items:
                self.camera_items[camera_id].set_recording(False)
            self.recording_stopped.emit(camera_id)
            logger.info(f"Stopped recording: {camera_id}")
            return True
        return False

    def cleanup_old_recordings(self, days: int = 7):
        """오래된 녹화 파일 정리"""
        # 기본 녹화 디렉토리 정리
        import time
        from pathlib import Path
        
        recordings_dir = Path("recordings")
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
        # UnifiedPipeline을 사용하는 카메라 스트림 찾기
        from ui.main_window import MainWindow
        main_window = None
        for widget in self.parent().parent().children():
            if hasattr(widget, 'camera_list'):
                main_window = widget
                break
        
        if not main_window or not hasattr(main_window, 'camera_list'):
            return False
            
        camera_stream = main_window.camera_list.get_camera_stream(camera_id)
        if not camera_stream or not camera_stream.pipeline_manager:
            return False
            
        # UnifiedPipeline의 녹화 상태 확인
        status = camera_stream.pipeline_manager.get_status()
        return status.get('is_recording', False)

    def closeEvent(self, event):
        """종료 시 모든 녹화 정지"""
        # UnifiedPipeline의 녹화 정지는 main_window에서 처리
        super().closeEvent(event)