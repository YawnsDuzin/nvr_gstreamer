# 설정 다이얼로그 구현 계획

## 개요
IT_RNVR.json의 모든 설정 항목을 체계적으로 관리할 수 있는 통합 설정 다이얼로그를 구현합니다.

## 1. 전체 구조 설계

### 1.1 아키텍처 패턴
- **QTabWidget 기반 탭 구조**: 각 설정 카테고리를 독립적인 탭으로 구성
- **ConfigManager 통합**: 싱글톤 패턴의 ConfigManager와 연동
- **실시간 검증**: 입력 값 변경 시 즉시 유효성 검사
- **부분 저장**: 각 탭의 Apply 버튼으로 해당 섹션만 저장 가능

### 1.2 파일 구조
```
ui/
├── settings_dialog.py          # 메인 설정 다이얼로그 (QTabWidget)
├── settings/                   # 설정 탭 위젯들
│   ├── __init__.py
│   ├── basic_settings_tab.py     # Basic Setting 탭
│   ├── cameras_settings_tab.py   # Cameras Setting 탭
│   ├── streaming_settings_tab.py # Streaming Setting 탭
│   ├── recording_settings_tab.py # Recording Setting 탭
│   ├── backup_settings_tab.py    # Backup Setting 탭
│   ├── storage_settings_tab.py   # Storage Setting 탭
│   ├── hotkey_settings_tab.py    # Hot_Key Setting 탭
│   └── ptz_key_settings_tab.py   # PTZ_Key Setting 탭
└── widgets/                    # 재사용 가능한 커스텀 위젯
    ├── key_sequence_edit.py      # 키 바인딩 입력 위젯
    └── color_picker_button.py    # 색상 선택 버튼
```

### 1.3 클래스 다이어그램
```
SettingsDialog (QDialog)
├── QTabWidget
│   ├── BasicSettingsTab (BaseSettingsTab)
│   ├── CamerasSettingsTab (BaseSettingsTab)
│   ├── StreamingSettingsTab (BaseSettingsTab)
│   ├── RecordingSettingsTab (BaseSettingsTab)
│   ├── BackupSettingsTab (BaseSettingsTab)
│   ├── StorageSettingsTab (BaseSettingsTab)
│   ├── HotKeySettingsTab (BaseSettingsTab)
│   └── PTZKeySettingsTab (BaseSettingsTab)
└── QDialogButtonBox (OK, Cancel, Apply)

BaseSettingsTab (추상 클래스)
├── load_settings()      # 설정 로드 (추상 메서드)
├── save_settings()      # 설정 저장 (추상 메서드)
├── validate_settings()  # 설정 검증 (추상 메서드)
└── has_changes()        # 변경 사항 확인
```

---

## 2. 각 탭별 상세 구현 계획

### 2.1 Basic Settings Tab

#### 구현 항목
1. **App 섹션** (IT_RNVR.json의 `app` 항목)
   - app_name: QLineEdit (읽기 전용)
   - version: QLineEdit (읽기 전용)

2. **UI 섹션** (IT_RNVR.json의 `ui` 항목)
   - theme: QComboBox ["dark", "light"]
   - show_status_bar: QCheckBox
   - fullscreen_on_start: QCheckBox
   - window_state: 표시만 (현재 창 위치/크기 정보)
   - dock_state: 3개 체크박스 (camera_visible, recording_visible, playback_visible)

#### UI 레이아웃
```python
QVBoxLayout
├── QGroupBox "Application Info"
│   └── QFormLayout
│       ├── app_name (읽기전용)
│       └── version (읽기전용)
├── QGroupBox "User Interface"
│   └── QFormLayout
│       ├── theme (QComboBox)
│       ├── show_status_bar (QCheckBox)
│       ├── fullscreen_on_start (QCheckBox)
│       └── Dock Widgets Visibility
│           ├── camera_visible (QCheckBox)
│           ├── recording_visible (QCheckBox)
│           └── playback_visible (QCheckBox)
└── QGroupBox "Window State (Read-only)"
    └── QLabel (현재 창 상태 표시)
```

