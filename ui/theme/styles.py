"""
위젯별 스타일 템플릿

모든 PyQt5 위젯의 QSS 스타일을 중앙에서 관리합니다.
"""

from .colors import ColorPalette


class StyleTemplates:
    """위젯별 QSS 템플릿"""

    @staticmethod
    def _c(theme: str, key: str) -> str:
        """색상 단축키"""
        return ColorPalette.get_color(theme, key)

    @classmethod
    def get_button_style(cls, theme: str) -> str:
        """QPushButton 스타일"""
        c = cls._c
        return f"""
            QPushButton {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                padding: 5px 15px;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {c(theme, 'bg_hover')};
                border-color: {c(theme, 'accent')};
            }}
            QPushButton:pressed {{
                background-color: {c(theme, 'bg_pressed')};
            }}
            QPushButton:disabled {{
                color: {c(theme, 'text_disabled')};
                background-color: {c(theme, 'bg_tertiary')};
                border-color: {c(theme, 'border_light')};
            }}
            QPushButton:default {{
                background-color: {c(theme, 'accent')};
                border-color: {c(theme, 'accent')};
            }}
            QPushButton:default:hover {{
                background-color: {c(theme, 'accent_hover')};
            }}
        """

    @classmethod
    def get_lineedit_style(cls, theme: str) -> str:
        """QLineEdit 스타일"""
        c = cls._c
        return f"""
            QLineEdit {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                padding: 5px;
                selection-background-color: {c(theme, 'selection_bg')};
            }}
            QLineEdit:focus {{
                border-color: {c(theme, 'accent')};
            }}
            QLineEdit:disabled {{
                background-color: {c(theme, 'bg_tertiary')};
                color: {c(theme, 'text_disabled')};
            }}
        """

    @classmethod
    def get_combobox_style(cls, theme: str) -> str:
        """QComboBox 스타일"""
        c = cls._c
        return f"""
            QComboBox {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                padding: 5px;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {c(theme, 'accent')};
            }}
            QComboBox:focus {{
                border-color: {c(theme, 'accent')};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {c(theme, 'text_primary')};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
                outline: none;
            }}
        """

    @classmethod
    def get_spinbox_style(cls, theme: str) -> str:
        """QSpinBox, QDoubleSpinBox 스타일"""
        c = cls._c
        return f"""
            QSpinBox, QDoubleSpinBox {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                padding: 5px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {c(theme, 'accent')};
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                background-color: {c(theme, 'bg_tertiary')};
                border-left: 1px solid {c(theme, 'border')};
                width: 16px;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: {c(theme, 'bg_tertiary')};
                border-left: 1px solid {c(theme, 'border')};
                width: 16px;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {c(theme, 'bg_hover')};
            }}
        """

    @classmethod
    def get_dateedit_style(cls, theme: str) -> str:
        """QDateEdit 스타일 - QComboBox와 동일한 디자인"""
        c = cls._c
        return f"""
            QDateEdit {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                padding: 5px;
                min-height: 20px;
            }}
            QDateEdit:hover {{
                border-color: {c(theme, 'accent')};
            }}
            QDateEdit:focus {{
                border-color: {c(theme, 'accent')};
            }}
            QDateEdit::drop-down {{
                border: none;
                width: 20px;
            }}
            QDateEdit::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {c(theme, 'text_primary')};
                margin-right: 5px;
            }}
            QDateEdit QAbstractItemView {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
                outline: none;
            }}
            QCalendarWidget {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
            }}
            QCalendarWidget QToolButton {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: none;
                padding: 2px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {c(theme, 'bg_hover')};
                border-radius: 3px;
            }}
            QCalendarWidget QMenu {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
            }}
            QCalendarWidget QSpinBox {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                background-color: {c(theme, 'bg_window')};
                color: {c(theme, 'text_primary')};
                selection-background-color: {c(theme, 'selection_bg')};
            }}
            QCalendarWidget QAbstractItemView:disabled {{
                color: {c(theme, 'text_disabled')};
            }}
        """

    @classmethod
    def get_checkbox_style(cls, theme: str) -> str:
        """QCheckBox 스타일"""
        c = cls._c
        return f"""
            QCheckBox {{
                color: {c(theme, 'text_primary')};
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                background-color: {c(theme, 'bg_secondary')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c(theme, 'accent')};
                border-color: {c(theme, 'accent')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c(theme, 'accent_hover')};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {c(theme, 'bg_tertiary')};
                border-color: {c(theme, 'border_light')};
            }}
        """

    @classmethod
    def get_radiobutton_style(cls, theme: str) -> str:
        """QRadioButton 스타일"""
        c = cls._c
        return f"""
            QRadioButton {{
                color: {c(theme, 'text_primary')};
                spacing: 5px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {c(theme, 'border')};
                border-radius: 9px;
                background-color: {c(theme, 'bg_secondary')};
            }}
            QRadioButton::indicator:checked {{
                background-color: {c(theme, 'accent')};
                border-color: {c(theme, 'accent')};
            }}
            QRadioButton::indicator:hover {{
                border-color: {c(theme, 'accent_hover')};
            }}
        """

    @classmethod
    def get_groupbox_style(cls, theme: str) -> str:
        """QGroupBox 스타일"""
        c = cls._c
        return f"""
            QGroupBox {{
                border: 1px solid {c(theme, 'border')};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: {c(theme, 'text_primary')};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """

    @classmethod
    def get_label_style(cls, theme: str) -> str:
        """QLabel 스타일"""
        c = cls._c
        return f"""
            QLabel {{
                color: {c(theme, 'text_primary')};
                background-color: transparent;
            }}
        """

    @classmethod
    def get_tablewidget_style(cls, theme: str) -> str:
        """QTableWidget 스타일"""
        c = cls._c
        return f"""
            QTableWidget {{
                background-color: {c(theme, 'bg_window')};
                alternate-background-color: {c(theme, 'bg_alternate')};
                color: {c(theme, 'text_primary')};
                gridline-color: {c(theme, 'border_light')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
                selection-color: {c(theme, 'text_primary')};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:hover {{
                background-color: {c(theme, 'bg_hover')};
            }}
            QHeaderView::section {{
                background-color: {c(theme, 'bg_tertiary')};
                color: {c(theme, 'text_primary')};
                padding: 5px;
                border: none;
                border-bottom: 1px solid {c(theme, 'border')};
                border-right: 1px solid {c(theme, 'border_light')};
                font-weight: bold;
            }}
        """

    @classmethod
    def get_listwidget_style(cls, theme: str) -> str:
        """QListWidget 스타일"""
        c = cls._c
        return f"""
            QListWidget {{
                background-color: {c(theme, 'bg_window')};
                alternate-background-color: {c(theme, 'bg_alternate')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
                selection-color: {c(theme, 'text_primary')};
            }}
            QListWidget::item {{
                padding: 5px;
            }}
            QListWidget::item:hover {{
                background-color: {c(theme, 'bg_hover')};
            }}
        """

    @classmethod
    def get_scrollbar_style(cls, theme: str) -> str:
        """QScrollBar 스타일"""
        c = cls._c
        return f"""
            QScrollBar:vertical {{
                background-color: {c(theme, 'scrollbar_bg')};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c(theme, 'scrollbar_handle')};
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c(theme, 'scrollbar_hover')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}

            QScrollBar:horizontal {{
                background-color: {c(theme, 'scrollbar_bg')};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c(theme, 'scrollbar_handle')};
                min-width: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c(theme, 'scrollbar_hover')};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """

    @classmethod
    def get_slider_style(cls, theme: str) -> str:
        """QSlider 스타일"""
        c = cls._c
        return f"""
            QSlider::groove:horizontal {{
                border: 1px solid {c(theme, 'border')};
                height: 6px;
                background-color: {c(theme, 'bg_secondary')};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: {c(theme, 'accent')};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {c(theme, 'accent_hover')};
            }}
        """

    @classmethod
    def get_menu_style(cls, theme: str) -> str:
        """QMenu, QMenuBar 스타일"""
        c = cls._c
        return f"""
            QMenuBar {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
                border-bottom: 1px solid {c(theme, 'border')};
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 5px 10px;
            }}
            QMenuBar::item:selected {{
                background-color: {c(theme, 'accent')};
            }}
            QMenuBar::item:pressed {{
                background-color: {c(theme, 'accent_pressed')};
            }}

            QMenu {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
            }}
            QMenu::item {{
                padding: 5px 25px 5px 10px;
            }}
            QMenu::item:selected {{
                background-color: {c(theme, 'accent')};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c(theme, 'menu_separator')};
                margin: 5px 0px;
            }}
        """

    @classmethod
    def get_statusbar_style(cls, theme: str) -> str:
        """QStatusBar 스타일"""
        c = cls._c
        return f"""
            QStatusBar {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
                border-top: 1px solid {c(theme, 'border')};
            }}
            QStatusBar::item {{
                border: none;
            }}
        """

    @classmethod
    def get_dockwidget_style(cls, theme: str) -> str:
        """QDockWidget 스타일"""
        c = cls._c
        return f"""
            QDockWidget {{
                titlebar-close-icon: none;
                titlebar-normal-icon: none;
                color: {c(theme, 'text_primary')};
            }}
            QDockWidget::title {{
                background-color: {c(theme, 'dock_title')};
                padding: 5px;
                border: 1px solid {c(theme, 'border')};
            }}
            QDockWidget::close-button, QDockWidget::float-button {{
                background-color: transparent;
                border: none;
                padding: 2px;
            }}
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
                background-color: {c(theme, 'bg_hover')};
            }}
        """

    @classmethod
    def get_tabwidget_style(cls, theme: str) -> str:
        """QTabWidget 스타일"""
        c = cls._c
        return f"""
            QTabWidget::pane {{
                border: 1px solid {c(theme, 'border')};
                background-color: {c(theme, 'bg_primary')};
            }}
            QTabBar::tab {{
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
                padding: 8px 16px;
                border: 1px solid {c(theme, 'border')};
                border-bottom: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {c(theme, 'bg_primary')};
                border-bottom: 2px solid {c(theme, 'accent')};
            }}
            QTabBar::tab:hover {{
                background-color: {c(theme, 'bg_hover')};
            }}
        """

    @classmethod
    def get_mainwindow_style(cls, theme: str) -> str:
        """QMainWindow 스타일"""
        c = cls._c
        return f"""
            QMainWindow {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
            }}
            QWidget {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
            }}
        """

    @classmethod
    def get_dialog_style(cls, theme: str) -> str:
        """QDialog 스타일"""
        c = cls._c
        return f"""
            QDialog {{
                background-color: {c(theme, 'bg_primary')};
                color: {c(theme, 'text_primary')};
            }}
        """

    @classmethod
    def get_tooltip_style(cls, theme: str) -> str:
        """QToolTip 스타일"""
        c = cls._c
        return f"""
            QToolTip {{
                background-color: {c(theme, 'tooltip_bg')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                padding: 5px;
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_textedit_style(cls, theme: str) -> str:
        """QTextEdit 스타일"""
        c = cls._c
        return f"""
            QTextEdit {{
                background-color: {c(theme, 'bg_window')};
                color: {c(theme, 'text_primary')};
                border: 1px solid {c(theme, 'border')};
                selection-background-color: {c(theme, 'selection_bg')};
            }}
        """

    @classmethod
    def get_progressbar_style(cls, theme: str) -> str:
        """QProgressBar 스타일"""
        c = cls._c
        return f"""
            QProgressBar {{
                border: 1px solid {c(theme, 'border')};
                border-radius: 3px;
                text-align: center;
                background-color: {c(theme, 'bg_secondary')};
                color: {c(theme, 'text_primary')};
            }}
            QProgressBar::chunk {{
                background-color: {c(theme, 'accent')};
                border-radius: 2px;
            }}
        """

    @classmethod
    def get_splitter_style(cls, theme: str) -> str:
        """QSplitter 스타일"""
        c = cls._c
        return f"""
            QSplitter::handle {{
                background-color: {c(theme, 'dock_separator')};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {c(theme, 'accent')};
            }}
        """

    @classmethod
    def get_status_label_style(cls, theme: str, status: str) -> str:
        """
        상태 라벨 스타일

        Args:
            theme: 테마
            status: 상태 ('success', 'warning', 'error', 'info')
        """
        c = cls._c
        color_map = {
            'success': c(theme, 'success'),
            'warning': c(theme, 'warning'),
            'error': c(theme, 'error'),
            'info': c(theme, 'text_info'),
        }
        color = color_map.get(status, c(theme, 'text_primary'))
        return f"color: {color}; font-weight: bold;"

    @classmethod
    def get_info_label_style(cls, theme: str) -> str:
        """정보 라벨 스타일 (배경 있는 박스형)"""
        c = cls._c
        return f"""
            padding: 10px;
            background-color: {c(theme, 'bg_secondary')};
            border: 1px solid {c(theme, 'border')};
            border-radius: 5px;
            color: {c(theme, 'text_primary')};
        """
