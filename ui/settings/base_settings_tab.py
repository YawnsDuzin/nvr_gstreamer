"""
Base class for all settings tabs
설정 탭의 추상 베이스 클래스
"""

from abc import ABCMeta, abstractmethod
from PyQt5.QtWidgets import QWidget
from loguru import logger

from core.config import ConfigManager


# QWidget와 ABC를 동시에 상속하기 위한 메타클래스
class CombinedMeta(type(QWidget), ABCMeta):
    """PyQt5와 ABC를 결합한 메타클래스"""
    pass


class BaseSettingsTab(QWidget, metaclass=CombinedMeta):
    """
    설정 탭의 베이스 클래스
    모든 설정 탭은 이 클래스를 상속받아 구현
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        초기화

        Args:
            config_manager: ConfigManager 인스턴스
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self._original_data = {}  # 원본 데이터 (변경 감지용)

    @abstractmethod
    def load_settings(self):
        """
        설정 로드
        서브클래스에서 반드시 구현해야 함
        """
        pass

    @abstractmethod
    def save_settings(self) -> bool:
        """
        설정 저장
        서브클래스에서 반드시 구현해야 함

        Returns:
            bool: 저장 성공 여부
        """
        pass

    @abstractmethod
    def validate_settings(self) -> tuple[bool, str]:
        """
        설정 검증
        서브클래스에서 반드시 구현해야 함

        Returns:
            tuple[bool, str]: (검증 성공 여부, 에러 메시지)
        """
        pass

    def has_changes(self) -> bool:
        """
        변경 사항이 있는지 확인
        서브클래스에서 오버라이드 가능

        Returns:
            bool: 변경 사항 존재 여부
        """
        # 기본 구현: 항상 False
        # 서브클래스에서 필요시 오버라이드
        return False

    def _store_original_data(self, data: dict):
        """
        원본 데이터 저장 (변경 감지용)

        Args:
            data: 원본 데이터 딕셔너리
        """
        self._original_data = data.copy()

    def _get_original_data(self) -> dict:
        """
        원본 데이터 반환

        Returns:
            dict: 원본 데이터
        """
        return self._original_data.copy()

    def reset_to_original(self):
        """
        원본 데이터로 되돌리기
        서브클래스에서 오버라이드 가능
        """
        if self._original_data:
            self.load_settings()
            logger.debug(f"{self.__class__.__name__}: Reset to original settings")

    def apply_theme(self, theme: str = "dark"):
        """
        테마 적용

        Args:
            theme: 테마 이름 ("dark" 또는 "light")
        """
        if theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #2a2a2a;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #4a4a4a;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                    background-color: #3a3a3a;
                    border: 1px solid #4a4a4a;
                    border-radius: 3px;
                    padding: 5px;
                    color: #ffffff;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                    border: 1px solid #5a9fd4;
                }
                QCheckBox {
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #4a4a4a;
                    border-radius: 3px;
                    background-color: #3a3a3a;
                }
                QCheckBox::indicator:checked {
                    background-color: #5a9fd4;
                    border-color: #5a9fd4;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #4a4a4a;
                    border-radius: 3px;
                    padding: 5px 15px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                    border-color: #5a9fd4;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QListWidget, QTreeWidget {
                    background-color: #3a3a3a;
                    border: 1px solid #4a4a4a;
                    border-radius: 3px;
                    color: #ffffff;
                }
                QListWidget::item:selected, QTreeWidget::item:selected {
                    background-color: #5a9fd4;
                }
                QScrollBar:vertical {
                    background-color: #2a2a2a;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #4a4a4a;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #5a5a5a;
                }
            """)
        else:
            # Light theme
            self.setStyleSheet("")