#### 구현 코드 예시
```python
class BasicSettingsTab(BaseSettingsTab):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # App Info Group (Read-only)
        app_group = QGroupBox("Application Info")
        app_layout = QFormLayout()

        self.app_name_label = QLabel()
        self.version_label = QLabel()
        app_layout.addRow("Application Name:", self.app_name_label)
        app_layout.addRow("Version:", self.version_label)
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)

        # UI Settings Group
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_layout.addRow("Theme:", self.theme_combo)

        self.status_bar_cb = QCheckBox("Show Status Bar")
        ui_layout.addRow(self.status_bar_cb)

        self.fullscreen_cb = QCheckBox("Fullscreen on Startup")
        ui_layout.addRow(self.fullscreen_cb)

        # Dock visibility
        dock_label = QLabel("Dock Widgets Visibility:")
        dock_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        ui_layout.addRow(dock_label)

        self.camera_dock_cb = QCheckBox("Camera List")
        self.recording_dock_cb = QCheckBox("Recording Control")
        self.playback_dock_cb = QCheckBox("Playback")

        ui_layout.addRow(self.camera_dock_cb)
        ui_layout.addRow(self.recording_dock_cb)
        ui_layout.addRow(self.playback_dock_cb)

        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)

        layout.addStretch()

    def load_settings(self):
        """설정 로드"""
        config = self.config_manager.config

        # App info
        app = config.get("app", {})
        self.app_name_label.setText(app.get("app_name", "IT_RNVR"))
        self.version_label.setText(app.get("version", "1.0.0"))

        # UI settings
        ui = config.get("ui", {})
        theme_idx = self.theme_combo.findText(ui.get("theme", "dark"))
        if theme_idx >= 0:
            self.theme_combo.setCurrentIndex(theme_idx)

        self.status_bar_cb.setChecked(ui.get("show_status_bar", True))
        self.fullscreen_cb.setChecked(ui.get("fullscreen_on_start", False))

        # Dock state
        dock_state = ui.get("dock_state", {})
        self.camera_dock_cb.setChecked(dock_state.get("camera_visible", True))
        self.recording_dock_cb.setChecked(dock_state.get("recording_visible", True))
        self.playback_dock_cb.setChecked(dock_state.get("playback_visible", True))

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            # UI 섹션만 업데이트
            if "ui" not in config:
                config["ui"] = {}

            config["ui"]["theme"] = self.theme_combo.currentText()
            config["ui"]["show_status_bar"] = self.status_bar_cb.isChecked()
            config["ui"]["fullscreen_on_start"] = self.fullscreen_cb.isChecked()

            # Dock state
            if "dock_state" not in config["ui"]:
                config["ui"]["dock_state"] = {}

            config["ui"]["dock_state"]["camera_visible"] = self.camera_dock_cb.isChecked()
            config["ui"]["dock_state"]["recording_visible"] = self.recording_dock_cb.isChecked()
            config["ui"]["dock_state"]["playback_visible"] = self.playback_dock_cb.isChecked()

            # ConfigManager를 통해 저장
            self.config_manager.save_config()
            return True
        except Exception as e:
            logger.error(f"Failed to save basic settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        # Basic settings는 특별한 검증 불필요
        return True, ""
```

---

### 2.2 Cameras Settings Tab

#### 구현 항목
- **좌측**: 카메라 리스트 (QListWidget)
- **우측**: 선택된 카메라의 상세 설정 (QFormLayout)
  - camera_id: QLineEdit
  - name: QLineEdit
  - rtsp_url: QLineEdit
  - enabled: QCheckBox
  - username/password: QLineEdit (Optional)
  - ptz_type: QComboBox ["None", "HIK", "ONVIF"]
  - ptz_port: QLineEdit
  - ptz_channel: QLineEdit
  - streaming_enabled_start: QCheckBox
  - recording_enabled_start: QCheckBox

- **버튼**: 추가, 수정, 삭제, 테스트 연결

#### UI 레이아웃
```python
QHBoxLayout
├── QVBoxLayout (좌측 - 카메라 리스트)
│   ├── QLabel "Camera List"
│   ├── QListWidget (카메라 목록)
│   └── QHBoxLayout (버튼)
│       ├── QPushButton "Add"
│       ├── QPushButton "Delete"
│       └── QPushButton "Duplicate"
└── QVBoxLayout (우측 - 카메라 설정)
    ├── QLabel "Camera Settings"
    ├── QScrollArea
    │   └── QGroupBox "Basic Info"
    │       └── QFormLayout
    │           ├── camera_id
    │           ├── name
    │           ├── rtsp_url
    │           └── enabled
    ├── QGroupBox "Authentication"
    │   └── QFormLayout
    │       ├── username
    │       └── password (EchoMode.Password)
    ├── QGroupBox "PTZ Settings"
    │   └── QFormLayout
    │       ├── ptz_type (QComboBox)
    │       ├── ptz_port
    │       └── ptz_channel
    ├── QGroupBox "Startup Options"
    │   └── QVBoxLayout
    │       ├── streaming_enabled_start
    │       └── recording_enabled_start
    └── QHBoxLayout
        ├── QPushButton "Test Connection"
        └── QPushButton "Apply"
```

