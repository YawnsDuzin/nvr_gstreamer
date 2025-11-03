"""
HotKey Settings Tab
단축키 설정 탭 (menu_keys 항목)
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from ui.widgets.key_sequence_edit import KeySequenceEdit
from .base_settings_tab import BaseSettingsTab


class HotKeySettingsTab(BaseSettingsTab):
    """
    단축키 설정 탭
    - 메뉴 단축키 (menu_keys)
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self.key_edits = {}  # 키 이름 -> KeySequenceEdit 매핑
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # 안내 문구
        info_label = QLabel(
            "Configure keyboard shortcuts for menu actions.\n"
            "Click on a field and press a key combination."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #3a3a3a; border-radius: 5px;")
        layout.addWidget(info_label)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # 단축키 설정 폼
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # IT_RNVR.json의 menu_keys 항목들
        hotkey_items = [
            ("camera_connect", "Camera Connect"),
            ("camera_stop", "Camera Stop"),
            ("camera_connect_all", "Connect All Cameras"),
            ("camera_stop_all", "Stop All Cameras"),
            ("prev_group", "Previous Group"),
            ("next_group", "Next Group"),
            ("prev_config", "Previous Config"),
            ("next_config", "Next Config"),
            ("record_start", "Start Recording"),
            ("record_stop", "Stop Recording"),
            ("screen_rotate", "Rotate Screen"),
            ("screen_flip", "Flip Screen"),
            ("screen_hide", "Hide Screen"),
            ("menu_open", "Open Menu"),
            ("program_exit", "Exit Program"),
        ]

        for key_name, label in hotkey_items:
            key_edit = KeySequenceEdit()
            key_edit.key_changed.connect(self._on_key_changed)
            self.key_edits[key_name] = key_edit
            form_layout.addRow(f"{label}:", key_edit)

        scroll_layout.addLayout(form_layout)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)

        layout.addWidget(scroll)

        # 하단 버튼
        btn_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        self.reset_btn.setToolTip("Reset all shortcuts to default values")

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.status_label)

        layout.addLayout(btn_layout)

        # Apply theme
        self.apply_theme()

        logger.debug("HotKeySettingsTab UI setup complete")

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
            "Reset all shortcuts to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 기본값 설정
            defaults = {
                "camera_connect": "F1",
                "camera_stop": "F2",
                "camera_connect_all": "F3",
                "camera_stop_all": "F4",
                "prev_group": "N",
                "next_group": "M",
                "prev_config": "F5",
                "next_config": "F6",
                "record_start": "F7",
                "record_stop": "F8",
                "screen_rotate": "F9",
                "screen_flip": "F10",
                "screen_hide": "Esc",
                "menu_open": "F11",
                "program_exit": "F12",
            }

            for key_name, default_value in defaults.items():
                if key_name in self.key_edits:
                    self.key_edits[key_name].set_key(default_value)

            self._on_key_changed()
            logger.info("Hotkeys reset to defaults")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            menu_keys = config.get("menu_keys", {})

            # 키 값 로드
            for key_name, key_edit in self.key_edits.items():
                key_value = menu_keys.get(key_name, "")
                key_edit.set_key(key_value)

            # 중복 확인
            self._on_key_changed()

            # Store original data
            self._store_original_data({
                "menu_keys": menu_keys.copy()
            })

            logger.debug("HotKeySettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load hotkey settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            if "menu_keys" not in config:
                config["menu_keys"] = {}

            # 키 값 저장
            for key_name, key_edit in self.key_edits.items():
                config["menu_keys"][key_name] = key_edit.get_key()

            self.config_manager.save_config()

            logger.info("Hotkey settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save hotkey settings: {e}")
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
            return False, f"Duplicate keyboard shortcuts detected: {', '.join(set(duplicates))}"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            original_keys = original.get("menu_keys", {})

            current_keys = {}
            for key_name, key_edit in self.key_edits.items():
                current_keys[key_name] = key_edit.get_key()

            return original_keys != current_keys

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
