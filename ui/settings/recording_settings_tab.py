"""
Recording Settings Tab
녹화 설정 탭 (recording 항목)
"""

import os
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QComboBox, QSpinBox, QFileDialog
)
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class RecordingSettingsTab(BaseSettingsTab):
    """
    녹화 설정 탭
    - 녹화 경로
    - 파일 포맷
    - 코덱
    - 파일 분할 시간
    - Fragment duration
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # Recording Path Group
        path_group = QGroupBox("Recording Path")
        path_layout = QVBoxLayout()

        # Base path selection
        base_path_layout = QHBoxLayout()
        self.base_path_edit = QLineEdit()
        self.base_path_edit.setPlaceholderText("Select recording base path...")
        self.base_path_edit.setToolTip("Base directory for all recordings")

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_base_path)

        base_path_layout.addWidget(self.base_path_edit)
        base_path_layout.addWidget(self.browse_btn)
        path_layout.addLayout(base_path_layout)

        # Path preview
        self.path_preview_label = QLabel()
        self.path_preview_label.setWordWrap(True)
        self.path_preview_label.setStyleSheet(
            "color: #999999; font-style: italic; padding: 5px; "
            "background-color: #3a3a3a; border-radius: 3px;"
        )
        path_layout.addWidget(self.path_preview_label)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # Recording Format Group
        format_group = QGroupBox("Recording Format")
        format_layout = QFormLayout()

        # File format
        self.file_format_combo = QComboBox()
        self.file_format_combo.addItems(["mkv", "mp4", "avi"])
        self.file_format_combo.setToolTip("Container format for recording files")
        self.file_format_combo.currentTextChanged.connect(self._update_preview)
        format_layout.addRow("File Format:", self.file_format_combo)

        # Codec
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["h264", "h265"])
        self.codec_combo.setToolTip("Video codec (h264 recommended for compatibility)")
        format_layout.addRow("Codec:", self.codec_combo)

        # Fragment duration
        self.fragment_duration_spin = QSpinBox()
        self.fragment_duration_spin.setRange(100, 10000)
        self.fragment_duration_spin.setSingleStep(100)
        self.fragment_duration_spin.setSuffix(" ms")
        self.fragment_duration_spin.setToolTip(
            "Fragment duration for MP4 muxer.\n"
            "Lower values improve seekability but increase file overhead."
        )
        format_layout.addRow("Fragment Duration:", self.fragment_duration_spin)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # File Rotation Group
        rotation_group = QGroupBox("File Rotation")
        rotation_layout = QFormLayout()

        # Rotation minutes
        self.rotation_minutes_spin = QSpinBox()
        self.rotation_minutes_spin.setRange(1, 1440)  # 1분 ~ 24시간
        self.rotation_minutes_spin.setSingleStep(1)
        self.rotation_minutes_spin.setSuffix(" minutes")
        self.rotation_minutes_spin.setToolTip(
            "Recording file will be split every N minutes.\n"
            "Smaller values create more files but easier to manage."
        )
        self.rotation_minutes_spin.valueChanged.connect(self._update_preview)
        rotation_layout.addRow("Rotation Interval:", self.rotation_minutes_spin)

        # Rotation info
        self.rotation_info_label = QLabel()
        self.rotation_info_label.setWordWrap(True)
        self.rotation_info_label.setStyleSheet("color: #999999; font-style: italic;")
        rotation_layout.addRow(self.rotation_info_label)

        rotation_group.setLayout(rotation_layout)
        layout.addWidget(rotation_group)

        layout.addStretch()

        # Apply theme
        self.apply_theme()

        logger.debug("RecordingSettingsTab UI setup complete")

    def _browse_base_path(self):
        """녹화 경로 선택"""
        current_path = self.base_path_edit.text()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self,
            "Select Recording Base Path",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if path:
            self.base_path_edit.setText(path)
            self._update_preview()

    def _update_preview(self):
        """경로 미리보기 업데이트"""
        base_path = self.base_path_edit.text().strip()
        file_format = self.file_format_combo.currentText()
        rotation_minutes = self.rotation_minutes_spin.value()

        if base_path:
            # Example preview
            preview = (
                f"Example: {base_path}/cam_01/2025-11-03/cam_01_20251103_143000.{file_format}\n"
                f"Files will be split every {rotation_minutes} minutes"
            )
            self.path_preview_label.setText(preview)
        else:
            self.path_preview_label.setText("Select a base path to see preview")

        # Rotation info
        hours = rotation_minutes / 60
        if hours >= 1:
            self.rotation_info_label.setText(f"≈ {hours:.1f} hours per file")
        else:
            self.rotation_info_label.setText(f"{rotation_minutes} minutes per file")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            recording = config.get("recording", {})

            # Base path
            base_path = recording.get("base_path", "")
            self.base_path_edit.setText(base_path)

            # File format
            file_format = recording.get("file_format", "mkv")
            format_idx = self.file_format_combo.findText(file_format)
            if format_idx >= 0:
                self.file_format_combo.setCurrentIndex(format_idx)

            # Codec
            codec = recording.get("codec", "h264")
            codec_idx = self.codec_combo.findText(codec)
            if codec_idx >= 0:
                self.codec_combo.setCurrentIndex(codec_idx)

            # Fragment duration
            fragment_duration = recording.get("fragment_duration_ms", 1000)
            self.fragment_duration_spin.setValue(fragment_duration)

            # Rotation minutes
            rotation_minutes = recording.get("rotation_minutes", 60)
            self.rotation_minutes_spin.setValue(rotation_minutes)

            # Update preview
            self._update_preview()

            # Store original data
            self._store_original_data({
                "base_path": base_path,
                "file_format": file_format,
                "codec": codec,
                "fragment_duration_ms": fragment_duration,
                "rotation_minutes": rotation_minutes,
            })

            logger.debug("RecordingSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load recording settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            # recording 섹션이 없으면 생성
            if "recording" not in config:
                config["recording"] = {}

            # Recording settings 업데이트
            config["recording"]["base_path"] = self.base_path_edit.text().strip()
            config["recording"]["file_format"] = self.file_format_combo.currentText()
            config["recording"]["codec"] = self.codec_combo.currentText()
            config["recording"]["fragment_duration_ms"] = self.fragment_duration_spin.value()
            config["recording"]["rotation_minutes"] = self.rotation_minutes_spin.value()

            # ConfigManager를 통해 저장
            self.config_manager.save_config()

            logger.info("Recording settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save recording settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        base_path = self.base_path_edit.text().strip()

        # 경로가 비어있으면 에러
        if not base_path:
            return False, "Recording base path is required"

        # 경로가 존재하지 않으면 생성 시도
        if not os.path.exists(base_path):
            try:
                os.makedirs(base_path, exist_ok=True)
                logger.info(f"Created recording directory: {base_path}")
            except Exception as e:
                return False, f"Failed to create recording directory:\n{base_path}\n{str(e)}"

        # 쓰기 권한 확인
        if not os.access(base_path, os.W_OK):
            return False, f"No write permission for recording path:\n{base_path}"

        # Rotation minutes 검증 (1 ~ 1440분)
        rotation_minutes = self.rotation_minutes_spin.value()
        if rotation_minutes < 1 or rotation_minutes > 1440:
            return False, "Rotation interval must be between 1 and 1440 minutes"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            current = {
                "base_path": self.base_path_edit.text().strip(),
                "file_format": self.file_format_combo.currentText(),
                "codec": self.codec_combo.currentText(),
                "fragment_duration_ms": self.fragment_duration_spin.value(),
                "rotation_minutes": self.rotation_minutes_spin.value(),
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