#### 핵심 기능 구현
```python
class CamerasSettingsTab(BaseSettingsTab):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self.current_camera_index = -1
        self.cameras_data = []  # 임시 카메라 데이터 저장
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # 좌측: 카메라 리스트
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Camera List"))

        self.camera_list = QListWidget()
        self.camera_list.currentRowChanged.connect(self._on_camera_selected)
        left_layout.addWidget(self.camera_list)

        # 리스트 버튼
        list_btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_camera)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_camera)
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self._duplicate_camera)

        list_btn_layout.addWidget(self.add_btn)
        list_btn_layout.addWidget(self.delete_btn)
        list_btn_layout.addWidget(self.duplicate_btn)
        left_layout.addLayout(list_btn_layout)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(250)

        # 우측: 카메라 상세 설정
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Camera Settings"))

        # 스크롤 가능한 설정 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Basic Info Group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout()

        self.camera_id_edit = QLineEdit()
        self.camera_name_edit = QLineEdit()
        self.rtsp_url_edit = QLineEdit()
        self.enabled_cb = QCheckBox("Enable Camera")

        basic_layout.addRow("Camera ID:", self.camera_id_edit)
        basic_layout.addRow("Name:", self.camera_name_edit)
        basic_layout.addRow("RTSP URL:", self.rtsp_url_edit)
        basic_layout.addRow(self.enabled_cb)
        basic_group.setLayout(basic_layout)
        scroll_layout.addWidget(basic_group)

        # Authentication Group
        auth_group = QGroupBox("Authentication (Optional)")
        auth_layout = QFormLayout()

        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        auth_layout.addRow("Username:", self.username_edit)
        auth_layout.addRow("Password:", self.password_edit)
        auth_group.setLayout(auth_layout)
        scroll_layout.addWidget(auth_group)

        # PTZ Group
        ptz_group = QGroupBox("PTZ Settings")
        ptz_layout = QFormLayout()

        self.ptz_type_combo = QComboBox()
        self.ptz_type_combo.addItems(["None", "HIK", "ONVIF"])
        self.ptz_type_combo.currentTextChanged.connect(self._on_ptz_type_changed)
        self.ptz_port_edit = QLineEdit()
        self.ptz_channel_edit = QLineEdit()

        ptz_layout.addRow("PTZ Type:", self.ptz_type_combo)
        ptz_layout.addRow("PTZ Port:", self.ptz_port_edit)
        ptz_layout.addRow("PTZ Channel:", self.ptz_channel_edit)
        ptz_group.setLayout(ptz_layout)
        scroll_layout.addWidget(ptz_group)

        # Startup Options Group
        startup_group = QGroupBox("Startup Options")
        startup_layout = QVBoxLayout()

        self.streaming_start_cb = QCheckBox("Start Streaming on Startup")
        self.recording_start_cb = QCheckBox("Start Recording on Startup")

        startup_layout.addWidget(self.streaming_start_cb)
        startup_layout.addWidget(self.recording_start_cb)
        startup_group.setLayout(startup_layout)
        scroll_layout.addWidget(startup_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll)

        # 하단 버튼
        btn_layout = QHBoxLayout()
        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.clicked.connect(self._test_connection)
        self.apply_camera_btn = QPushButton("Apply Changes")
        self.apply_camera_btn.clicked.connect(self._apply_camera_changes)

        btn_layout.addStretch()
        btn_layout.addWidget(self.test_conn_btn)
        btn_layout.addWidget(self.apply_camera_btn)
        right_layout.addLayout(btn_layout)

        # 레이아웃 조합
        layout.addWidget(left_widget)
        layout.addLayout(right_layout, 1)

        # 초기 상태: 우측 패널 비활성화
        self._set_detail_panel_enabled(False)

    def _on_ptz_type_changed(self, ptz_type: str):
        """PTZ 타입 변경 시 포트/채널 활성화 상태 변경"""
        enabled = ptz_type != "None"
        self.ptz_port_edit.setEnabled(enabled)
        self.ptz_channel_edit.setEnabled(enabled)

    def _add_camera(self):
        """카메라 추가"""
        # 새 카메라 데이터 생성
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
            "streaming_enabled_start": False,
            "recording_enabled_start": False
        }

        self.cameras_data.append(new_camera)
        self.camera_list.addItem(new_camera["name"])
        self.camera_list.setCurrentRow(len(self.cameras_data) - 1)

    def _delete_camera(self):
        """카메라 삭제"""
        if self.current_camera_index < 0:
            return

        reply = QMessageBox.question(
            self, "Delete Camera",
            f"Delete camera '{self.cameras_data[self.current_camera_index]['name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            del self.cameras_data[self.current_camera_index]
            self.camera_list.takeItem(self.current_camera_index)

            if len(self.cameras_data) == 0:
                self._set_detail_panel_enabled(False)

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

    def _on_camera_selected(self, index: int):
        """카메라 선택 시 상세 정보 로드"""
        if index < 0 or index >= len(self.cameras_data):
            self._set_detail_panel_enabled(False)
            return

        self.current_camera_index = index
        camera = self.cameras_data[index]

        # 상세 패널 활성화
        self._set_detail_panel_enabled(True)

        # 데이터 로드
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
            self.ptz_type_combo.setCurrentIndex(0)  # None

        self.ptz_port_edit.setText(camera.get("ptz_port") or "")
        self.ptz_channel_edit.setText(camera.get("ptz_channel") or "")

        self.streaming_start_cb.setChecked(camera.get("streaming_enabled_start", False))
        self.recording_start_cb.setChecked(camera.get("recording_enabled_start", False))

    def _apply_camera_changes(self):
        """현재 카메라 변경사항 적용"""
        if self.current_camera_index < 0:
            return

        camera = self.cameras_data[self.current_camera_index]

        # 데이터 업데이트
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

        camera["streaming_enabled_start"] = self.streaming_start_cb.isChecked()
        camera["recording_enabled_start"] = self.recording_start_cb.isChecked()

        # 리스트 업데이트
        self.camera_list.item(self.current_camera_index).setText(camera["name"])

        QMessageBox.information(self, "Success", "Camera settings applied.")

    def _test_connection(self):
        """RTSP 연결 테스트"""
        rtsp_url = self.rtsp_url_edit.text().strip()
        if not rtsp_url:
            QMessageBox.warning(self, "Test Connection", "Please enter RTSP URL")
            return

        # 기존 camera_dialog.py의 테스트 로직 재사용
        # TODO: 실제 GStreamer 연결 테스트 구현
        QMessageBox.information(self, "Test Connection",
                               f"Testing connection to:\n{rtsp_url}\n\n(Not implemented yet)")

    def _set_detail_panel_enabled(self, enabled: bool):
        """상세 패널 활성화/비활성화"""
        self.camera_id_edit.setEnabled(enabled)
        self.camera_name_edit.setEnabled(enabled)
        self.rtsp_url_edit.setEnabled(enabled)
        self.enabled_cb.setEnabled(enabled)
        self.username_edit.setEnabled(enabled)
        self.password_edit.setEnabled(enabled)
        self.ptz_type_combo.setEnabled(enabled)
        self.ptz_port_edit.setEnabled(enabled)
        self.ptz_channel_edit.setEnabled(enabled)
        self.streaming_start_cb.setEnabled(enabled)
        self.recording_start_cb.setEnabled(enabled)
        self.test_conn_btn.setEnabled(enabled)
        self.apply_camera_btn.setEnabled(enabled)

    def load_settings(self):
        """카메라 설정 로드"""
        config = self.config_manager.config
        cameras = config.get("cameras", [])

        self.cameras_data = [cam.copy() for cam in cameras]
        self.camera_list.clear()

        for camera in self.cameras_data:
            self.camera_list.addItem(camera.get("name", "Unknown"))

        if len(self.cameras_data) > 0:
            self.camera_list.setCurrentRow(0)

    def save_settings(self) -> bool:
        """카메라 설정 저장"""
        try:
            # 현재 편집 중인 카메라 적용
            if self.current_camera_index >= 0:
                self._apply_camera_changes()

            config = self.config_manager.config
            config["cameras"] = self.cameras_data

            self.config_manager.save_config()
            return True
        except Exception as e:
            logger.error(f"Failed to save camera settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """카메라 설정 검증"""
        # 카메라 ID 중복 체크
        camera_ids = [cam["camera_id"] for cam in self.cameras_data]
        if len(camera_ids) != len(set(camera_ids)):
            return False, "Duplicate camera IDs found"

        # 필수 필드 체크
        for camera in self.cameras_data:
            if not camera.get("camera_id"):
                return False, f"Camera ID is required for all cameras"
            if not camera.get("name"):
                return False, f"Camera name is required for all cameras"
            if not camera.get("rtsp_url"):
                return False, f"RTSP URL is required for camera '{camera['name']}'"

        return True, ""
```

