"""
Logging Settings Tab
로깅 설정 탭 (logging 항목)
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QCheckBox, QSpinBox, QComboBox, QLineEdit,
    QScrollArea, QWidget, QPushButton, QHBoxLayout,
    QFileDialog
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class LoggingSettingsTab(BaseSettingsTab):
    """
    로깅 설정 탭
    - 로깅 활성화/비활성화
    - 로그 파일 경로
    - 콘솔 로그 설정
    - 파일 로그 설정
    - 에러 로그 설정
    - JSON 로그 설정
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        # 스크롤 가능하게 설정
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # Main Logging Group
        main_group = QGroupBox("Main Settings")
        main_layout = QVBoxLayout()

        self.logging_enabled_cb = QCheckBox("Enable Logging")
        self.logging_enabled_cb.setToolTip("Enable or disable entire logging system")
        self.logging_enabled_cb.toggled.connect(self._on_logging_enabled_toggled)
        main_layout.addWidget(self.logging_enabled_cb)

        # Log path
        log_path_layout = QHBoxLayout()
        log_path_label = QLabel("Log Path:")
        self.log_path_edit = QLineEdit()
        self.log_path_edit.setPlaceholderText("Log files directory...")
        self.log_path_edit.setToolTip("Directory where log files will be saved")

        self.browse_log_path_btn = QPushButton("Browse...")
        self.browse_log_path_btn.clicked.connect(self._browse_log_path)

        log_path_layout.addWidget(log_path_label)
        log_path_layout.addWidget(self.log_path_edit, 1)
        log_path_layout.addWidget(self.browse_log_path_btn)
        main_layout.addLayout(log_path_layout)

        main_group.setLayout(main_layout)
        layout.addWidget(main_group)

        # Console Log Group
        console_group = QGroupBox("Console Log")
        console_layout = QVBoxLayout()

        self.console_enabled_cb = QCheckBox("Enable Console Logging")
        self.console_enabled_cb.setToolTip("Show logs in console/terminal")
        console_layout.addWidget(self.console_enabled_cb)

        console_form = QFormLayout()

        self.console_level_combo = QComboBox()
        self.console_level_combo.addItems(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.console_level_combo.setToolTip("Minimum log level for console output")
        console_form.addRow("Log Level:", self.console_level_combo)

        self.console_colorize_cb = QCheckBox("Colorize console output")
        self.console_colorize_cb.setToolTip("Use colors in console logs")
        console_form.addRow(self.console_colorize_cb)

        self.console_format_edit = QLineEdit()
        self.console_format_edit.setToolTip("Loguru format string for console logs")
        console_form.addRow("Format:", self.console_format_edit)

        console_layout.addLayout(console_form)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)

        # File Log Group
        file_group = QGroupBox("File Log")
        file_layout = QVBoxLayout()

        self.file_enabled_cb = QCheckBox("Enable File Logging")
        self.file_enabled_cb.setToolTip("Save logs to files")
        file_layout.addWidget(self.file_enabled_cb)

        file_form = QFormLayout()

        self.file_level_combo = QComboBox()
        self.file_level_combo.addItems(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.file_level_combo.setToolTip("Minimum log level for file output")
        file_form.addRow("Log Level:", self.file_level_combo)

        self.file_filename_edit = QLineEdit()
        self.file_filename_edit.setPlaceholderText("pynvr_{time:YYYY-MM-DD}.log")
        self.file_filename_edit.setToolTip("Log file name pattern (supports Loguru time format)")
        file_form.addRow("Filename:", self.file_filename_edit)

        self.file_format_edit = QLineEdit()
        self.file_format_edit.setToolTip("Loguru format string for file logs")
        file_form.addRow("Format:", self.file_format_edit)

        self.file_rotation_edit = QLineEdit()
        self.file_rotation_edit.setPlaceholderText("1 day, 10 MB, etc.")
        self.file_rotation_edit.setToolTip("When to rotate log file (e.g., '1 day', '100 MB')")
        file_form.addRow("Rotation:", self.file_rotation_edit)

        self.file_retention_edit = QLineEdit()
        self.file_retention_edit.setPlaceholderText("7 days, 10 files, etc.")
        self.file_retention_edit.setToolTip("How long to keep rotated logs (e.g., '7 days', '10 files')")
        file_form.addRow("Retention:", self.file_retention_edit)

        self.file_compression_edit = QLineEdit()
        self.file_compression_edit.setPlaceholderText("zip, gz, etc.")
        self.file_compression_edit.setToolTip("Compression format for rotated logs (zip, gz, bz2, xz)")
        file_form.addRow("Compression:", self.file_compression_edit)

        self.file_max_size_spin = QSpinBox()
        self.file_max_size_spin.setRange(1, 10000)
        self.file_max_size_spin.setSuffix(" MB")
        self.file_max_size_spin.setToolTip("Maximum size of log file before rotation")
        file_form.addRow("Max Size:", self.file_max_size_spin)

        self.file_rotation_count_spin = QSpinBox()
        self.file_rotation_count_spin.setRange(1, 100)
        self.file_rotation_count_spin.setToolTip("Maximum number of rotated log files to keep")
        file_form.addRow("Rotation Count:", self.file_rotation_count_spin)

        file_layout.addLayout(file_form)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Error Log Group
        error_group = QGroupBox("Error Log")
        error_layout = QVBoxLayout()

        self.error_enabled_cb = QCheckBox("Enable Error Logging")
        self.error_enabled_cb.setToolTip("Separate log file for errors only")
        error_layout.addWidget(self.error_enabled_cb)

        error_form = QFormLayout()

        self.error_filename_edit = QLineEdit()
        self.error_filename_edit.setPlaceholderText("pynvr_errors_{time:YYYY-MM-DD}.log")
        self.error_filename_edit.setToolTip("Error log file name pattern")
        error_form.addRow("Filename:", self.error_filename_edit)

        self.error_level_combo = QComboBox()
        self.error_level_combo.addItems(["WARNING", "ERROR", "CRITICAL"])
        self.error_level_combo.setToolTip("Minimum log level for error log")
        error_form.addRow("Log Level:", self.error_level_combo)

        self.error_rotation_edit = QLineEdit()
        self.error_rotation_edit.setPlaceholderText("10 MB")
        self.error_rotation_edit.setToolTip("When to rotate error log file")
        error_form.addRow("Rotation:", self.error_rotation_edit)

        self.error_retention_edit = QLineEdit()
        self.error_retention_edit.setPlaceholderText("30 days")
        self.error_retention_edit.setToolTip("How long to keep rotated error logs")
        error_form.addRow("Retention:", self.error_retention_edit)

        error_layout.addLayout(error_form)
        error_group.setLayout(error_layout)
        layout.addWidget(error_group)

        # JSON Log Group
        json_group = QGroupBox("JSON Log (Structured)")
        json_layout = QVBoxLayout()

        self.json_enabled_cb = QCheckBox("Enable JSON Logging")
        self.json_enabled_cb.setToolTip("Save logs in JSON format for parsing")
        json_layout.addWidget(self.json_enabled_cb)

        json_form = QFormLayout()

        self.json_filename_edit = QLineEdit()
        self.json_filename_edit.setPlaceholderText("pynvr_{time:YYYY-MM-DD}.json")
        self.json_filename_edit.setToolTip("JSON log file name pattern")
        json_form.addRow("Filename:", self.json_filename_edit)

        self.json_serialize_cb = QCheckBox("Serialize log records")
        self.json_serialize_cb.setToolTip("Serialize entire log record to JSON")
        json_form.addRow(self.json_serialize_cb)

        json_layout.addLayout(json_form)
        json_group.setLayout(json_layout)
        layout.addWidget(json_group)

        # Info note
        info_label = QLabel(
            "<b>Note:</b> Changes to logging settings will take effect after application restart."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "padding: 10px; background-color: #3a3a3a; "
            "border-radius: 5px; color: #ffaa00;"
        )
        layout.addWidget(info_label)

        layout.addStretch()

        scroll.setWidget(scroll_content)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        logger.debug("LoggingSettingsTab UI setup complete")

    def _browse_log_path(self):
        """로그 경로 선택"""
        import os
        current_path = self.log_path_edit.text()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self,
            "Select Log Path",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if path:
            self.log_path_edit.setText(path)

    def _on_logging_enabled_toggled(self, checked: bool):
        """로깅 활성화 토글 시 관련 위젯 활성화/비활성화"""
        # Console group
        self.console_enabled_cb.setEnabled(checked)
        self.console_level_combo.setEnabled(checked)
        self.console_colorize_cb.setEnabled(checked)
        self.console_format_edit.setEnabled(checked)

        # File group
        self.file_enabled_cb.setEnabled(checked)
        self.file_level_combo.setEnabled(checked)
        self.file_filename_edit.setEnabled(checked)
        self.file_format_edit.setEnabled(checked)
        self.file_rotation_edit.setEnabled(checked)
        self.file_retention_edit.setEnabled(checked)
        self.file_compression_edit.setEnabled(checked)
        self.file_max_size_spin.setEnabled(checked)
        self.file_rotation_count_spin.setEnabled(checked)

        # Error group
        self.error_enabled_cb.setEnabled(checked)
        self.error_filename_edit.setEnabled(checked)
        self.error_level_combo.setEnabled(checked)
        self.error_rotation_edit.setEnabled(checked)
        self.error_retention_edit.setEnabled(checked)

        # JSON group
        self.json_enabled_cb.setEnabled(checked)
        self.json_filename_edit.setEnabled(checked)
        self.json_serialize_cb.setEnabled(checked)

        # Log path
        self.log_path_edit.setEnabled(checked)
        self.browse_log_path_btn.setEnabled(checked)

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            logging_config = config.get("logging", {})

            # Main settings
            enabled = logging_config.get("enabled", True)
            self.logging_enabled_cb.setChecked(enabled)
            self.log_path_edit.setText(logging_config.get("log_path", "./_logs"))

            # Console settings
            console = logging_config.get("console", {})
            self.console_enabled_cb.setChecked(console.get("enabled", True))

            console_level = console.get("level", "DEBUG")
            idx = self.console_level_combo.findText(console_level)
            if idx >= 0:
                self.console_level_combo.setCurrentIndex(idx)

            self.console_colorize_cb.setChecked(console.get("colorize", True))
            self.console_format_edit.setText(
                console.get("format", "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
            )

            # File settings
            file_config = logging_config.get("file", {})
            self.file_enabled_cb.setChecked(file_config.get("enabled", True))

            file_level = file_config.get("level", "DEBUG")
            idx = self.file_level_combo.findText(file_level)
            if idx >= 0:
                self.file_level_combo.setCurrentIndex(idx)

            self.file_filename_edit.setText(file_config.get("filename", "pynvr_{time:YYYY-MM-DD}.log"))
            self.file_format_edit.setText(
                file_config.get("format", "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")
            )
            self.file_rotation_edit.setText(file_config.get("rotation", "1 day"))
            self.file_retention_edit.setText(file_config.get("retention", "7 days"))
            self.file_compression_edit.setText(file_config.get("compression", "zip"))
            self.file_max_size_spin.setValue(file_config.get("max_size_mb", 100))
            self.file_rotation_count_spin.setValue(file_config.get("rotation_count", 10))

            # Error log settings
            error_config = logging_config.get("error_log", {})
            self.error_enabled_cb.setChecked(error_config.get("enabled", True))
            self.error_filename_edit.setText(
                error_config.get("filename", "pynvr_errors_{time:YYYY-MM-DD}.log")
            )

            error_level = error_config.get("level", "ERROR")
            idx = self.error_level_combo.findText(error_level)
            if idx >= 0:
                self.error_level_combo.setCurrentIndex(idx)

            self.error_rotation_edit.setText(error_config.get("rotation", "10 MB"))
            self.error_retention_edit.setText(error_config.get("retention", "30 days"))

            # JSON log settings
            json_config = logging_config.get("json_log", {})
            self.json_enabled_cb.setChecked(json_config.get("enabled", False))
            self.json_filename_edit.setText(
                json_config.get("filename", "pynvr_{time:YYYY-MM-DD}.json")
            )
            self.json_serialize_cb.setChecked(json_config.get("serialize", True))

            # Enable/disable fields based on main logging enabled state
            self._on_logging_enabled_toggled(enabled)

            # Store original data
            self._store_original_data({
                "enabled": enabled,
                "log_path": logging_config.get("log_path", "./_logs"),
                "console": console.copy(),
                "file": file_config.copy(),
                "error_log": error_config.copy(),
                "json_log": json_config.copy(),
            })

            logger.debug("LoggingSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load logging settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            if "logging" not in config:
                config["logging"] = {}

            # Main settings
            config["logging"]["enabled"] = self.logging_enabled_cb.isChecked()
            config["logging"]["log_path"] = self.log_path_edit.text().strip()

            # Console settings
            config["logging"]["console"] = {
                "enabled": self.console_enabled_cb.isChecked(),
                "level": self.console_level_combo.currentText(),
                "colorize": self.console_colorize_cb.isChecked(),
                "format": self.console_format_edit.text().strip()
            }

            # File settings
            config["logging"]["file"] = {
                "enabled": self.file_enabled_cb.isChecked(),
                "level": self.file_level_combo.currentText(),
                "filename": self.file_filename_edit.text().strip(),
                "format": self.file_format_edit.text().strip(),
                "rotation": self.file_rotation_edit.text().strip(),
                "retention": self.file_retention_edit.text().strip(),
                "compression": self.file_compression_edit.text().strip(),
                "max_size_mb": self.file_max_size_spin.value(),
                "rotation_count": self.file_rotation_count_spin.value()
            }

            # Error log settings
            config["logging"]["error_log"] = {
                "enabled": self.error_enabled_cb.isChecked(),
                "filename": self.error_filename_edit.text().strip(),
                "level": self.error_level_combo.currentText(),
                "rotation": self.error_rotation_edit.text().strip(),
                "retention": self.error_retention_edit.text().strip()
            }

            # JSON log settings
            config["logging"]["json_log"] = {
                "enabled": self.json_enabled_cb.isChecked(),
                "filename": self.json_filename_edit.text().strip(),
                "serialize": self.json_serialize_cb.isChecked()
            }

            logger.debug("Logging settings prepared")
            return True

        except Exception as e:
            logger.error(f"Failed to save logging settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        import os

        # Log path validation
        log_path = self.log_path_edit.text().strip()
        if not log_path:
            return False, "Log path is required"

        # 경로가 존재하지 않으면 생성 시도
        if not os.path.exists(log_path):
            try:
                os.makedirs(log_path, exist_ok=True)
                logger.info(f"Created log directory: {log_path}")
            except Exception as e:
                return False, f"Failed to create log directory:\n{log_path}\n{str(e)}"

        # 쓰기 권한 확인
        if not os.access(log_path, os.W_OK):
            return False, f"No write permission for log path:\n{log_path}"

        # File name validation
        if self.file_enabled_cb.isChecked():
            filename = self.file_filename_edit.text().strip()
            if not filename:
                return False, "File log filename is required when file logging is enabled"

        # Error log filename validation
        if self.error_enabled_cb.isChecked():
            filename = self.error_filename_edit.text().strip()
            if not filename:
                return False, "Error log filename is required when error logging is enabled"

        # JSON log filename validation
        if self.json_enabled_cb.isChecked():
            filename = self.json_filename_edit.text().strip()
            if not filename:
                return False, "JSON log filename is required when JSON logging is enabled"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()

            # Current console settings
            current_console = {
                "enabled": self.console_enabled_cb.isChecked(),
                "level": self.console_level_combo.currentText(),
                "colorize": self.console_colorize_cb.isChecked(),
                "format": self.console_format_edit.text().strip()
            }

            # Current file settings
            current_file = {
                "enabled": self.file_enabled_cb.isChecked(),
                "level": self.file_level_combo.currentText(),
                "filename": self.file_filename_edit.text().strip(),
                "format": self.file_format_edit.text().strip(),
                "rotation": self.file_rotation_edit.text().strip(),
                "retention": self.file_retention_edit.text().strip(),
                "compression": self.file_compression_edit.text().strip(),
                "max_size_mb": self.file_max_size_spin.value(),
                "rotation_count": self.file_rotation_count_spin.value()
            }

            # Current error log settings
            current_error = {
                "enabled": self.error_enabled_cb.isChecked(),
                "filename": self.error_filename_edit.text().strip(),
                "level": self.error_level_combo.currentText(),
                "rotation": self.error_rotation_edit.text().strip(),
                "retention": self.error_retention_edit.text().strip()
            }

            # Current JSON log settings
            current_json = {
                "enabled": self.json_enabled_cb.isChecked(),
                "filename": self.json_filename_edit.text().strip(),
                "serialize": self.json_serialize_cb.isChecked()
            }

            current = {
                "enabled": self.logging_enabled_cb.isChecked(),
                "log_path": self.log_path_edit.text().strip(),
                "console": current_console,
                "file": current_file,
                "error_log": current_error,
                "json_log": current_json,
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
