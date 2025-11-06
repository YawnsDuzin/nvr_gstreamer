"""
Cameras Settings Tab
카메라 설정 탭 (cameras 항목)
"""

from PyQt5.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QListWidget, QCheckBox, QComboBox,
    QMessageBox, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class CamerasSettingsTab(BaseSettingsTab):
    """
    카메라 설정 탭
    - 좌측: 카메라 리스트
    - 우측: 선택된 카메라 상세 설정
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self.current_camera_index = -1
        self.cameras_data = []  # 임시 카메라 데이터 저장
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QHBoxLayout(self)

        # 좌측: 카메라 리스트
        left_widget = self._create_camera_list_panel()
        left_widget.setMaximumWidth(250)
        layout.addWidget(left_widget)

        # 우측: 카메라 상세 설정
        right_widget = self._create_camera_detail_panel()
        layout.addWidget(right_widget, 1)

        logger.debug("CamerasSettingsTab UI setup complete")

    def _create_camera_list_panel(self) -> QWidget:
        """카메라 리스트 패널 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Camera List"))

        # Camera list
        self.camera_list = QListWidget()
        self.camera_list.currentRowChanged.connect(self._on_camera_selected)
        layout.addWidget(self.camera_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_camera)
        self.add_btn.setToolTip("Add new camera")

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_camera)
        self.delete_btn.setToolTip("Delete selected camera")

        self.duplicate_btn = QPushButton("Copy")
        self.duplicate_btn.clicked.connect(self._duplicate_camera)
        self.duplicate_btn.setToolTip("Duplicate selected camera")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.duplicate_btn)
        layout.addLayout(btn_layout)

        return widget

    def _create_camera_detail_panel(self) -> QWidget:
        """카메라 상세 설정 패널 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Camera Settings"))

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Basic Info Group
        basic_group = QGroupBox("Basic Information")
        basic_form = QFormLayout()

        self.camera_id_edit = QLineEdit()
        self.camera_id_edit.setPlaceholderText("e.g., cam_01")
        basic_form.addRow("Camera ID:", self.camera_id_edit)

        self.camera_name_edit = QLineEdit()
        self.camera_name_edit.setPlaceholderText("e.g., Front Door")
        basic_form.addRow("Name:", self.camera_name_edit)

        self.rtsp_url_edit = QLineEdit()
        self.rtsp_url_edit.setPlaceholderText("rtsp://192.168.1.100:554/stream")
        basic_form.addRow("RTSP URL:", self.rtsp_url_edit)

        self.enabled_cb = QCheckBox("Enable Camera")
        self.enabled_cb.setChecked(True)
        basic_form.addRow(self.enabled_cb)

        basic_group.setLayout(basic_form)
        scroll_layout.addWidget(basic_group)

        # Authentication Group
        auth_group = QGroupBox("Authentication (Optional)")
        auth_form = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        auth_form.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password")
        auth_form.addRow("Password:", self.password_edit)

        auth_group.setLayout(auth_form)
        scroll_layout.addWidget(auth_group)

        # PTZ Group
        ptz_group = QGroupBox("PTZ Settings")
        ptz_form = QFormLayout()

        self.ptz_type_combo = QComboBox()
        self.ptz_type_combo.addItems(["None", "HIK", "ONVIF"])
        self.ptz_type_combo.currentTextChanged.connect(self._on_ptz_type_changed)
        ptz_form.addRow("PTZ Type:", self.ptz_type_combo)

        self.ptz_port_edit = QLineEdit()
        self.ptz_port_edit.setPlaceholderText("e.g., 80")
        ptz_form.addRow("PTZ Port:", self.ptz_port_edit)

        self.ptz_channel_edit = QLineEdit()
        self.ptz_channel_edit.setPlaceholderText("e.g., 1")
        ptz_form.addRow("PTZ Channel:", self.ptz_channel_edit)

        ptz_group.setLayout(ptz_form)
        scroll_layout.addWidget(ptz_group)

        # Video Transform Group
        transform_group = QGroupBox("Video Transform")
        transform_layout = QVBoxLayout()

        self.transform_enabled_cb = QCheckBox("Enable Video Transform")
        self.transform_enabled_cb.toggled.connect(self._toggle_transform_controls)
        transform_layout.addWidget(self.transform_enabled_cb)

        transform_form = QFormLayout()

        self.flip_combo = QComboBox()
        self.flip_combo.addItems(["None", "Horizontal", "Vertical", "Both"])
        self.flip_combo.setToolTip("Flip video horizontally, vertically, or both")
        transform_form.addRow("Flip:", self.flip_combo)

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setToolTip("Rotate video clockwise")
        transform_form.addRow("Rotation:", self.rotation_combo)

        transform_layout.addLayout(transform_form)
        transform_group.setLayout(transform_layout)
        scroll_layout.addWidget(transform_group)

        # Startup Options Group
        startup_group = QGroupBox("Startup Options")
        startup_layout = QVBoxLayout()

        self.streaming_start_cb = QCheckBox("Start Streaming on Startup")
        self.streaming_start_cb.setToolTip("Automatically start streaming when application starts")
        startup_layout.addWidget(self.streaming_start_cb)

        self.recording_start_cb = QCheckBox("Start Recording on Startup")
        self.recording_start_cb.setToolTip("Automatically start recording when application starts")
        startup_layout.addWidget(self.recording_start_cb)

        startup_group.setLayout(startup_layout)
        scroll_layout.addWidget(startup_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.apply_camera_btn = QPushButton("Apply Changes")
        self.apply_camera_btn.clicked.connect(self._apply_camera_changes)
        self.apply_camera_btn.setToolTip("Apply changes to selected camera")
        btn_layout.addWidget(self.apply_camera_btn)

        layout.addLayout(btn_layout)

        # Store widgets for enable/disable
        self._detail_widgets = [
            self.camera_id_edit, self.camera_name_edit, self.rtsp_url_edit,
            self.enabled_cb, self.username_edit, self.password_edit,
            self.ptz_type_combo, self.ptz_port_edit, self.ptz_channel_edit,
            self.transform_enabled_cb, self.flip_combo, self.rotation_combo,
            self.streaming_start_cb, self.recording_start_cb,
            self.apply_camera_btn
        ]

        # Initial state: disable detail panel
        self._set_detail_panel_enabled(False)

        return widget

    def _on_ptz_type_changed(self, ptz_type: str):
        """PTZ 타입 변경 시 포트/채널 필드 활성화"""
        enabled = ptz_type != "None"
        self.ptz_port_edit.setEnabled(enabled)
        self.ptz_channel_edit.setEnabled(enabled)

    def _toggle_transform_controls(self, checked: bool):
        """Video Transform 활성화/비활성화 시 컨트롤 토글"""
        self.flip_combo.setEnabled(checked)
        self.rotation_combo.setEnabled(checked)

    def _set_detail_panel_enabled(self, enabled: bool):
        """상세 패널 활성화/비활성화"""
        for widget in self._detail_widgets:
            widget.setEnabled(enabled)

    def _add_camera(self):
        """카메라 추가"""
        new_camera = {
            "camera_id": f"cam_{len(self.cameras_data) + 1:02d}",
            "name": f"New Camera {len(self.cameras_data) + 1}",
            "rtsp_url": "",
            "enabled": True,
            "username": None,
            "password": None,
            "ptz_type": None,
            "ptz_port": None,
            "ptz_channel": None,
            "video_transform": {
                "enabled": False,
                "flip": "none",
                "rotation": 0
            },
            "streaming_enabled_start": False,
            "recording_enabled_start": False
        }

        self.cameras_data.append(new_camera)
        self.camera_list.addItem(new_camera["name"])
        self.camera_list.setCurrentRow(len(self.cameras_data) - 1)

        logger.debug(f"Camera added: {new_camera['camera_id']}")

    def _delete_camera(self):
        """카메라 삭제"""
        if self.current_camera_index < 0:
            return

        camera_name = self.cameras_data[self.current_camera_index]["name"]

        reply = QMessageBox.question(
            self, "Delete Camera",
            f"Delete camera '{camera_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            del self.cameras_data[self.current_camera_index]
            self.camera_list.takeItem(self.current_camera_index)

            if len(self.cameras_data) == 0:
                self._set_detail_panel_enabled(False)
                self.current_camera_index = -1

            logger.debug(f"Camera deleted: {camera_name}")

    def _duplicate_camera(self):
        """카메라 복제"""
        if self.current_camera_index < 0:
            return

        source_camera = self.cameras_data[self.current_camera_index].copy()
        source_camera["camera_id"] = f"cam_{len(self.cameras_data) + 1:02d}"
        source_camera["name"] = f"{source_camera['name']} (Copy)"

        self.cameras_data.append(source_camera)
        self.camera_list.addItem(source_camera["name"])
        self.camera_list.setCurrentRow(len(self.cameras_data) - 1)

        logger.debug(f"Camera duplicated: {source_camera['camera_id']}")

    def _on_camera_selected(self, index: int):
        """카메라 선택 시 상세 정보 로드"""
        if index < 0 or index >= len(self.cameras_data):
            self._set_detail_panel_enabled(False)
            return

        self.current_camera_index = index
        camera = self.cameras_data[index]

        # Enable detail panel
        self._set_detail_panel_enabled(True)

        # Load data
        self.camera_id_edit.setText(camera.get("camera_id", ""))
        self.camera_name_edit.setText(camera.get("name", ""))
        self.rtsp_url_edit.setText(camera.get("rtsp_url", ""))
        self.enabled_cb.setChecked(camera.get("enabled", True))

        self.username_edit.setText(camera.get("username") or "")
        self.password_edit.setText(camera.get("password") or "")

        ptz_type = camera.get("ptz_type") or "None"
        idx = self.ptz_type_combo.findText(ptz_type)
        if idx >= 0:
            self.ptz_type_combo.setCurrentIndex(idx)
        else:
            self.ptz_type_combo.setCurrentIndex(0)

        self.ptz_port_edit.setText(camera.get("ptz_port") or "")
        self.ptz_channel_edit.setText(camera.get("ptz_channel") or "")

        # Load video transform settings
        transform = camera.get("video_transform", {})
        self.transform_enabled_cb.setChecked(transform.get("enabled", False))

        # Map flip string to combo index
        # ⭐ IMPORTANT: JSON에서 대소문자 혼용 가능하므로 lower()로 정규화
        flip_value = transform.get("flip", "none").lower()  # 소문자로 변환
        flip_map = {"none": 0, "horizontal": 1, "vertical": 2, "both": 3}
        flip_index = flip_map.get(flip_value, 0)
        self.flip_combo.setCurrentIndex(flip_index)

        # Map rotation degree to combo index
        rotation_value = transform.get("rotation", 0)
        rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
        rotation_index = rotation_map.get(rotation_value, 0)
        self.rotation_combo.setCurrentIndex(rotation_index)

        self.streaming_start_cb.setChecked(camera.get("streaming_enabled_start", False))
        self.recording_start_cb.setChecked(camera.get("recording_enabled_start", False))

        logger.debug(f"Camera selected: {camera.get('camera_id')}")

    def _apply_camera_changes(self):
        """현재 카메라 변경사항 적용"""
        if self.current_camera_index < 0:
            return

        camera = self.cameras_data[self.current_camera_index]

        # Update data
        camera["camera_id"] = self.camera_id_edit.text().strip()
        camera["name"] = self.camera_name_edit.text().strip()
        camera["rtsp_url"] = self.rtsp_url_edit.text().strip()
        camera["enabled"] = self.enabled_cb.isChecked()

        camera["username"] = self.username_edit.text().strip() or None
        camera["password"] = self.password_edit.text().strip() or None

        ptz_type = self.ptz_type_combo.currentText()
        camera["ptz_type"] = ptz_type if ptz_type != "None" else None
        camera["ptz_port"] = self.ptz_port_edit.text().strip() or None
        camera["ptz_channel"] = self.ptz_channel_edit.text().strip() or None

        # Update video transform settings
        if self.transform_enabled_cb.isChecked():
            # Map flip combo index to string value
            flip_map = {0: 'none', 1: 'horizontal', 2: 'vertical', 3: 'both'}
            flip_value = flip_map.get(self.flip_combo.currentIndex(), 'none')

            # Map rotation combo index to degree value
            rotation_map = {0: 0, 1: 90, 2: 180, 3: 270}
            rotation_value = rotation_map.get(self.rotation_combo.currentIndex(), 0)

            camera["video_transform"] = {
                'enabled': True,
                'flip': flip_value,
                'rotation': rotation_value
            }
        else:
            camera["video_transform"] = {
                'enabled': False,
                'flip': 'none',
                'rotation': 0
            }

        camera["streaming_enabled_start"] = self.streaming_start_cb.isChecked()
        camera["recording_enabled_start"] = self.recording_start_cb.isChecked()

        # Update list item
        self.camera_list.item(self.current_camera_index).setText(camera["name"])

        QMessageBox.information(self, "Success", f"Camera '{camera['name']}' updated.")
        logger.info(f"Camera updated: {camera['camera_id']}")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            cameras = config.get("cameras", [])

            self.cameras_data = [cam.copy() for cam in cameras]
            self.camera_list.clear()

            for camera in self.cameras_data:
                self.camera_list.addItem(camera.get("name", "Unknown"))

            if len(self.cameras_data) > 0:
                self.camera_list.setCurrentRow(0)

            # Store original data
            self._store_original_data({
                "cameras": [cam.copy() for cam in cameras]
            })

            logger.debug("CamerasSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load camera settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            # Apply current camera changes first
            if self.current_camera_index >= 0:
                self._apply_camera_changes()

            config = self.config_manager.config
            config["cameras"] = self.cameras_data

            self.config_manager.save_config()

            logger.info(f"Camera settings saved: {len(self.cameras_data)} cameras")
            return True

        except Exception as e:
            logger.error(f"Failed to save camera settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        # Camera ID uniqueness check
        camera_ids = [cam["camera_id"] for cam in self.cameras_data]
        if len(camera_ids) != len(set(camera_ids)):
            return False, "Duplicate camera IDs found"

        # Required fields check
        for camera in self.cameras_data:
            if not camera.get("camera_id"):
                return False, "Camera ID is required for all cameras"
            if not camera.get("name"):
                return False, "Camera name is required for all cameras"
            if not camera.get("rtsp_url"):
                return False, f"RTSP URL is required for camera '{camera['name']}'"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            current = {"cameras": self.cameras_data}

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