---

### 2.3 Streaming Settings Tab

#### 구현 항목
- default_layout: QComboBox ["1x1", "2x2", "3x3", "4x4"]
- show_timestamp: QCheckBox
- show_camera_name: QCheckBox
- OSD 설정
  - osd_font_size: QSpinBox
  - osd_font_color: ColorPickerButton (RGB)
  - osd_valignment: QComboBox ["top", "center", "bottom"]
  - osd_halignment: QComboBox ["left", "center", "right"]
  - osd_xpad, osd_ypad: QSpinBox
- use_hardware_acceleration: QCheckBox
- decoder_preference: QListWidget (드래그로 순서 변경 가능)
- buffer_size: QSpinBox (bytes)
- latency_ms: QSpinBox
- tcp_timeout: QSpinBox
- auto_reconnect: QCheckBox
- max_reconnect_attempts: QSpinBox
- reconnect_delay_seconds: QSpinBox
- connection_timeout: QSpinBox

#### UI 레이아웃
```python
QVBoxLayout
├── QGroupBox "Display Layout"
│   └── QFormLayout
│       └── default_layout (QComboBox)
├── QGroupBox "OSD (On-Screen Display)"
│   └── QFormLayout
│       ├── show_timestamp (QCheckBox)
│       ├── show_camera_name (QCheckBox)
│       ├── osd_font_size (QSpinBox)
│       ├── osd_font_color (ColorPickerButton)
│       ├── osd_valignment (QComboBox)
│       ├── osd_halignment (QComboBox)
│       ├── osd_xpad (QSpinBox)
│       └── osd_ypad (QSpinBox)
├── QGroupBox "Hardware Acceleration"
│   └── QVBoxLayout
│       ├── use_hardware_acceleration (QCheckBox)
│       └── decoder_preference (DraggableListWidget)
├── QGroupBox "Network & Buffering"
│   └── QFormLayout
│       ├── buffer_size (QSpinBox with suffix "bytes")
│       ├── latency_ms (QSpinBox with suffix "ms")
│       ├── tcp_timeout (QSpinBox with suffix "ms")
│       └── connection_timeout (QSpinBox with suffix "sec")
└── QGroupBox "Auto Reconnection"
    └── QFormLayout
        ├── auto_reconnect (QCheckBox)
        ├── max_reconnect_attempts (QSpinBox)
        └── reconnect_delay_seconds (QSpinBox with suffix "sec")
```

