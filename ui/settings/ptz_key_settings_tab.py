"""
PTZ Key Settings Tab
PTZ 컨트롤 키 설정 탭 (ptz_keys 항목)
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QPushButton, QGridLayout, QWidget, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from ui.widgets.key_sequence_edit import KeySequenceEdit
from .base_settings_tab import BaseSettingsTab


class PTZKeySettingsTab(BaseSettingsTab):
    """
    PTZ 컨트롤 키 설정 탭
    - PTZ 방향 키 (9방향)
    - Zoom In/Out
    - Speed 조절
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self.key_edits = {}  # 키 이름 -> KeySequenceEdit 매핑
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # 안내 문구
        info_label = QLabel(
            "Configure PTZ (Pan-Tilt-Zoom) control keys.\n"
            "Click on a field and press a key."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #3a3a3a; border-radius: 5px;")
        layout.addWidget(info_label)

        # Direction Control Group (9-way)
        direction_group = QGroupBox("Direction Control (9-way)")
        direction_layout = QGridLayout()

        # 3x3 그리드로 방향키 배치
        direction_keys = [
            ("pan_left", "↖", 0, 0),
            ("up", "↑", 0, 1),
            ("right_up", "↗", 0, 2),
            ("left", "←", 1, 0),
            ("stop", "■ Stop", 1, 1),
            ("right", "→", 1, 2),
            ("pan_down", "↙", 2, 0),
            ("down", "↓", 2, 1),
            ("right_down", "↘", 2, 2),
        ]

        for key_name, symbol, row, col in direction_keys:
            key_edit = KeySequenceEdit()
            key_edit.key_changed.connect(self._on_key_changed)
            self.key_edits[key_name] = key_edit

            # Label with symbol
            label = QLabel(symbol)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 16px; font-weight: bold;")

            # 컨테이너
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5)
            container_layout.addWidget(label)
            container_layout.addWidget(key_edit)

            direction_layout.addWidget(container, row, col)

        direction_group.setLayout(direction_layout)
        layout.addWidget(direction_group)

        # Zoom Control Group
        zoom_group = QGroupBox("Zoom Control")
        zoom_form = QFormLayout()

        self.key_edits["zoom_in"] = KeySequenceEdit()
        self.key_edits["zoom_in"].key_changed.connect(self._on_key_changed)
        zoom_form.addRow("Zoom In (+):", self.key_edits["zoom_in"])

        self.key_edits["zoom_out"] = KeySequenceEdit()
        self.key_edits["zoom_out"].key_changed.connect(self._on_key_changed)
        zoom_form.addRow("Zoom Out (-):", self.key_edits["zoom_out"])

        zoom_group.setLayout(zoom_form)
        layout.addWidget(zoom_group)

        # Speed Control Group
        speed_group = QGroupBox("Speed Control")
        speed_form = QFormLayout()

        self.key_edits["ptz_speed_up"] = KeySequenceEdit()
        self.key_edits["ptz_speed_up"].key_changed.connect(self._on_key_changed)
        speed_form.addRow("Speed Up:", self.key_edits["ptz_speed_up"])

        self.key_edits["ptz_speed_down"] = KeySequenceEdit()
        self.key_edits["ptz_speed_down"].key_changed.connect(self._on_key_changed)
        speed_form.addRow("Speed Down:", self.key_edits["ptz_speed_down"])

        speed_group.setLayout(speed_form)
        layout.addWidget(speed_group)

        layout.addStretch()
        scroll.setWidget(scroll_content)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # 하단 버튼
        btn_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        self.reset_btn.setToolTip("Reset all PTZ keys to default values")

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.status_label)

        main_layout.addLayout(btn_layout)

        logger.debug("PTZKeySettingsTab UI setup complete")

    def _on_key_changed(self):
        """키 변경 시 중복 확인"""
        # 중복 키 확인
        keys_used = {}
        duplicates = []

        for key_name, key_edit in self.key_edits.items():
            key_value = key_edit.get_key()
            if key_value and key_value != "":
                if key_value in keys_used:
                    duplicates.append(key_value)
                else:
                    keys_used[key_value] = key_name

        if duplicates:
            self.status_label.setText(
                f"⚠ Warning: Duplicate keys detected: {', '.join(set(duplicates))}"
            )
            self.status_label.setStyleSheet("color: #ff9944; font-weight: bold;")
        else:
            self.status_label.setText("✓ No duplicate keys")
            self.status_label.setStyleSheet("color: #44ff44;")

    def _reset_to_defaults(self):
        """기본값으로 리셋"""
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Reset all PTZ keys to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 기본값 설정
            defaults = {
                "pan_left": "Q",
                "up": "W",
                "right_up": "E",
                "left": "A",
                "stop": "S",
                "right": "D",
                "pan_down": "Z",
                "down": "X",
                "right_down": "C",
                "zoom_in": "V",
                "zoom_out": "B",
                "ptz_speed_up": "R",
                "ptz_speed_down": "T",
            }

            for key_name, default_value in defaults.items():
                if key_name in self.key_edits:
                    self.key_edits[key_name].set_key(default_value)

            self._on_key_changed()
            logger.info("PTZ keys reset to defaults")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            ptz_keys = config.get("ptz_keys", {})

            # 키 값 로드
            for key_name, key_edit in self.key_edits.items():
                key_value = ptz_keys.get(key_name, "")
                key_edit.set_key(key_value)

            # 중복 확인
            self._on_key_changed()

            # Store original data
            self._store_original_data({
                "ptz_keys": ptz_keys.copy()
            })

            logger.debug("PTZKeySettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load PTZ key settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            if "ptz_keys" not in config:
                config["ptz_keys"] = {}

            # 키 값 저장
            for key_name, key_edit in self.key_edits.items():
                config["ptz_keys"][key_name] = key_edit.get_key()

            self.config_manager.save_config()

            logger.info("PTZ key settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save PTZ key settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        # 중복 키 확인
        keys_used = {}
        duplicates = []

        for key_name, key_edit in self.key_edits.items():
            key_value = key_edit.get_key()
            if key_value and key_value != "":
                if key_value in keys_used:
                    duplicates.append(key_value)
                else:
                    keys_used[key_value] = key_name

        if duplicates:
            return False, f"Duplicate PTZ keys detected: {', '.join(set(duplicates))}"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            original_keys = original.get("ptz_keys", {})

            current_keys = {}
            for key_name, key_edit in self.key_edits.items():
                current_keys[key_name] = key_edit.get_key()

            return original_keys != current_keys

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
