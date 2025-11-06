"""
테마 시스템

애플리케이션 전체의 테마를 중앙에서 관리하는 시스템입니다.

사용 예:
    from ui.theme import ThemeManager, ThemedDialog

    # 테마 관리자 사용
    theme_manager = ThemeManager()
    theme_manager.set_theme('dark')

    # 테마 인식 다이얼로그
    class MyDialog(ThemedDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._setup_ui()
            self.apply_initial_theme()  # UI 구성 후 테마 적용
"""

from .theme_manager import ThemeManager
from .colors import ColorPalette
from .styles import StyleTemplates
from .base import ThemedWidget, ThemedDialog

__all__ = [
    'ThemeManager',
    'ColorPalette',
    'StyleTemplates',
    'ThemedWidget',
    'ThemedDialog',
]