---

### 2.4 Recording Settings Tab

#### 구현 항목
- base_path: QLineEdit + Browse 버튼
- file_format: QComboBox ["mkv", "mp4", "avi"]
- rotation_minutes: QSpinBox (분 단위)
- codec: QComboBox ["h264", "h265"]
- fragment_duration_ms: QSpinBox (ms)

#### UI 레이아웃
```python
QVBoxLayout
├── QGroupBox "Recording Path"
│   └── QHBoxLayout
│       ├── QLineEdit (base_path)
│       └── QPushButton "Browse..."
├── QGroupBox "Recording Format"
│   └── QFormLayout
│       ├── file_format (QComboBox)
│       ├── codec (QComboBox)
│       └── fragment_duration_ms (QSpinBox)
├── QGroupBox "File Rotation"
│   └── QFormLayout
│       └── rotation_minutes (QSpinBox)
└── QLabel "Preview" (저장 경로 예시 표시)
```

---

### 2.5 Backup Settings Tab

#### 구현 항목
- destination_path: QLineEdit + Browse 버튼
- delete_after_backup: QCheckBox
- verification: QCheckBox

#### UI 레이아웃
```python
QVBoxLayout
├── QGroupBox "Backup Destination"
│   └── QVBoxLayout
│       ├── QHBoxLayout
│       │   ├── QLineEdit (destination_path)
│       │   └── QPushButton "Browse..."
│       └── QLabel (여유 공간 표시)
├── QGroupBox "Backup Options"
│   └── QVBoxLayout
│       ├── verification (QCheckBox "Verify files with MD5 hash")
│       └── delete_after_backup (QCheckBox "Delete source after backup")
└── QLabel "Warning" (delete_after_backup 체크 시 경고 메시지)
```

---

### 2.6 Storage Settings Tab

#### 구현 항목
- auto_cleanup_enabled: QCheckBox
- cleanup_interval_hours: QSpinBox
- cleanup_on_startup: QCheckBox
- min_free_space_gb: QDoubleSpinBox
- min_free_space_percent: QSpinBox
- cleanup_threshold_percent: QSpinBox
- retention_days: QSpinBox
- delete_batch_size: QSpinBox
- delete_batch_delay_seconds: QSpinBox
- auto_delete_priority: QComboBox ["oldest_first", "largest_first"]

#### UI 레이아웃
```python
QVBoxLayout
├── QGroupBox "Auto Cleanup"
│   └── QVBoxLayout
│       ├── auto_cleanup_enabled (QCheckBox)
│       ├── QFormLayout
│       │   ├── cleanup_interval_hours
│       │   ├── cleanup_on_startup
│       │   └── auto_delete_priority
├── QGroupBox "Space Management"
│   └── QFormLayout
│       ├── min_free_space_gb
│       ├── min_free_space_percent
│       └── cleanup_threshold_percent
├── QGroupBox "Retention Policy"
│   └── QFormLayout
│       ├── retention_days
│       ├── delete_batch_size
│       └── delete_batch_delay_seconds
└── QLabel "Current Storage Status" (현재 디스크 사용량 표시)
```

---

### 2.7 Hot_Key Settings Tab

#### 구현 항목
IT_RNVR.json의 `menu_keys` 항목의 모든 키 매핑 설정
- KeySequenceEdit 위젯 사용 (키 입력 감지)
- 중복 키 감지 및 경고

#### UI 레이아웃
```python
QVBoxLayout
├── QLabel "Keyboard Shortcuts Configuration"
├── QScrollArea
│   └── QFormLayout
│       ├── camera_connect (KeySequenceEdit)
│       ├── camera_stop (KeySequenceEdit)
│       ├── prev_group (KeySequenceEdit)
│       ├── camera_connect_all (KeySequenceEdit)
│       ├── camera_stop_all (KeySequenceEdit)
│       ├── next_group (KeySequenceEdit)
│       ├── prev_config (KeySequenceEdit)
│       ├── record_start (KeySequenceEdit)
│       ├── screen_rotate (KeySequenceEdit)
│       ├── next_config (KeySequenceEdit)
│       ├── record_stop (KeySequenceEdit)
│       ├── screen_flip (KeySequenceEdit)
│       ├── screen_hide (KeySequenceEdit)
│       ├── menu_open (KeySequenceEdit)
│       └── program_exit (KeySequenceEdit)
└── QHBoxLayout
    ├── QPushButton "Reset to Defaults"
    └── QLabel "Status: OK / Duplicate key detected"
```

