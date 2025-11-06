"""
테마 관리자 (싱글톤)

애플리케이션 전체의 테마를 중앙에서 관리합니다.
"""

from PyQt5.QtCore import QObject, pyqtSignal
from .colors import ColorPalette
from .styles import StyleTemplates


class ThemeManager(QObject):
    """
    테마 관리자 싱글톤

    애플리케이션 전체의 테마를 관리하고,
    테마 변경 시 모든 위젯에 알립니다.
    """

    _instance = None
    theme_changed = pyqtSignal(str)  # 테마 변경 시그널 (theme_name)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._current_theme = 'dark'
        self._initialized = True

    @property
    def current_theme(self) -> str:
        """현재 테마 ('dark' 또는 'light')"""
        return self._current_theme

    def set_theme(self, theme: str, force_update: bool = False):
        """
        테마 변경

        Args:
            theme: 'dark' 또는 'light'
            force_update: True면 테마가 같아도 시그널 emit (초기화용)
        """
        if theme not in ['dark', 'light']:
            theme = 'dark'

        if self._current_theme != theme or force_update:
            self._current_theme = theme
            self.theme_changed.emit(theme)

    def get_color(self, key: str) -> str:
        """
        현재 테마의 색상 가져오기

        Args:
            key: 색상 키 (예: 'bg_primary', 'accent')

        Returns:
            HEX 색상 코드
        """
        return ColorPalette.get_color(self._current_theme, key)

    def get_palette(self) -> dict:
        """
        현재 테마의 전체 팔레트 가져오기

        Returns:
            색상 딕셔너리
        """
        return ColorPalette.get_palette(self._current_theme)

    def get_application_stylesheet(self) -> str:
        """
        전체 애플리케이션 스타일시트 생성

        Returns:
            모든 위젯 스타일을 포함한 QSS 문자열
        """
        theme = self._current_theme
        styles = StyleTemplates

        # 모든 위젯 스타일 조합
        stylesheet = f"""
            /* === 메인 윈도우 === */
            {styles.get_mainwindow_style(theme)}

            /* === 기본 위젯 === */
            {styles.get_label_style(theme)}
            {styles.get_button_style(theme)}
            {styles.get_lineedit_style(theme)}
            {styles.get_combobox_style(theme)}
            {styles.get_dateedit_style(theme)}
            {styles.get_spinbox_style(theme)}
            {styles.get_checkbox_style(theme)}
            {styles.get_radiobutton_style(theme)}
            {styles.get_groupbox_style(theme)}

            /* === 리스트 및 테이블 === */
            {styles.get_tablewidget_style(theme)}
            {styles.get_listwidget_style(theme)}
            {styles.get_textedit_style(theme)}

            /* === 스크롤바 및 슬라이더 === */
            {styles.get_scrollbar_style(theme)}
            {styles.get_slider_style(theme)}

            /* === 메뉴 및 상태바 === */
            {styles.get_menu_style(theme)}
            {styles.get_statusbar_style(theme)}

            /* === 도크 및 탭 === */
            {styles.get_dockwidget_style(theme)}
            {styles.get_tabwidget_style(theme)}
            {styles.get_splitter_style(theme)}

            /* === 다이얼로그 === */
            {styles.get_dialog_style(theme)}
            {styles.get_tooltip_style(theme)}
            {styles.get_progressbar_style(theme)}
        """

        return stylesheet

    def get_widget_style(self, widget_type: str) -> str:
        """
        특정 위젯 타입의 스타일만 가져오기

        Args:
            widget_type: 위젯 타입 (예: 'button', 'lineedit')

        Returns:
            해당 위젯의 QSS 스타일
        """
        theme = self._current_theme
        method_name = f'get_{widget_type}_style'
        method = getattr(StyleTemplates, method_name, None)

        if method:
            return method(theme)
        return ""

    def get_status_style(self, status: str) -> str:
        """
        상태 라벨 스타일 가져오기

        Args:
            status: 상태 ('success', 'warning', 'error', 'info')

        Returns:
            상태 라벨 스타일
        """
        return StyleTemplates.get_status_label_style(self._current_theme, status)

    def get_info_box_style(self) -> str:
        """
        정보 박스 스타일 가져오기

        Returns:
            정보 박스 스타일 (배경 있는 라벨)
        """
        return StyleTemplates.get_info_label_style(self._current_theme)