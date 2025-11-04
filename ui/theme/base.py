"""
테마 인식 베이스 클래스

모든 위젯과 다이얼로그가 테마 변경에 자동으로 반응하도록 합니다.
"""

from PyQt5.QtWidgets import QWidget, QDialog
from .theme_manager import ThemeManager


class ThemedWidget(QWidget):
    """
    테마 인식 위젯 베이스 클래스

    이 클래스를 상속받은 위젯은 테마 변경 시 자동으로 스타일이 업데이트됩니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        # 초기 테마 적용은 서브클래스의 UI 구성 후에 호출해야 함

    def _apply_theme(self):
        """
        테마 적용 (서브클래스에서 오버라이드)

        서브클래스에서 이 메서드를 오버라이드하여
        위젯별 특별한 스타일을 적용합니다.

        Note: 대부분의 경우 QApplication 레벨의 스타일시트가 자동으로 적용되므로
        별도의 작업이 필요하지 않습니다.
        """
        # 기본 구현: 아무 작업도 하지 않음
        # (QApplication 레벨에서 이미 스타일시트가 적용됨)
        pass

    def _on_theme_changed(self, theme: str):
        """
        테마 변경 시그널 핸들러

        Args:
            theme: 변경된 테마 이름
        """
        self._apply_theme()

    def apply_initial_theme(self):
        """
        초기 테마 적용

        UI 구성이 완료된 후 호출합니다.
        """
        self._apply_theme()


class ThemedDialog(QDialog):
    """
    테마 인식 다이얼로그 베이스 클래스

    이 클래스를 상속받은 다이얼로그는 테마 변경 시 자동으로 스타일이 업데이트됩니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        # 초기 테마 적용은 서브클래스의 UI 구성 후에 호출해야 함

    def _apply_theme(self):
        """
        테마 적용 (서브클래스에서 오버라이드)

        서브클래스에서 이 메서드를 오버라이드하여
        위젯별 특별한 스타일을 적용합니다.

        Note: 대부분의 경우 QApplication 레벨의 스타일시트가 자동으로 적용되므로
        별도의 작업이 필요하지 않습니다.
        """
        # 기본 구현: 아무 작업도 하지 않음
        # (QApplication 레벨에서 이미 스타일시트가 적용됨)
        pass

    def _on_theme_changed(self, theme: str):
        """
        테마 변경 시그널 핸들러

        Args:
            theme: 변경된 테마 이름
        """
        self._apply_theme()

    def apply_initial_theme(self):
        """
        초기 테마 적용

        UI 구성이 완료된 후 호출합니다.
        """
        self._apply_theme()