#### KeySequenceEdit 위젯 구현
```python
class KeySequenceEdit(QLineEdit):
    """키 입력을 감지하는 커스텀 위젯"""
    key_changed = pyqtSignal(str)  # 키 변경 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Press a key...")
        self._current_key = ""

    def keyPressEvent(self, event):
        """키 입력 이벤트"""
        key = event.key()

        # 특수 키 처리
        if key == Qt.Key_Escape:
            self.setText("")
            self._current_key = ""
            self.key_changed.emit("")
            return

        # 키 이름 변환
        key_name = QKeySequence(key).toString()

        # 수정자 키 추가 (Ctrl, Alt, Shift)
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            key_name = f"Ctrl+{key_name}"
        if modifiers & Qt.AltModifier:
            key_name = f"Alt+{key_name}"
        if modifiers & Qt.ShiftModifier:
            key_name = f"Shift+{key_name}"

        self.setText(key_name)
        self._current_key = key_name
        self.key_changed.emit(key_name)

    def get_key(self) -> str:
        """현재 키 반환"""
        return self._current_key

    def set_key(self, key: str):
        """키 설정"""
        self.setText(key)
        self._current_key = key
```

---

### 2.8 PTZ_Key Settings Tab

#### 구현 항목
IT_RNVR.json의 `ptz_keys` 항목의 모든 키 매핑 설정
- PTZ 방향키 (9방향)
- Zoom In/Out
- Speed 조절

#### UI 레이아웃
```python
QVBoxLayout
├── QLabel "PTZ Control Keys"
├── QGroupBox "Direction Control (9-way)"
│   └── QGridLayout (3x3)
│       ├── [0,0] pan_left (KeySequenceEdit "Q")
│       ├── [0,1] up (KeySequenceEdit "W")
│       ├── [0,2] right_up (KeySequenceEdit "E")
│       ├── [1,0] left (KeySequenceEdit "A")
│       ├── [1,1] stop (KeySequenceEdit "S")
│       ├── [1,2] right (KeySequenceEdit "D")
│       ├── [2,0] pan_down (KeySequenceEdit "Z")
│       ├── [2,1] down (KeySequenceEdit "X")
│       └── [2,2] right_down (KeySequenceEdit "C")
├── QGroupBox "Zoom Control"
│   └── QFormLayout
│       ├── zoom_in (KeySequenceEdit "V")
│       └── zoom_out (KeySequenceEdit "B")
├── QGroupBox "Speed Control"
│   └── QFormLayout
│       ├── ptz_speed_up (KeySequenceEdit "R")
│       └── ptz_speed_down (KeySequenceEdit "T")
└── QHBoxLayout
    └── QPushButton "Reset to Defaults"
```

---

## 3. 메인 설정 다이얼로그 구현

### 3.1 SettingsDialog 클래스

