"""
Settings Dialog
통합 설정 다이얼로그
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QTabWidget, QDialogButtonBox,
    QMessageBox
)
from PyQt5.QtCore import pyqtSignal
from loguru import logger

from core.config import ConfigManager
from ui.theme import ThemedDialog
from ui.settings.basic_settings_tab import BasicSettingsTab
from ui.settings.backup_settings_tab import BackupSettingsTab
from ui.settings.recording_settings_tab import RecordingSettingsTab
from ui.settings.streaming_settings_tab import StreamingSettingsTab
from ui.settings.storage_settings_tab import StorageSettingsTab
from ui.settings.cameras_settings_tab import CamerasSettingsTab
from ui.settings.hotkey_settings_tab import HotKeySettingsTab
from ui.settings.ptz_key_settings_tab import PTZKeySettingsTab
from ui.settings.logging_settings_tab import LoggingSettingsTab
from ui.settings.performance_settings_tab import PerformanceSettingsTab


class SettingsDialog(ThemedDialog):
    """
    메인 설정 다이얼로그
    모든 설정 탭을 통합 관리
    """

    # 설정 변경 시그널
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        """
        초기화

        Args:
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.config_manager = ConfigManager.get_instance()

        # 탭 위젯들 (나중에 추가)
        self.basic_tab = None
        self.cameras_tab = None
        self.streaming_tab = None
        self.recording_tab = None
        self.backup_tab = None
        self.storage_tab = None
        self.performance_tab = None
        self.hotkey_tab = None
        self.ptz_key_tab = None
        self.logging_tab = None

        self._setup_ui()
        self._load_all_settings()

        logger.debug("SettingsDialog initialized")

    def _setup_ui(self):
        """UI 구성"""
        self.setWindowTitle("Settings")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # 탭 위젯
        self.tab_widget = QTabWidget()

        # 탭 추가 (모두 구현 완료)
        self.basic_tab = BasicSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.basic_tab, "Basic")

        self.cameras_tab = CamerasSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.cameras_tab, "Cameras")

        self.streaming_tab = StreamingSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.streaming_tab, "Streaming")

        self.recording_tab = RecordingSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.recording_tab, "Recording")

        self.storage_tab = StorageSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.storage_tab, "Storage")

        self.backup_tab = BackupSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.backup_tab, "Backup")

        self.performance_tab = PerformanceSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.performance_tab, "Performance")

        self.hotkey_tab = HotKeySettingsTab(self.config_manager)
        self.tab_widget.addTab(self.hotkey_tab, "Hot Keys")

        self.ptz_key_tab = PTZKeySettingsTab(self.config_manager)
        self.tab_widget.addTab(self.ptz_key_tab, "PTZ Keys")

        self.logging_tab = LoggingSettingsTab(self.config_manager)
        self.tab_widget.addTab(self.logging_tab, "Logging")

        layout.addWidget(self.tab_widget)

        # 버튼박스
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self._on_cancel)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)

        layout.addWidget(button_box)

        logger.debug("SettingsDialog UI setup complete")

    def _load_all_settings(self):
        """모든 설정 로드"""
        try:
            # 각 탭의 load_settings() 호출
            if self.basic_tab:
                self.basic_tab.load_settings()
            if self.cameras_tab:
                self.cameras_tab.load_settings()
            if self.streaming_tab:
                self.streaming_tab.load_settings()
            if self.recording_tab:
                self.recording_tab.load_settings()
            if self.backup_tab:
                self.backup_tab.load_settings()
            if self.storage_tab:
                self.storage_tab.load_settings()
            if self.performance_tab:
                self.performance_tab.load_settings()
            if self.hotkey_tab:
                self.hotkey_tab.load_settings()
            if self.ptz_key_tab:
                self.ptz_key_tab.load_settings()
            if self.logging_tab:
                self.logging_tab.load_settings()

            logger.debug("All settings loaded")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load settings:\n{str(e)}")

    def _validate_all_settings(self) -> tuple[bool, str]:
        """
        모든 탭 설정 검증

        Returns:
            tuple[bool, str]: (검증 성공 여부, 에러 메시지)
        """
        tabs = []

        if self.basic_tab:
            tabs.append(("Basic", self.basic_tab))
        if self.cameras_tab:
            tabs.append(("Cameras", self.cameras_tab))
        if self.streaming_tab:
            tabs.append(("Streaming", self.streaming_tab))
        if self.recording_tab:
            tabs.append(("Recording", self.recording_tab))
        if self.backup_tab:
            tabs.append(("Backup", self.backup_tab))
        if self.storage_tab:
            tabs.append(("Storage", self.storage_tab))
        if self.performance_tab:
            tabs.append(("Performance", self.performance_tab))
        if self.hotkey_tab:
            tabs.append(("Hot Keys", self.hotkey_tab))
        if self.ptz_key_tab:
            tabs.append(("PTZ Keys", self.ptz_key_tab))
        if self.logging_tab:
            tabs.append(("Logging", self.logging_tab))

        for tab_name, tab in tabs:
            valid, error_msg = tab.validate_settings()
            if not valid:
                return False, f"{tab_name} Tab: {error_msg}"

        return True, ""

    def _save_all_settings(self) -> bool:
        """
        모든 설정 저장 (각 탭은 config dict만 업데이트, 마지막에 한 번만 DB 저장)

        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 검증
            valid, error_msg = self._validate_all_settings()
            if not valid:
                QMessageBox.warning(self, "Validation Error", error_msg)
                logger.warning(f"Settings validation failed: {error_msg}")
                return False

            # 각 탭의 save_settings() 호출 (config dict만 업데이트)
            success = True
            if self.basic_tab:
                success &= self.basic_tab.save_settings()
            if self.cameras_tab:
                success &= self.cameras_tab.save_settings()
            if self.streaming_tab:
                success &= self.streaming_tab.save_settings()
            if self.recording_tab:
                success &= self.recording_tab.save_settings()
            if self.backup_tab:
                success &= self.backup_tab.save_settings()
            if self.storage_tab:
                success &= self.storage_tab.save_settings()
            if self.performance_tab:
                success &= self.performance_tab.save_settings()
            if self.hotkey_tab:
                success &= self.hotkey_tab.save_settings()
            if self.ptz_key_tab:
                success &= self.ptz_key_tab.save_settings()
            if self.logging_tab:
                success &= self.logging_tab.save_settings()

            if not success:
                QMessageBox.warning(self, "Save Error", "Failed to prepare some settings")
                logger.error("Failed to prepare some settings")
                return False

            # 모든 탭의 설정 준비 완료 후, 한 번만 DB 저장
            logger.debug("Saving all settings to DB...")
            db_save_success = self.config_manager.save_config(save_ui=True)

            if db_save_success:
                self.settings_changed.emit()
                logger.info("All settings saved successfully to DB")
                return True
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save settings to database")
                logger.error("Failed to save settings to database")
                return False

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Error", f"Save failed:\n{str(e)}")
            return False

    def _has_any_changes(self) -> bool:
        """
        변경사항이 있는지 확인

        Returns:
            bool: 변경사항 존재 여부
        """
        has_changes = False

        if self.basic_tab:
            has_changes |= self.basic_tab.has_changes()
        if self.cameras_tab:
            has_changes |= self.cameras_tab.has_changes()
        if self.streaming_tab:
            has_changes |= self.streaming_tab.has_changes()
        if self.recording_tab:
            has_changes |= self.recording_tab.has_changes()
        if self.backup_tab:
            has_changes |= self.backup_tab.has_changes()
        if self.storage_tab:
            has_changes |= self.storage_tab.has_changes()
        if self.performance_tab:
            has_changes |= self.performance_tab.has_changes()
        if self.hotkey_tab:
            has_changes |= self.hotkey_tab.has_changes()
        if self.ptz_key_tab:
            has_changes |= self.ptz_key_tab.has_changes()
        if self.logging_tab:
            has_changes |= self.logging_tab.has_changes()

        return has_changes

    def _on_ok(self):
        """OK 버튼 클릭"""
        if self._save_all_settings():
            self.accept()

    def _on_cancel(self):
        """Cancel 버튼 클릭"""
        # 변경사항이 있는지 확인
        if self._has_any_changes():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                logger.debug("Settings changes discarded")
                self.reject()
        else:
            self.reject()

    def _on_apply(self):
        """Apply 버튼 클릭"""
        if self._save_all_settings():
            QMessageBox.information(self, "Success", "Settings applied successfully")
            logger.debug("Settings applied via Apply button")

    def add_tab(self, tab_widget, tab_name: str):
        """
        탭 추가

        Args:
            tab_widget: 탭 위젯 (BaseSettingsTab 상속)
            tab_name: 탭 이름
        """
        self.tab_widget.addTab(tab_widget, tab_name)
        logger.debug(f"Tab added: {tab_name}")
