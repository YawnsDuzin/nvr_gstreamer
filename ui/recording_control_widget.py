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

        # 위젯 전체 스타일 설정
        self.setStyleSheet("""
            QWidget {
                background-color: #252526;
                color: #cccccc;
            }
            QGroupBox {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: 600;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                background-color: #2d2d30;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                color: #cccccc;
            }
            QLabel {
                color: #cccccc;
                background-color: transparent;
            }
            QComboBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #454545;
                border-radius: 3px;
                padding: 4px 8px;
                min-width: 80px;
            }
            QComboBox:hover {
                background-color: #4e4e4e;
                border: 1px solid #007acc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #cccccc;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #454545;
                selection-background-color: #094771;
                selection-color: #ffffff;
            }
            QCheckBox {
                color: #cccccc;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #454545;
                border-radius: 3px;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #007acc;
                background-color: #4e4e4e;
            }
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #0098ff;
            }
        """)

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
        self.camera_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
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
        self.disk_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: #2a2a2a;
                color: #888888;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.disk_label)

        self.setLayout(layout)

        # 스타일 적용
        self._apply_style()

    def _apply_style(self):
        """스타일 적용"""
        # 기본 버튼 스타일
        base_button_style = """
            QPushButton {{
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: #4e4e4e;
                border: 1px solid #007acc;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #007acc;
                border: 1px solid #007acc;
                color: #ffffff;
            }}
            QPushButton:disabled {{
                background-color: #2d2d30;
                color: #6e6e6e;
                border: 1px solid #3c3c3c;
            }}
        """

        # 시작 버튼 스타일 (녹색 강조)
        start_button_style = """
            QPushButton {{
                background-color: #0e6027;
                color: #ffffff;
                border: 1px solid #0e6027;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: #117030;
                border: 1px solid #14803b;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #0d5222;
                border: 1px solid #0d5222;
                color: #ffffff;
            }}
            QPushButton:disabled {{
                background-color: #2d2d30;
                color: #6e6e6e;
                border: 1px solid #3c3c3c;
            }}
        """

        # 정지 버튼 스타일 (빨간색 강조)
        stop_button_style = """
            QPushButton {{
                background-color: #a1260d;
                color: #ffffff;
                border: 1px solid #a1260d;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: #c52a0e;
                border: 1px solid #d13110;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #8a210b;
                border: 1px solid #8a210b;
                color: #ffffff;
            }}
            QPushButton:disabled {{
                background-color: #2d2d30;
                color: #6e6e6e;
                border: 1px solid #3c3c3c;
            }}
        """

        # 일시정지 버튼 스타일 (기본 스타일)
        pause_button_style = base_button_style

        # 스타일 적용
        self.start_all_btn.setStyleSheet(start_button_style)
        self.start_btn.setStyleSheet(start_button_style)
        self.stop_all_btn.setStyleSheet(stop_button_style)
        self.stop_btn.setStyleSheet(stop_button_style)
        self.pause_btn.setStyleSheet(pause_button_style)

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

        logger.debug(f"Added camera to recording control: {camera_name}")

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
            camera_name, rtsp_url = self.cameras[camera_id]

            # 녹화 시작
            file_format = self.format_combo.currentText()
            duration = self._get_duration_seconds()

            if self.recording_manager.start_recording(
                camera_id, camera_name, rtsp_url,
                file_format=file_format,
                file_duration=duration
            ):
                camera_item.set_recording(True)
                self.recording_started.emit(camera_id)
                logger.info(f"Started recording: {camera_name}")
            else:
                QMessageBox.error(self, "Error", f"Failed to start recording for {camera_name}")

    def _stop_recording(self):
        """선택된 카메라 녹화 정지"""
        current_item = self.camera_list.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_id = camera_item.camera_id

        if self.recording_manager.stop_recording(camera_id):
            camera_item.set_recording(False)
            self.recording_stopped.emit(camera_id)
            logger.info(f"Stopped recording: {camera_item.camera_name}")

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
                if self.recording_manager.start_recording(
                    camera_id, camera_name, rtsp_url,
                    file_format=file_format,
                    file_duration=duration
                ):
                    self.camera_items[camera_id].set_recording(True)
                    self.recording_started.emit(camera_id)
                    started_count += 1

        logger.info(f"Started recording for {started_count} cameras")

    def _stop_all_recording(self):
        """모든 카메라 녹화 정지"""
        self.recording_manager.stop_all_recordings()

        for camera_id, item in self.camera_items.items():
            item.set_recording(False)
            self.recording_stopped.emit(camera_id)

        logger.info("Stopped all recordings")

    def _on_item_double_clicked(self, item):
        """아이템 더블클릭 시 녹화 토글"""
        camera_item = item
        camera_id = camera_item.camera_id

        if self.recording_manager.is_recording(camera_id):
            self._stop_recording()
        else:
            self._start_recording()

    def _update_status(self):
        """상태 업데이트"""
        # 녹화 상태 업데이트
        for camera_id, item in self.camera_items.items():
            is_recording = self.recording_manager.is_recording(camera_id)
            item.set_recording(is_recording)

        # 디스크 사용량 업데이트
        disk_info = self.recording_manager.get_disk_usage()
        disk_text = (f"Disk Usage: {disk_info['total_size_mb']:.1f} MB "
                    f"({disk_info['file_count']} files)")
        self.disk_label.setText(disk_text)

        # 일시정지 버튼 텍스트 업데이트
        current_item = self.camera_list.currentItem()
        if current_item:
            status = self.recording_manager.get_recording_status(current_item.camera_id)
            if status == RecordingStatus.PAUSED:
                self.pause_btn.setText("▶ Resume")
            else:
                self.pause_btn.setText("❚❚ Pause")

    def cleanup_old_recordings(self, days: int = 7):
        """오래된 녹화 파일 정리"""
        self.recording_manager.cleanup_old_recordings(days)

    def closeEvent(self, event):
        """종료 시 모든 녹화 정지"""
        self.recording_manager.stop_all_recordings()
        super().closeEvent(event)