```python
class SettingsDialog(QDialog):
    """메인 설정 다이얼로그"""

    settings_changed = pyqtSignal()  # 설정 변경 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager.get_instance()

        self.setWindowTitle("Settings")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self._setup_ui()
        self._load_all_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # 탭 위젯
        self.tab_widget = QTabWidget()

        # 각 탭 추가
        self.basic_tab = BasicSettingsTab(self.config_manager)
        self.cameras_tab = CamerasSettingsTab(self.config_manager)
        self.streaming_tab = StreamingSettingsTab(self.config_manager)
        self.recording_tab = RecordingSettingsTab(self.config_manager)
        self.backup_tab = BackupSettingsTab(self.config_manager)
        self.storage_tab = StorageSettingsTab(self.config_manager)
        self.hotkey_tab = HotKeySettingsTab(self.config_manager)
        self.ptz_key_tab = PTZKeySettingsTab(self.config_manager)

        self.tab_widget.addTab(self.basic_tab, "Basic")
        self.tab_widget.addTab(self.cameras_tab, "Cameras")
        self.tab_widget.addTab(self.streaming_tab, "Streaming")
        self.tab_widget.addTab(self.recording_tab, "Recording")
        self.tab_widget.addTab(self.backup_tab, "Backup")
        self.tab_widget.addTab(self.storage_tab, "Storage")
        self.tab_widget.addTab(self.hotkey_tab, "Hot Keys")
        self.tab_widget.addTab(self.ptz_key_tab, "PTZ Keys")

        layout.addWidget(self.tab_widget)

        # 버튼
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self._on_cancel)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)

        layout.addWidget(button_box)

        self._apply_theme()

    def _apply_theme(self):
        """다크 테마 적용"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #4a4a4a;
                background-color: #2a2a2a;
            }
            QTabBar::tab {
                background-color: #3a3a3a;
                color: #ffffff;
                padding: 8px 16px;
                border: 1px solid #4a4a4a;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #2a2a2a;
                border-bottom: 2px solid #5a9fd4;
            }
            QTabBar::tab:hover {
                background-color: #4a4a4a;
            }
        """)

    def _load_all_settings(self):
        """모든 설정 로드"""
        self.basic_tab.load_settings()
        self.cameras_tab.load_settings()
        self.streaming_tab.load_settings()
        self.recording_tab.load_settings()
        self.backup_tab.load_settings()
        self.storage_tab.load_settings()
        self.hotkey_tab.load_settings()
        self.ptz_key_tab.load_settings()

    def _validate_all_settings(self) -> tuple[bool, str]:
        """모든 탭 설정 검증"""
        tabs = [
            ("Basic", self.basic_tab),
            ("Cameras", self.cameras_tab),
            ("Streaming", self.streaming_tab),
            ("Recording", self.recording_tab),
            ("Backup", self.backup_tab),
            ("Storage", self.storage_tab),
            ("Hot Keys", self.hotkey_tab),
            ("PTZ Keys", self.ptz_key_tab),
        ]

        for tab_name, tab in tabs:
            valid, error_msg = tab.validate_settings()
            if not valid:
                return False, f"{tab_name} Tab: {error_msg}"

        return True, ""

    def _save_all_settings(self) -> bool:
        """모든 설정 저장"""
        try:
            # 검증
            valid, error_msg = self._validate_all_settings()
            if not valid:
                QMessageBox.warning(self, "Validation Error", error_msg)
                return False

            # 저장
            success = True
            success &= self.basic_tab.save_settings()
            success &= self.cameras_tab.save_settings()
            success &= self.streaming_tab.save_settings()
            success &= self.recording_tab.save_settings()
            success &= self.backup_tab.save_settings()
            success &= self.storage_tab.save_settings()
            success &= self.hotkey_tab.save_settings()
            success &= self.ptz_key_tab.save_settings()

            if success:
                self.settings_changed.emit()
                logger.info("All settings saved successfully")
                return True
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save some settings")
                return False
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Error", f"Save failed:\n{str(e)}")
            return False

    def _on_ok(self):
        """OK 버튼 클릭"""
        if self._save_all_settings():
            self.accept()

    def _on_cancel(self):
        """Cancel 버튼 클릭"""
        # 변경사항이 있는지 확인
        has_changes = any([
            self.basic_tab.has_changes(),
            self.cameras_tab.has_changes(),
            self.streaming_tab.has_changes(),
            self.recording_tab.has_changes(),
            self.backup_tab.has_changes(),
            self.storage_tab.has_changes(),
            self.hotkey_tab.has_changes(),
            self.ptz_key_tab.has_changes(),
        ])

        if has_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.reject()
        else:
            self.reject()

    def _on_apply(self):
        """Apply 버튼 클릭"""
        if self._save_all_settings():
            QMessageBox.information(self, "Success", "Settings applied successfully")
```

---

## 4. BaseSettingsTab 추상 클래스

```python
from abc import ABC, abstractmethod

class BaseSettingsTab(QWidget, ABC):
    """설정 탭의 베이스 클래스"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._original_data = {}  # 원본 데이터 (변경 감지용)

    @abstractmethod
    def load_settings(self):
        """설정 로드 (서브클래스에서 구현)"""
        pass

    @abstractmethod
    def save_settings(self) -> bool:
        """설정 저장 (서브클래스에서 구현)"""
        pass

    @abstractmethod
    def validate_settings(self) -> tuple[bool, str]:
        """
        설정 검증 (서브클래스에서 구현)

        Returns:
            (valid, error_message) 튜플
        """
        pass

    def has_changes(self) -> bool:
        """
        변경 사항이 있는지 확인
        서브클래스에서 오버라이드 가능
        """
        # 기본 구현: 항상 False (서브클래스에서 오버라이드)
        return False
```

---

## 5. 메인 윈도우 통합

### main_window.py 수정

```python
def _setup_menu_bar(self):
    """메뉴바 구성"""
    menubar = self.menuBar()

    # File 메뉴
    file_menu = menubar.addMenu("&File")

    # Settings 액션 추가
    settings_action = QAction("&Settings", self)
    settings_action.setShortcut("Ctrl+,")
    settings_action.triggered.connect(self._show_settings_dialog)
    file_menu.addAction(settings_action)

    file_menu.addSeparator()

    exit_action = QAction("E&xit", self)
    exit_action.setShortcut("Ctrl+Q")
    exit_action.triggered.connect(self.close)
    file_menu.addAction(exit_action)

def _show_settings_dialog(self):
    """설정 다이얼로그 표시"""
    from ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(self)
    dialog.settings_changed.connect(self._on_settings_changed)
    dialog.exec_()

def _on_settings_changed(self):
    """설정 변경 시 처리"""
    logger.info("Settings changed - reloading configuration")

    # 설정 변경 후 필요한 처리
    # 예: 테마 적용, 핫키 재설정, 카메라 재연결 등

    QMessageBox.information(
        self,
        "Settings Saved",
        "Settings have been saved.\nSome changes may require application restart."
    )
```

