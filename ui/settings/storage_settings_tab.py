"""
Storage Settings Tab
스토리지 설정 탭 (storage 항목)
"""

import shutil
from PyQt5.QtWidgets import (
    QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class StorageSettingsTab(BaseSettingsTab):
    """
    스토리지 설정 탭
    - 자동 정리 설정
    - 디스크 공간 관리
    - 보관 정책
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

        # Recording Path Group (moved from recording_settings_tab)
        from PyQt5.QtWidgets import QLineEdit, QFileDialog, QPushButton, QHBoxLayout
        import os

        path_group = QGroupBox("Recording Path")
        path_layout = QVBoxLayout()

        # Base path selection
        base_path_layout = QHBoxLayout()
        self.recording_path_edit = QLineEdit()
        self.recording_path_edit.setPlaceholderText("Select recording path...")
        self.recording_path_edit.setToolTip("Base directory for all recordings")

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_recording_path)

        base_path_layout.addWidget(self.recording_path_edit)
        base_path_layout.addWidget(self.browse_btn)
        path_layout.addLayout(base_path_layout)

        # Path preview
        from PyQt5.QtWidgets import QLabel
        self.path_preview_label = QLabel()
        self.path_preview_label.setWordWrap(True)
        self.path_preview_label.setStyleSheet(
            "color: #999999; font-style: italic; padding: 5px; "
            "background-color: #3a3a3a; border-radius: 3px;"
        )
        path_layout.addWidget(self.path_preview_label)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # Auto Cleanup Group
        cleanup_group = QGroupBox("Auto Cleanup")
        cleanup_layout = QVBoxLayout()

        self.auto_cleanup_cb = QCheckBox("Enable Auto Cleanup")
        self.auto_cleanup_cb.setToolTip(
            "Automatically delete old recordings when disk space is low"
        )
        self.auto_cleanup_cb.toggled.connect(self._on_auto_cleanup_toggled)
        cleanup_layout.addWidget(self.auto_cleanup_cb)

        cleanup_form = QFormLayout()

        self.cleanup_interval_spin = QSpinBox()
        self.cleanup_interval_spin.setRange(1, 168)  # 1 hour ~ 1 week
        self.cleanup_interval_spin.setSuffix(" hours")
        self.cleanup_interval_spin.setToolTip("How often to check for cleanup")
        cleanup_form.addRow("Cleanup Interval:", self.cleanup_interval_spin)

        self.cleanup_on_startup_cb = QCheckBox("Run cleanup on startup")
        self.cleanup_on_startup_cb.setToolTip(
            "Check and cleanup old recordings when application starts"
        )
        cleanup_form.addRow(self.cleanup_on_startup_cb)

        self.delete_priority_combo = QComboBox()
        self.delete_priority_combo.addItems(["oldest_first", "largest_first"])
        self.delete_priority_combo.setToolTip(
            "oldest_first: Delete oldest recordings first\n"
            "largest_first: Delete largest files first"
        )
        cleanup_form.addRow("Delete Priority:", self.delete_priority_combo)

        cleanup_layout.addLayout(cleanup_form)
        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)

        # Space Management Group
        space_group = QGroupBox("Space Management")
        space_form = QFormLayout()

        self.min_free_space_gb_spin = QDoubleSpinBox()
        self.min_free_space_gb_spin.setRange(1.0, 1000.0)
        self.min_free_space_gb_spin.setSingleStep(1.0)
        self.min_free_space_gb_spin.setSuffix(" GB")
        self.min_free_space_gb_spin.setDecimals(1)
        self.min_free_space_gb_spin.setToolTip(
            "Minimum free space required before cleanup"
        )
        space_form.addRow("Min Free Space:", self.min_free_space_gb_spin)

        self.min_free_space_percent_spin = QSpinBox()
        self.min_free_space_percent_spin.setRange(1, 50)
        self.min_free_space_percent_spin.setSuffix(" %")
        self.min_free_space_percent_spin.setToolTip(
            "Minimum free space percentage before cleanup"
        )
        space_form.addRow("Min Free Space %:", self.min_free_space_percent_spin)

        self.cleanup_threshold_spin = QSpinBox()
        self.cleanup_threshold_spin.setRange(50, 99)
        self.cleanup_threshold_spin.setSuffix(" %")
        self.cleanup_threshold_spin.setToolTip(
            "Start cleanup when disk usage exceeds this threshold"
        )
        space_form.addRow("Cleanup Threshold:", self.cleanup_threshold_spin)

        space_group.setLayout(space_form)
        layout.addWidget(space_group)

        # Retention Policy Group
        retention_group = QGroupBox("Retention Policy")
        retention_form = QFormLayout()

        self.retention_days_spin = QSpinBox()
        self.retention_days_spin.setRange(1, 3650)  # 1 day ~ 10 years
        self.retention_days_spin.setSuffix(" days")
        self.retention_days_spin.setToolTip(
            "Automatically delete recordings older than this"
        )
        retention_form.addRow("Retention Days:", self.retention_days_spin)

        self.delete_batch_size_spin = QSpinBox()
        self.delete_batch_size_spin.setRange(1, 100)
        self.delete_batch_size_spin.setToolTip(
            "Number of files to delete per batch"
        )
        retention_form.addRow("Delete Batch Size:", self.delete_batch_size_spin)

        self.delete_batch_delay_spin = QSpinBox()
        self.delete_batch_delay_spin.setRange(0, 60)
        self.delete_batch_delay_spin.setSuffix(" sec")
        self.delete_batch_delay_spin.setToolTip(
            "Delay between batch deletions (0 for no delay)"
        )
        retention_form.addRow("Batch Delay:", self.delete_batch_delay_spin)

        retention_group.setLayout(retention_form)
        layout.addWidget(retention_group)

        # Current Storage Status Group
        status_group = QGroupBox("Current Storage Status")
        status_layout = QVBoxLayout()

        self.storage_status_label = QLabel()
        self.storage_status_label.setWordWrap(True)
        self.storage_status_label.setStyleSheet(
            "padding: 10px; background-color: #3a3a3a; "
            "border-radius: 5px; font-family: monospace;"
        )
        status_layout.addWidget(self.storage_status_label)

        refresh_btn_layout = QVBoxLayout()
        from PyQt5.QtWidgets import QPushButton
        self.refresh_btn = QPushButton("Refresh Storage Info")
        self.refresh_btn.clicked.connect(self._update_storage_status)
        refresh_btn_layout.addWidget(self.refresh_btn)
        status_layout.addLayout(refresh_btn_layout)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

        scroll.setWidget(scroll_content)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Apply theme
        self.apply_theme()

        logger.debug("StorageSettingsTab UI setup complete")

    def _browse_recording_path(self):
        """녹화 경로 선택"""
        import os
        current_path = self.recording_path_edit.text()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")

        from PyQt5.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Recording Path",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if path:
            self.recording_path_edit.setText(path)
            self._update_path_preview()

    def _update_path_preview(self):
        """경로 미리보기 업데이트"""
        recording_path = self.recording_path_edit.text().strip()

        if recording_path:
            # Example preview
            preview = (
                f"Example: {recording_path}/cam_01/20251103/cam_01_20251103_143000.mkv\n"
                f"Recordings will be organized by camera and date"
            )
            self.path_preview_label.setText(preview)
        else:
            self.path_preview_label.setText("Select a recording path to see preview")

    def _on_auto_cleanup_toggled(self, checked: bool):
        """자동 정리 토글 시 관련 위젯 활성화/비활성화"""
        self.cleanup_interval_spin.setEnabled(checked)
        self.cleanup_on_startup_cb.setEnabled(checked)
        self.delete_priority_combo.setEnabled(checked)
        self.min_free_space_gb_spin.setEnabled(checked)
        self.min_free_space_percent_spin.setEnabled(checked)
        self.cleanup_threshold_spin.setEnabled(checked)
        self.retention_days_spin.setEnabled(checked)
        self.delete_batch_size_spin.setEnabled(checked)
        self.delete_batch_delay_spin.setEnabled(checked)

    def _update_storage_status(self):
        """현재 스토리지 상태 업데이트"""
        try:
            # Get recording path from config (storage.recording_path 사용)
            config = self.config_manager.config
            recording_path = config.get("storage", {}).get("recording_path", "")

            if not recording_path:
                self.storage_status_label.setText(
                    "Recording path not configured.\n"
                    "Please set the recording path in Recording Settings tab."
                )
                return

            import os
            if not os.path.exists(recording_path):
                self.storage_status_label.setText(
                    f"Recording path does not exist:\n{recording_path}"
                )
                return

            # Get disk usage
            stat = shutil.disk_usage(recording_path)
            total_gb = stat.total / (1024 ** 3)
            used_gb = stat.used / (1024 ** 3)
            free_gb = stat.free / (1024 ** 3)
            used_percent = (stat.used / stat.total) * 100

            # Get recording files count and total size
            recording_size = 0
            recording_count = 0
            try:
                for root, dirs, files in os.walk(recording_path):
                    for file in files:
                        if file.endswith(('.mp4', '.mkv', '.avi')):
                            file_path = os.path.join(root, file)
                            recording_size += os.path.getsize(file_path)
                            recording_count += 1
            except Exception as e:
                logger.warning(f"Failed to scan recordings: {e}")

            recording_size_gb = recording_size / (1024 ** 3)

            # Format status text
            status_text = (
                f"Recording Path: {recording_path}\n"
                f"\n"
                f"Disk Usage:\n"
                f"  Total: {total_gb:.2f} GB\n"
                f"  Used:  {used_gb:.2f} GB ({used_percent:.1f}%)\n"
                f"  Free:  {free_gb:.2f} GB ({100 - used_percent:.1f}%)\n"
                f"\n"
                f"Recordings:\n"
                f"  Files: {recording_count}\n"
                f"  Size:  {recording_size_gb:.2f} GB"
            )

            self.storage_status_label.setText(status_text)

            # Color code based on free space
            if free_gb < 10:
                self.storage_status_label.setStyleSheet(
                    "padding: 10px; background-color: #ff4444; "
                    "color: #ffffff; border-radius: 5px; "
                    "font-family: monospace; font-weight: bold;"
                )
            elif free_gb < 50:
                self.storage_status_label.setStyleSheet(
                    "padding: 10px; background-color: #ff9944; "
                    "color: #000000; border-radius: 5px; "
                    "font-family: monospace; font-weight: bold;"
                )
            else:
                self.storage_status_label.setStyleSheet(
                    "padding: 10px; background-color: #3a3a3a; "
                    "border-radius: 5px; font-family: monospace;"
                )

        except Exception as e:
            logger.error(f"Failed to update storage status: {e}")
            self.storage_status_label.setText(f"Error: {str(e)}")

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            storage = config.get("storage", {})

            # Recording path
            recording_path = storage.get("recording_path", "")
            self.recording_path_edit.setText(recording_path)
            self._update_path_preview()

            # Auto cleanup
            auto_cleanup = storage.get("auto_cleanup_enabled", True)
            self.auto_cleanup_cb.setChecked(auto_cleanup)

            self.cleanup_interval_spin.setValue(storage.get("cleanup_interval_hours", 6))
            self.cleanup_on_startup_cb.setChecked(storage.get("cleanup_on_startup", True))

            priority = storage.get("auto_delete_priority", "oldest_first")
            idx = self.delete_priority_combo.findText(priority)
            if idx >= 0:
                self.delete_priority_combo.setCurrentIndex(idx)

            # Space management
            self.min_free_space_gb_spin.setValue(storage.get("min_free_space_gb", 10.0))
            self.min_free_space_percent_spin.setValue(storage.get("min_free_space_percent", 5))
            self.cleanup_threshold_spin.setValue(storage.get("cleanup_threshold_percent", 90))

            # Retention policy
            self.retention_days_spin.setValue(storage.get("retention_days", 30))
            self.delete_batch_size_spin.setValue(storage.get("delete_batch_size", 5))
            self.delete_batch_delay_spin.setValue(storage.get("delete_batch_delay_seconds", 1))

            # Enable/disable fields
            self._on_auto_cleanup_toggled(auto_cleanup)

            # Update storage status
            self._update_storage_status()

            # Store original data
            self._store_original_data({
                "recording_path": recording_path,
                "auto_cleanup_enabled": auto_cleanup,
                "cleanup_interval_hours": storage.get("cleanup_interval_hours", 6),
                "cleanup_on_startup": storage.get("cleanup_on_startup", True),
                "auto_delete_priority": priority,
                "min_free_space_gb": storage.get("min_free_space_gb", 10.0),
                "min_free_space_percent": storage.get("min_free_space_percent", 5),
                "cleanup_threshold_percent": storage.get("cleanup_threshold_percent", 90),
                "retention_days": storage.get("retention_days", 30),
                "delete_batch_size": storage.get("delete_batch_size", 5),
                "delete_batch_delay_seconds": storage.get("delete_batch_delay_seconds", 1),
            })

            logger.debug("StorageSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load storage settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            if "storage" not in config:
                config["storage"] = {}

            # Update settings
            config["storage"]["recording_path"] = self.recording_path_edit.text().strip()
            config["storage"]["auto_cleanup_enabled"] = self.auto_cleanup_cb.isChecked()
            config["storage"]["cleanup_interval_hours"] = self.cleanup_interval_spin.value()
            config["storage"]["cleanup_on_startup"] = self.cleanup_on_startup_cb.isChecked()
            config["storage"]["auto_delete_priority"] = self.delete_priority_combo.currentText()

            config["storage"]["min_free_space_gb"] = self.min_free_space_gb_spin.value()
            config["storage"]["min_free_space_percent"] = self.min_free_space_percent_spin.value()
            config["storage"]["cleanup_threshold_percent"] = self.cleanup_threshold_spin.value()

            config["storage"]["retention_days"] = self.retention_days_spin.value()
            config["storage"]["delete_batch_size"] = self.delete_batch_size_spin.value()
            config["storage"]["delete_batch_delay_seconds"] = self.delete_batch_delay_spin.value()

            self.config_manager.save_config()

            logger.info("Storage settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save storage settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        import os
        recording_path = self.recording_path_edit.text().strip()

        # 경로가 비어있으면 에러
        if not recording_path:
            return False, "Recording path is required"

        # 경로가 존재하지 않으면 생성 시도
        if not os.path.exists(recording_path):
            try:
                os.makedirs(recording_path, exist_ok=True)
                logger.info(f"Created recording directory: {recording_path}")
            except Exception as e:
                return False, f"Failed to create recording directory:\n{recording_path}\n{str(e)}"

        # 쓰기 권한 확인
        if not os.access(recording_path, os.W_OK):
            return False, f"No write permission for recording path:\n{recording_path}"

        # Min free space validation
        min_free_gb = self.min_free_space_gb_spin.value()
        if min_free_gb < 1.0:
            return False, "Minimum free space must be at least 1 GB"

        # Cleanup threshold validation
        threshold = self.cleanup_threshold_spin.value()
        if threshold < 50 or threshold > 99:
            return False, "Cleanup threshold must be between 50% and 99%"

        # Retention days validation
        retention = self.retention_days_spin.value()
        if retention < 1:
            return False, "Retention days must be at least 1"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            current = {
                "recording_path": self.recording_path_edit.text().strip(),
                "auto_cleanup_enabled": self.auto_cleanup_cb.isChecked(),
                "cleanup_interval_hours": self.cleanup_interval_spin.value(),
                "cleanup_on_startup": self.cleanup_on_startup_cb.isChecked(),
                "auto_delete_priority": self.delete_priority_combo.currentText(),
                "min_free_space_gb": self.min_free_space_gb_spin.value(),
                "min_free_space_percent": self.min_free_space_percent_spin.value(),
                "cleanup_threshold_percent": self.cleanup_threshold_spin.value(),
                "retention_days": self.retention_days_spin.value(),
                "delete_batch_size": self.delete_batch_size_spin.value(),
                "delete_batch_delay_seconds": self.delete_batch_delay_spin.value(),
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
