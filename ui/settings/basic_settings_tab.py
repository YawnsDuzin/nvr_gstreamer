"""
Basic Settings Tab
기본 설정 탭 (app, ui 항목)
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QComboBox, QCheckBox
)
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class BasicSettingsTab(BaseSettingsTab):
    """
    기본 설정 탭
    - App 정보 (읽기 전용)
    - UI 설정 (테마, 상태바, 풀스크린, Dock 표시)
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # App Info Group (Read-only)
        app_group = QGroupBox("Application Information")
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

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setToolTip("Select application theme")
        ui_layout.addRow("Theme:", self.theme_combo)

        # Status bar
        self.status_bar_cb = QCheckBox("Show Status Bar")
        self.status_bar_cb.setToolTip("Show/hide status bar at the bottom")
        ui_layout.addRow(self.status_bar_cb)

        # Fullscreen on startup
        self.fullscreen_cb = QCheckBox("Fullscreen on Startup")
        self.fullscreen_cb.setToolTip("Start application in fullscreen mode")
        ui_layout.addRow(self.fullscreen_cb)

        # Dock visibility section
        dock_label = QLabel("Dock Widgets Visibility:")
        dock_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        ui_layout.addRow(dock_label)

        self.camera_dock_cb = QCheckBox("Show Camera List")
        self.camera_dock_cb.setToolTip("Show/hide camera list dock")
        ui_layout.addRow(self.camera_dock_cb)

        self.recording_dock_cb = QCheckBox("Show Recording Control")
        self.recording_dock_cb.setToolTip("Show/hide recording control dock")
        ui_layout.addRow(self.recording_dock_cb)

        self.playback_dock_cb = QCheckBox("Show Playback")
        self.playback_dock_cb.setToolTip("Show/hide playback dock")
        ui_layout.addRow(self.playback_dock_cb)

        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)

        # Window State Group (Read-only)
        window_group = QGroupBox("Window State (Read-only)")
        window_layout = QFormLayout()

        self.window_info_label = QLabel()
        self.window_info_label.setWordWrap(True)
        window_layout.addRow(self.window_info_label)

        window_group.setLayout(window_layout)
        layout.addWidget(window_group)

        layout.addStretch()

        # Apply theme
        self.apply_theme()

        logger.debug("BasicSettingsTab UI setup complete")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config

            # App info (read-only)
            app = config.get("app", {})
            self.app_name_label.setText(app.get("app_name", "IT_RNVR"))
            self.version_label.setText(app.get("version", "1.0.0"))

            # UI settings
            ui = config.get("ui", {})

            # Theme
            theme = ui.get("theme", "dark")
            theme_idx = self.theme_combo.findText(theme)
            if theme_idx >= 0:
                self.theme_combo.setCurrentIndex(theme_idx)

            # Status bar
            self.status_bar_cb.setChecked(ui.get("show_status_bar", True))

            # Fullscreen on startup
            self.fullscreen_cb.setChecked(ui.get("fullscreen_on_start", False))

            # Dock state
            dock_state = ui.get("dock_state", {})
            self.camera_dock_cb.setChecked(dock_state.get("camera_visible", True))
            self.recording_dock_cb.setChecked(dock_state.get("recording_visible", True))
            self.playback_dock_cb.setChecked(dock_state.get("playback_visible", True))

            # Window state (read-only)
            window_state = ui.get("window_state", {})
            x = window_state.get("x", 0)
            y = window_state.get("y", 0)
            width = window_state.get("width", 1200)
            height = window_state.get("height", 700)
            self.window_info_label.setText(
                f"Position: ({x}, {y})\n"
                f"Size: {width} x {height}"
            )

            # Store original data for change detection
            self._store_original_data({
                "theme": theme,
                "show_status_bar": ui.get("show_status_bar", True),
                "fullscreen_on_start": ui.get("fullscreen_on_start", False),
                "camera_visible": dock_state.get("camera_visible", True),
                "recording_visible": dock_state.get("recording_visible", True),
                "playback_visible": dock_state.get("playback_visible", True),
            })

            logger.debug("BasicSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load basic settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            # UI 섹션이 없으면 생성
            if "ui" not in config:
                config["ui"] = {}

            # UI settings 업데이트
            config["ui"]["theme"] = self.theme_combo.currentText()
            config["ui"]["show_status_bar"] = self.status_bar_cb.isChecked()
            config["ui"]["fullscreen_on_start"] = self.fullscreen_cb.isChecked()

            # Dock state 업데이트
            if "dock_state" not in config["ui"]:
                config["ui"]["dock_state"] = {}

            config["ui"]["dock_state"]["camera_visible"] = self.camera_dock_cb.isChecked()
            config["ui"]["dock_state"]["recording_visible"] = self.recording_dock_cb.isChecked()
            config["ui"]["dock_state"]["playback_visible"] = self.playback_dock_cb.isChecked()

            # ConfigManager를 통해 저장
            self.config_manager.save_config()

            logger.info("Basic settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save basic settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        # Basic settings는 특별한 검증 불필요
        # 모든 값이 유효함
        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            current = {
                "theme": self.theme_combo.currentText(),
                "show_status_bar": self.status_bar_cb.isChecked(),
                "fullscreen_on_start": self.fullscreen_cb.isChecked(),
                "camera_visible": self.camera_dock_cb.isChecked(),
                "recording_visible": self.recording_dock_cb.isChecked(),
                "playback_visible": self.playback_dock_cb.isChecked(),
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