---

## 6. 구현 순서

### Phase 1: 기본 구조 (1-2일)
1. ✅ BaseSettingsTab 추상 클래스 작성
2. ✅ SettingsDialog 메인 다이얼로그 틀 작성
3. ✅ 메인 윈도우에 설정 메뉴 추가

### Phase 2: 간단한 탭 구현 (2-3일)
4. ✅ BasicSettingsTab 구현 (가장 간단)
5. ✅ BackupSettingsTab 구현
6. ✅ RecordingSettingsTab 구현

### Phase 3: 중간 난이도 탭 (3-4일)
7. ✅ StreamingSettingsTab 구현
8. ✅ StorageSettingsTab 구현

### Phase 4: 복잡한 탭 구현 (4-5일)
9. ✅ CamerasSettingsTab 구현 (가장 복잡)
10. ✅ HotKeySettingsTab 구현 (KeySequenceEdit 위젯 필요)
11. ✅ PTZKeySettingsTab 구현

### Phase 5: 통합 및 테스트 (2-3일)
12. ✅ 모든 탭 통합 테스트
13. ✅ 설정 저장/로드 검증
14. ✅ UI 테마 및 스타일 통일
15. ✅ 에러 처리 강화

---

## 7. 핵심 기능 구현 가이드

### 7.1 ConfigManager와의 연동
```python
# 설정 로드
config = ConfigManager.get_instance()
cameras = config.config.get("cameras", [])

# 설정 저장
config.config["cameras"] = new_cameras_data
config.save_config()
```

### 7.2 실시간 검증
```python
# 입력 필드에 변경 감지
self.camera_id_edit.textChanged.connect(self._on_camera_id_changed)

def _on_camera_id_changed(self, text):
    # 실시간 검증
    if not re.match(r'^[a-zA-Z0-9_]+$', text):
        self.camera_id_edit.setStyleSheet("border: 1px solid red;")
    else:
        self.camera_id_edit.setStyleSheet("")
```

### 7.3 변경 사항 추적
```python
def load_settings(self):
    # 원본 데이터 저장
    self._original_data = {
        "theme": self.theme_combo.currentText(),
        "show_status_bar": self.status_bar_cb.isChecked(),
        # ...
    }

def has_changes(self) -> bool:
    # 현재 값과 원본 비교
    current_data = {
        "theme": self.theme_combo.currentText(),
        "show_status_bar": self.status_bar_cb.isChecked(),
        # ...
    }
    return current_data != self._original_data
```

---

## 8. 테스트 계획

### 8.1 단위 테스트
- 각 탭의 load_settings() 테스트
- 각 탭의 save_settings() 테스트
- validate_settings() 테스트

### 8.2 통합 테스트
- 설정 다이얼로그 열기/닫기
- 탭 전환 테스트
- 설정 저장 후 재로드 테스트

### 8.3 사용자 시나리오 테스트
1. 카메라 추가 → 저장 → 재시작 → 카메라 로드 확인
2. 핫키 변경 → 저장 → 핫키 동작 확인
3. 잘못된 입력 → 검증 오류 메시지 확인

---

## 9. 참고 사항

### 9.1 기존 코드 재사용
- `camera_dialog.py`: 카메라 설정 UI 참고
- `backup_dialog.py`: 백업 설정 UI 참고
- `core/config.py`: ConfigManager 사용법

### 9.2 주의 사항
- ConfigManager는 싱글톤 패턴 - `ConfigManager.get_instance()` 사용
- 설정 저장 시 JSON 파일 직접 수정 (`config.save_config()`)
- PyQt5 사용 (PyQt6 아님)

### 9.3 확장성 고려
- 새로운 설정 탭 추가 시 BaseSettingsTab 상속
- 공통 위젯 (KeySequenceEdit, ColorPickerButton) 재사용
- 설정 검증 로직 분리 (validate_settings 메서드)

---

## 요약

이 계획서는 IT_RNVR.json의 모든 설정 항목을 체계적으로 관리할 수 있는 통합 설정 다이얼로그의 전체 구현 방법을 제시합니다.

**핵심 특징:**
1. **탭 기반 UI**: 각 설정 카테고리를 독립적인 탭으로 구성
2. **BaseSettingsTab 패턴**: 공통 인터페이스로 확장성 확보
3. **실시간 검증**: 입력 즉시 유효성 검사
4. **ConfigManager 통합**: 싱글톤 패턴으로 설정 관리
5. **단계별 구현**: 간단한 탭부터 복잡한 탭까지 순차적 개발

**예상 개발 기간**: 약 15-20일 (순수 개발 시간 기준)
