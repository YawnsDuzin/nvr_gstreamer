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

    def _get_all_tabs(self) -> list:
        """모든 탭 리스트 반환"""
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
        return tabs

    def _save_all_settings(self) -> bool:
        """
        변경된 설정만 선택적으로 저장

        Returns:
            bool: 저장 성공 여부
        """
        try:
            tabs = self._get_all_tabs()

            # 변경된 탭 찾기
            changed_tabs = []
            for tab_name, tab in tabs:
                if tab.has_changes():
                    changed_tabs.append((tab_name, tab))
                    logger.debug(f"{tab_name} tab has changes")

            if not changed_tabs:
                logger.info("No changes to save")
                return True

            logger.info(f"Saving changes in {len(changed_tabs)} tabs: {[name for name, _ in changed_tabs]}")

            # 변경된 탭만 검증
            for tab_name, tab in changed_tabs:
                valid, error_msg = tab.validate_settings()
                if not valid:
                    QMessageBox.warning(self, "Validation Error", f"{tab_name} Tab: {error_msg}")
                    logger.warning(f"{tab_name} validation failed: {error_msg}")
                    return False

            # 변경된 탭만 메모리에 저장 및 DB에 저장
            saved_count = 0
            failed_tabs = []

            for tab_name, tab in changed_tabs:
                try:
                    # save_to_db()는 내부적으로 save_settings()를 호출하고 DB에 저장
                    if tab.save_to_db():
                        saved_count += 1
                        logger.success(f"✓ {tab_name} settings saved to DB")
                    else:
                        failed_tabs.append(tab_name)
                        logger.error(f"✗ {tab_name} settings failed to save")
                except Exception as e:
                    failed_tabs.append(tab_name)
                    logger.error(f"✗ {tab_name} settings error: {e}")

            if failed_tabs:
                QMessageBox.warning(
                    self, "Save Error",
                    f"Failed to save settings for: {', '.join(failed_tabs)}"
                )
                return False

            # 모든 변경사항이 성공적으로 저장됨
            self.settings_changed.emit()
            logger.info(f"Successfully saved {saved_count} changed tab(s)")

            # Apply 후 변경사항 플래그 리셋
            for _, tab in changed_tabs:
                tab.mark_as_saved()

            return True

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
