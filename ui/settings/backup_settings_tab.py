"""
Backup Settings Tab
백업 설정 탭 (backup 항목)
"""

import os
import shutil
from pathlib import Path
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QCheckBox, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QFont
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class BackupSettingsTab(BaseSettingsTab):
    """
    백업 설정 탭
    - 백업 경로
    - MD5 검증 옵션
    - 백업 후 원본 삭제 옵션
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # Backup Destination Group
        dest_group = QGroupBox("Backup Destination")
        dest_layout = QVBoxLayout()

        # Path selection
        path_layout = QHBoxLayout()
        self.destination_path_edit = QLineEdit()
        self.destination_path_edit.setPlaceholderText("Select backup destination path...")
        self.destination_path_edit.textChanged.connect(self._on_path_changed)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_destination)

        path_layout.addWidget(self.destination_path_edit)
        path_layout.addWidget(self.browse_btn)
        dest_layout.addLayout(path_layout)

        # Disk space info
        self.space_info_label = QLabel("Available space: -")
        self.space_info_label.setStyleSheet("color: #999999; font-style: italic;")
        dest_layout.addWidget(self.space_info_label)

        dest_group.setLayout(dest_layout)
        layout.addWidget(dest_group)

        # Backup Options Group
        options_group = QGroupBox("Backup Options")
        options_layout = QFormLayout()

        # Verification
        self.verification_cb = QCheckBox("Verify files with MD5 hash")
        self.verification_cb.setToolTip(
            "Verify file integrity after backup using MD5 checksum.\n"
            "This ensures files are copied correctly but takes longer."
        )
        self.verification_cb.setChecked(True)
        options_layout.addRow(self.verification_cb)

        # Delete after backup
        self.delete_after_cb = QCheckBox("Delete source files after successful backup")
        self.delete_after_cb.setToolTip(
            "Automatically delete source files after backup is complete and verified.\n"
            "WARNING: This is permanent and cannot be undone!"
        )
        self.delete_after_cb.setChecked(False)
        self.delete_after_cb.toggled.connect(self._on_delete_after_toggled)
        options_layout.addRow(self.delete_after_cb)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Warning Label
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            "background-color: #ff4444; "
            "color: #ffffff; "
            "padding: 10px; "
            "border-radius: 5px; "
            "font-weight: bold;"
        )
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

        layout.addStretch()

        logger.debug("BackupSettingsTab UI setup complete")

    def _browse_destination(self):
        """백업 경로 선택"""
        current_path = self.destination_path_edit.text()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Destination",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if path:
            self.destination_path_edit.setText(path)

    def _on_path_changed(self, path: str):
        """경로 변경 시 여유 공간 업데이트"""
        if path and os.path.exists(path):
            try:
                stat = shutil.disk_usage(path)
                free_gb = stat.free / (1024 ** 3)
                total_gb = stat.total / (1024 ** 3)
                used_percent = (stat.used / stat.total) * 100

                self.space_info_label.setText(
                    f"Available space: {free_gb:.2f} GB / {total_gb:.2f} GB "
                    f"({100 - used_percent:.1f}% free)"
                )

                # 여유 공간이 10GB 미만이면 경고
                if free_gb < 10:
                    self.space_info_label.setStyleSheet(
                        "color: #ff4444; font-weight: bold;"
                    )
                else:
                    self.space_info_label.setStyleSheet(
                        "color: #999999; font-style: italic;"
                    )

            except Exception as e:
                logger.warning(f"Failed to get disk usage: {e}")
                self.space_info_label.setText("Available space: Unknown")
        else:
            self.space_info_label.setText("Available space: -")

    def _on_delete_after_toggled(self, checked: bool):
        """Delete after backup 옵션 토글 시 경고 표시"""
        if checked:
            self.warning_label.setText(
                "⚠ WARNING: Source files will be PERMANENTLY DELETED after backup!\n"
                "Make sure the backup destination is reliable and has enough space."
            )
            self.warning_label.show()
        else:
            self.warning_label.hide()

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            backup = config.get("backup", {})

            # Destination path
            destination_path = backup.get("destination_path", "")
            self.destination_path_edit.setText(destination_path)

            # Verification
            self.verification_cb.setChecked(backup.get("verification", True))

            # Delete after backup
            delete_after = backup.get("delete_after_backup", False)
            self.delete_after_cb.setChecked(delete_after)

            # Show warning if delete_after is enabled
            if delete_after:
                self._on_delete_after_toggled(True)

            # Store original data
            self._store_original_data({
                "destination_path": destination_path,
                "verification": backup.get("verification", True),
                "delete_after_backup": delete_after,
            })

            logger.debug("BackupSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load backup settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            # backup 섹션이 없으면 생성
            if "backup" not in config:
                config["backup"] = {}

            # Backup settings 업데이트
            config["backup"]["destination_path"] = self.destination_path_edit.text().strip()
            config["backup"]["verification"] = self.verification_cb.isChecked()
            config["backup"]["delete_after_backup"] = self.delete_after_cb.isChecked()

            # ConfigManager를 통해 저장
            self.config_manager.save_config()

            logger.info("Backup settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save backup settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        destination_path = self.destination_path_edit.text().strip()

        # 경로가 비어있으면 경고 (필수는 아님)
        if not destination_path:
            return True, ""  # 경고만 하고 통과

        # 경로가 존재하는지 확인
        if not os.path.exists(destination_path):
            return False, f"Backup destination path does not exist:\n{destination_path}"

        # 쓰기 권한 확인
        if not os.access(destination_path, os.W_OK):
            return False, f"No write permission for backup destination:\n{destination_path}"

        # 여유 공간 확인 (10GB 미만이면 경고)
        try:
            stat = shutil.disk_usage(destination_path)
            free_gb = stat.free / (1024 ** 3)

            if free_gb < 10:
                # 경고만 하고 통과 (사용자가 선택)
                logger.warning(f"Low disk space at backup destination: {free_gb:.2f} GB")

        except Exception as e:
            logger.warning(f"Failed to check disk space: {e}")

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()
            current = {
                "destination_path": self.destination_path_edit.text().strip(),
                "verification": self.verification_cb.isChecked(),
                "delete_after_backup": self.delete_after_cb.isChecked(),
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False