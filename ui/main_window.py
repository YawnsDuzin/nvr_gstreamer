"""
Enhanced Main Window with 4-channel grid view
Integrates camera list, grid view, and configuration management
"""

import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QAction,
    QMessageBox, QDockWidget, QLabel
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QDateTime
from PyQt5.QtGui import QKeySequence, QCloseEvent
from loguru import logger

# Fix imports with full paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.grid_view import GridViewWidget
from ui.camera_list_widget import CameraListWidget
from ui.camera_dialog import CameraDialog
from ui.recording_control_widget import RecordingControlWidget
from ui.playback_widget import PlaybackWidget
from config.config_manager import ConfigManager
from streaming.camera_stream import CameraStream
from recording.recording_manager import RecordingManager
from playback.playback_manager import PlaybackManager
from utils.system_monitor import SystemMonitorThread


class MainWindow(QMainWindow):
    """Main application window with camera grid view"""

    def __init__(self):
        super().__init__()
        # Get singleton instance
        self.config_manager = ConfigManager.get_instance()
        self.recording_manager = RecordingManager()
        self.playback_manager = PlaybackManager()
        self.grid_view = None
        self.camera_list = None
        self.recording_control = None
        self.playback_widget = None
        self.is_playback_mode = False

        # Get app name and version from config
        self.app_name = self.config_manager.app_config.app_name
        self.app_version = self.config_manager.app_config.version
        self.app_display_name = f"{self.app_name}/{self.app_version}"

        self.monitor_thread = None

        self._setup_ui()
        self._setup_menus()
        self._setup_status_bar()
        self._load_dock_state()  # Dock 상태를 먼저 로드
        self._setup_connections()  # 그 다음 시그널 연결

        # fullscreen_on_start 설정 적용 (모든 UI 설정 완료 후)
        if self.config_manager.ui_config.fullscreen_on_start:
            self.showFullScreen()
            logger.info("Window shown in fullscreen mode")

        logger.info("Enhanced main window initialized")

    def _setup_ui(self):
        """Setup main UI with splitter layout"""
        self.setWindowTitle(f"{self.app_display_name} - Network Video Recorder (Single Camera)")

        # UI 설정에서 window_state 및 fullscreen_on_start 가져오기
        ui_config = self.config_manager.ui_config
        ws = ui_config.window_state

        if ui_config.fullscreen_on_start:
            # 전체화면으로 시작
            logger.info("Starting in fullscreen mode (fullscreen_on_start=true)")
            # 먼저 기본 geometry 설정 (전체화면 전에 필요)
            self.setGeometry(100, 100, 1024, 768)
        else:
            # window_state 설정값 적용
            self.setGeometry(ws.get('x', 100), ws.get('y', 100),
                            ws.get('width', 1200), ws.get('height', 700))
            logger.info(f"Starting with window state: x={ws.get('x', 100)}, y={ws.get('y', 100)}, w={ws.get('width', 1200)}, h={ws.get('height', 700)}")

        # Central widget with splitter
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Camera list (as dock widget)
        self.camera_dock = QDockWidget("Cameras", self)
        self.camera_dock.setObjectName("camera_dock")  # 객체 이름 설정 (저장/복원에 필요)
        self.camera_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.camera_list = CameraListWidget(self.config_manager)
        self.camera_list.main_window = self  # Set reference to main window for grid_view access
        self.camera_dock.setWidget(self.camera_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.camera_dock)

        # Right panel - Recording control (as dock widget)
        self.recording_dock = QDockWidget("Recording Control", self)
        self.recording_dock.setObjectName("recording_dock")  # 객체 이름 설정
        self.recording_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.recording_control = RecordingControlWidget(self.recording_manager)
        self.recording_dock.setWidget(self.recording_control)
        self.addDockWidget(Qt.RightDockWidgetArea, self.recording_dock)

        # Bottom panel - Playback widget (as dock widget)
        self.playback_dock = QDockWidget("Playback", self)
        self.playback_dock.setObjectName("playback_dock")  # 객체 이름 설정
        self.playback_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.playback_widget = PlaybackWidget()
        self.playback_dock.setWidget(self.playback_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.playback_dock)

        # Main area - Grid view
        self.grid_view = GridViewWidget()
        splitter.addWidget(self.grid_view)

        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Apply theme from config
        self._apply_theme()

        # Load default layout from streaming config
        rows, cols = self.config_manager.get_default_layout()
        self.grid_view.set_layout(rows, cols)
        logger.info(f"Set initial grid layout to {rows}x{cols} from config")

    def _apply_theme(self):
        """Apply theme based on UI configuration"""
        ui_config = self.config_manager.ui_config

        if ui_config.theme == "light":
            self._apply_light_theme()
        else:  # default to dark
            self._apply_dark_theme()

        logger.info(f"Applied theme: {ui_config.theme}")

    def _apply_dark_theme(self):
        """Apply modern dark theme to application"""
        dark_style = """
        /* Main Window */
        QMainWindow {
            background-color: #1e1e1e;
        }

        /* Menu Bar */
        QMenuBar {
            background-color: #252526;
            color: #cccccc;
            border-bottom: 1px solid #3c3c3c;
            padding: 4px;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 6px 12px;
            margin: 2px 0px;
            border-radius: 4px;
        }
        QMenuBar::item:selected {
            background-color: #37373d;
            color: #ffffff;
        }
        QMenuBar::item:pressed {
            background-color: #094771;
            color: #ffffff;
        }

        /* Menu */
        QMenu {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #454545;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 24px 8px 12px;
            margin: 2px 4px;
            border-radius: 3px;
        }
        QMenu::item:selected {
            background-color: #094771;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #3c3c3c;
            margin: 4px 8px;
        }

        /* Status Bar */
        QStatusBar {
            background-color: #007acc;
            color: #ffffff;
            border-top: 1px solid #005a9e;
            font-size: 12px;
        }
        QStatusBar QLabel {
            color: #ffffff;
            padding: 0px 8px;
        }

        /* Dock Widget */
        QDockWidget {
            background-color: #252526;
            color: #cccccc;
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(float.png);
        }
        QDockWidget::title {
            background-color: #2d2d30;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #3c3c3c;
            font-size: 13px;
            font-weight: 600;
            color: #cccccc;
        }
        QDockWidget::close-button,
        QDockWidget::float-button {
            background-color: transparent;
            border: none;
            padding: 3px;
            icon-size: 12px;
        }
        QDockWidget::close-button:hover,
        QDockWidget::float-button:hover {
            background-color: #3c3c3c;
            border-radius: 3px;
        }

        /* Splitter */
        QSplitter::handle {
            background-color: #3c3c3c;
        }
        QSplitter::handle:hover {
            background-color: #007acc;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }

        /* Scroll Bar */
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #424242;
            min-height: 30px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #4e4e4e;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background-color: #1e1e1e;
            height: 12px;
            border: none;
        }
        QScrollBar::handle:horizontal {
            background-color: #424242;
            min-width: 30px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #4e4e4e;
        }
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* List Widget (Camera List, Playback List) */
        QListWidget {
            background-color: #1a1a1a;
            color: #ffffff;
            border: none;
            outline: none;
        }
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #2a2a2a;
        }
        QListWidget::item:selected {
            background-color: #3a3a3a;
        }
        QListWidget::item:hover {
            background-color: #2a2a2a;
        }

        /* Push Button */
        QPushButton {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666;
        }

        /* Labels */
        QLabel {
            color: #cccccc;
        }

        /* Group Box */
        QGroupBox {
            background-color: #252526;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            color: #cccccc;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #cccccc;
        }

        /* Combo Box */
        QComboBox {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 3px;
            padding: 5px;
        }
        QComboBox:hover {
            border-color: #007acc;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 5px;
        }
        QComboBox QAbstractItemView {
            background-color: #2a2a2a;
            color: #ffffff;
            selection-background-color: #094771;
            selection-color: #ffffff;
            border: 1px solid #4a4a4a;
        }

        /* Line Edit */
        QLineEdit {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 3px;
            padding: 5px;
        }
        QLineEdit:focus {
            border-color: #007acc;
        }

        /* Date Edit */
        QDateEdit {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 3px;
            padding: 5px;
        }
        QDateEdit:hover {
            border-color: #007acc;
        }
        QDateEdit::drop-down {
            border: none;
            padding-right: 5px;
        }

        /* Spin Box */
        QSpinBox, QDoubleSpinBox {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 3px;
            padding: 5px;
        }
        QSpinBox:hover, QDoubleSpinBox:hover {
            border-color: #007acc;
        }

        /* Check Box */
        QCheckBox {
            color: #cccccc;
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #4a4a4a;
            border-radius: 3px;
            background-color: #3a3a3a;
        }
        QCheckBox::indicator:hover {
            border-color: #007acc;
        }
        QCheckBox::indicator:checked {
            background-color: #007acc;
            border-color: #007acc;
        }

        /* Slider */
        QSlider::groove:horizontal {
            height: 6px;
            background: #3c3c3c;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #007acc;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:hover {
            background: #1c97ea;
        }

        /* Table Widget */
        QTableWidget {
            background-color: #1e1e1e;
            alternate-background-color: #252526;
            color: #cccccc;
            gridline-color: #3c3c3c;
            border: 1px solid #3c3c3c;
        }
        QTableWidget::item {
            padding: 4px;
        }
        QTableWidget::item:selected {
            background-color: #094771;
            color: #ffffff;
        }
        QTableWidget::item:hover {
            background-color: #2d2d30;
        }
        QHeaderView::section {
            background-color: #2d2d30;
            color: #cccccc;
            padding: 5px;
            border: 1px solid #3c3c3c;
            font-weight: bold;
        }

        /* Tool Tip */
        QToolTip {
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            padding: 3px;
        }

        /* Widget (Generic panels) */
        QWidget {
            background-color: #252526;
            color: #cccccc;
        }

        /* Video Display Widget */
        QWidget#videoWidget {
            background-color: #000000;
            border: 1px solid #3c3c3c;
        }
        """
        self.setStyleSheet(dark_style)

    def _apply_light_theme(self):
        """Apply modern light theme to application"""
        light_style = """
        /* Main Window */
        QMainWindow {
            background-color: #f3f3f3;
        }

        /* Menu Bar */
        QMenuBar {
            background-color: #ffffff;
            color: #1e1e1e;
            border-bottom: 1px solid #e0e0e0;
            padding: 4px;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 6px 12px;
            margin: 2px 0px;
            border-radius: 4px;
        }
        QMenuBar::item:selected {
            background-color: #e5e5e5;
            color: #000000;
        }
        QMenuBar::item:pressed {
            background-color: #0078d4;
            color: #ffffff;
        }

        /* Menu */
        QMenu {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 24px 8px 12px;
            margin: 2px 4px;
            border-radius: 3px;
        }
        QMenu::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #e0e0e0;
            margin: 4px 8px;
        }

        /* Status Bar */
        QStatusBar {
            background-color: #0078d4;
            color: #ffffff;
            border-top: 1px solid #005a9e;
            font-size: 12px;
        }
        QStatusBar QLabel {
            color: #ffffff;
            padding: 0px 8px;
        }

        /* Dock Widget */
        QDockWidget {
            background-color: #ffffff;
            color: #1e1e1e;
        }
        QDockWidget::title {
            background-color: #f5f5f5;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
            font-size: 13px;
            font-weight: 600;
            color: #1e1e1e;
        }
        QDockWidget::close-button,
        QDockWidget::float-button {
            background-color: transparent;
            border: none;
            padding: 3px;
            icon-size: 12px;
        }
        QDockWidget::close-button:hover,
        QDockWidget::float-button:hover {
            background-color: #e0e0e0;
            border-radius: 3px;
        }

        /* Splitter */
        QSplitter::handle {
            background-color: #e0e0e0;
        }
        QSplitter::handle:hover {
            background-color: #0078d4;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }

        /* Scroll Bar */
        QScrollBar:vertical {
            background-color: #f3f3f3;
            width: 12px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #cdcdcd;
            min-height: 30px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #a6a6a6;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background-color: #f3f3f3;
            height: 12px;
            border: none;
        }
        QScrollBar::handle:horizontal {
            background-color: #cdcdcd;
            min-width: 30px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #a6a6a6;
        }
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* List Widget (Camera List, Playback List) */
        QListWidget {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #e0e0e0;
            outline: none;
        }
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #f0f0f0;
        }
        QListWidget::item:selected {
            background-color: #e5e5e5;
            color: #000000;
        }
        QListWidget::item:hover {
            background-color: #f5f5f5;
        }

        /* Push Button */
        QPushButton {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
            border-color: #999999;
        }
        QPushButton:pressed {
            background-color: #0078d4;
            color: #ffffff;
            border-color: #0078d4;
        }
        QPushButton:disabled {
            background-color: #f3f3f3;
            color: #a0a0a0;
            border-color: #e0e0e0;
        }

        /* Labels */
        QLabel {
            color: #1e1e1e;
        }

        /* Group Box */
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            color: #1e1e1e;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #1e1e1e;
        }

        /* Combo Box */
        QComboBox {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }
        QComboBox:hover {
            border-color: #999999;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 5px;
        }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #1e1e1e;
            selection-background-color: #0078d4;
            selection-color: #ffffff;
            border: 1px solid #cccccc;
        }

        /* Line Edit */
        QLineEdit {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }

        /* Date Edit */
        QDateEdit {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }
        QDateEdit:hover {
            border-color: #999999;
        }
        QDateEdit::drop-down {
            border: none;
            padding-right: 5px;
        }

        /* Spin Box */
        QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }
        QSpinBox:hover, QDoubleSpinBox:hover {
            border-color: #999999;
        }

        /* Check Box */
        QCheckBox {
            color: #1e1e1e;
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #cccccc;
            border-radius: 3px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:hover {
            border-color: #999999;
        }
        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border-color: #0078d4;
        }

        /* Slider */
        QSlider::groove:horizontal {
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #0078d4;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:hover {
            background: #005a9e;
        }

        /* Table Widget */
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f9f9f9;
            color: #1e1e1e;
            gridline-color: #e0e0e0;
            border: 1px solid #e0e0e0;
        }
        QTableWidget::item {
            padding: 4px;
        }
        QTableWidget::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        QTableWidget::item:hover {
            background-color: #e8e8e8;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            color: #1e1e1e;
            padding: 5px;
            border: 1px solid #e0e0e0;
            font-weight: bold;
        }

        /* Tool Tip */
        QToolTip {
            background-color: #ffffff;
            color: #1e1e1e;
            border: 1px solid #cccccc;
            padding: 3px;
        }

        /* Widget (Generic panels) */
        QWidget {
            background-color: #ffffff;
            color: #1e1e1e;
        }

        /* Video Display Widget */
        QWidget#videoWidget {
            background-color: #000000;
            border: 1px solid #cccccc;
        }
        """
        self.setStyleSheet(light_style)

    def _setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        add_camera_action = QAction("Add Camera", self)
        add_camera_action.setShortcut(QKeySequence("Ctrl+N"))
        add_camera_action.triggered.connect(self._add_camera)
        file_menu.addAction(add_camera_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        # Single camera - no layout submenu needed
        # Just keep 1x1 layout option for consistency
        single_view = QAction("Single View", self)
        single_view.setShortcut(QKeySequence("Alt+1"))
        single_view.setEnabled(False)  # Already in single view
        view_menu.addAction(single_view)

        view_menu.addSeparator()

        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        # Dock visibility
        self.camera_dock_action = QAction("Show Camera List", self)
        self.camera_dock_action.setCheckable(True)
        self.camera_dock_action.triggered.connect(self._toggle_camera_dock)
        view_menu.addAction(self.camera_dock_action)

        self.recording_dock_action = QAction("Show Recording Control", self)
        self.recording_dock_action.setCheckable(True)
        self.recording_dock_action.triggered.connect(self._toggle_recording_dock)
        view_menu.addAction(self.recording_dock_action)

        self.playback_dock_action = QAction("Show Playback", self)
        self.playback_dock_action.setCheckable(True)
        self.playback_dock_action.triggered.connect(self._toggle_playback_dock)
        view_menu.addAction(self.playback_dock_action)

        # Camera menu
        camera_menu = menubar.addMenu("Camera")

        connect_all_action = QAction("Connect All", self)
        connect_all_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        connect_all_action.triggered.connect(self._connect_all_cameras)
        camera_menu.addAction(connect_all_action)

        disconnect_all_action = QAction("Disconnect All", self)
        disconnect_all_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        disconnect_all_action.triggered.connect(self._disconnect_all_cameras)
        camera_menu.addAction(disconnect_all_action)

        camera_menu.addSeparator()

        sequence_action = QAction("Start Sequence", self)
        sequence_action.setShortcut(QKeySequence("Ctrl+S"))
        sequence_action.triggered.connect(self.grid_view.toggle_sequence)
        camera_menu.addAction(sequence_action)

        # Setting menu
        setting_menu = menubar.addMenu("Setting")

        basic_setting_action = QAction("Basic Setting", self)
        basic_setting_action.triggered.connect(self._show_basic_setting)
        setting_menu.addAction(basic_setting_action)

        hotkey_setting_action = QAction("HotKey Setting", self)
        hotkey_setting_action.triggered.connect(self._show_hotkey_setting)
        setting_menu.addAction(hotkey_setting_action)

        ptzkey_setting_action = QAction("PTZKey Setting", self)
        ptzkey_setting_action.triggered.connect(self._show_ptzkey_setting)
        setting_menu.addAction(ptzkey_setting_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_connections(self):
        """Setup signal connections between components"""
        # Camera list signals
        self.camera_list.camera_selected.connect(self._on_camera_selected)
        self.camera_list.camera_added.connect(self._on_camera_added)
        self.camera_list.camera_removed.connect(self._on_camera_removed)
        self.camera_list.camera_connected.connect(self._on_camera_connected)
        self.camera_list.camera_disconnected.connect(self._on_camera_disconnected)

        # Grid view signals
        self.grid_view.channel_double_clicked.connect(self._on_channel_double_clicked)
        self.grid_view.layout_changed.connect(self._on_layout_changed)

        # Recording control signals
        self.recording_control.recording_started.connect(self._on_recording_started)
        self.recording_control.recording_stopped.connect(self._on_recording_stopped)

        # F5 키 단축키 설정 (Refresh Recordings)
        refresh_shortcut = QAction(self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self._refresh_recordings)
        self.addAction(refresh_shortcut)

        # Dock visibility 시그널 연결 (Dock이 닫힐 때 메뉴 체크 상태 동기화)
        self.camera_dock.visibilityChanged.connect(self._on_camera_dock_visibility_changed)
        self.recording_dock.visibilityChanged.connect(self._on_recording_dock_visibility_changed)
        self.playback_dock.visibilityChanged.connect(self._on_playback_dock_visibility_changed)

        # Auto-assign cameras to channels first
        self._auto_assign_cameras()
        # Then assign window handles to camera streams
        self._assign_window_handles_to_streams()
        # Finally populate recording control
        self._populate_recording_control()

    def _setup_status_bar(self):
        """Setup status bar with system monitoring"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 타이머와 스레드 변수 초기화 (closeEvent에서 참조되므로 항상 필요)
        self.status_timer = None
        self.clock_timer = None
        self.monitor_thread = None

        # show_status_bar 설정에 따라 표시/숨김
        ui_config = self.config_manager.ui_config
        if not ui_config.show_status_bar:
            self.status_bar.hide()
            logger.info("Status bar hidden (show_status_bar=false)")
            return

        # 상태바 스타일 (메인 테마와 일관성 유지)
        # 메인 테마의 QStatusBar 스타일이 적용되므로 별도 스타일 불필요

        # Connection status
        self.connection_label = QLabel("No cameras connected")
        self.status_bar.addWidget(self.connection_label)

        # Separator
        # self.status_bar.addWidget(QLabel(" | "))

        # Layout info
        self.layout_label = QLabel("Layout: Single Camera")
        self.status_bar.addWidget(self.layout_label)

        # Separator
        # self.status_bar.addWidget(QLabel(" | "))

        # System monitoring labels
        self.cpu_label = QLabel("CPU: --%")
        self.memory_label = QLabel("Memory: --%")
        self.temp_label = QLabel("Temp: --°C")
        self.disk_label = QLabel("Disk: -- GB free")
        self.clock_label = QLabel("")

        self.status_bar.addWidget(self.cpu_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.memory_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.temp_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.disk_label)
        self.status_bar.addPermanentWidget(self.clock_label)

        # 초기 시계 설정
        self._update_clock()

        # 시스템 모니터링 스레드 시작
        self.monitor_thread = SystemMonitorThread(update_interval=5)
        self.monitor_thread.status_updated.connect(self._update_system_status)
        self.monitor_thread.start()

        # 시계 업데이트 타이머 (1초마다)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

        # Connection status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)

        logger.info("Status bar with system monitoring initialized")

    def _update_status(self):
        """Update camera connection status"""
        # Get connection stats from camera list
        connected = 0
        total = 0

        for camera_id, camera_item in self.camera_list.camera_items.items():
            total += 1
            if camera_item.camera_stream and camera_item.camera_stream.is_connected():
                connected += 1

        if connected > 0:
            self.connection_label.setText(f"{connected}/{total} cameras connected")
        else:
            self.connection_label.setText("No cameras connected")

    def _update_system_status(self, cpu: float, memory: float, temp: float, disk_free: float):
        """
        시스템 상태 업데이트 (모니터링 스레드에서 호출)

        Args:
            cpu: CPU 사용률 (%)
            memory: 메모리 사용률 (%)
            temp: 시스템 온도 (°C)
            disk_free: 남은 디스크 공간 (GB)
        """
        # CPU 경고 (80% 이상)
        if cpu >= 80:
            self.cpu_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.cpu_label.setStyleSheet("color: #ffffff;")
        self.cpu_label.setText(f"CPU: {cpu:.1f}%")

        # 메모리 경고 (85% 이상)
        if memory >= 85:
            self.memory_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.memory_label.setStyleSheet("color: #ffffff;")
        self.memory_label.setText(f"Memory: {memory:.1f}%")

        # 온도 표시
        if temp > 0:
            # 온도 경고 (70°C 이상)
            if temp >= 70:
                self.temp_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            else:
                self.temp_label.setStyleSheet("color: #ffffff;")
            self.temp_label.setText(f"Temp: {temp:.1f}°C")
        else:
            self.temp_label.setText("Temp: N/A")

        # 디스크 경고 (10GB 미만)
        if disk_free < 10:
            self.disk_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.disk_label.setStyleSheet("color: #ffffff;")
        self.disk_label.setText(f"Disk: {disk_free:.1f}GB free")

    def _update_clock(self):
        """시계 업데이트"""
        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.clock_label.setText(f"  {current_time}")

    def _auto_assign_cameras(self):
        """Auto-assign cameras from config to grid channels"""
        # 디버그 로그 추가
        logger.info(f"ConfigManager cameras list: {self.config_manager.cameras}")
        logger.info(f"ConfigManager cameras count: {len(self.config_manager.cameras)}")

        cameras = self.config_manager.get_enabled_cameras()
        logger.info(f"Enabled cameras count: {len(cameras)}")

        if cameras:
            for cam in cameras:
                logger.info(f"Camera found: {cam.camera_id} - {cam.name} - enabled: {cam.enabled}")

        # Single camera setup - only use first camera
        if cameras:
            camera = cameras[0]
            channel = self.grid_view.get_channel(0)
            if channel:
                channel.update_camera_info(camera.camera_id, camera.name)
                logger.debug(f"Assigned {camera.camera_id} to single channel")
        else:
            logger.warning("No enabled cameras found in configuration!")

    def _assign_window_handles_to_streams(self):
        """Assign window handles from grid channels to camera streams"""
        logger.info("Assigning window handles to camera streams...")

        # 디버깅을 위해 모든 채널과 카메라 정보 출력
        logger.debug(f"Total channels: {len(self.grid_view.channels)}")
        logger.debug(f"Total camera streams: {len(self.camera_list.camera_streams)}")

        # 먼저 모든 채널 정보 확인
        for i, channel in enumerate(self.grid_view.channels[:16]):
            logger.debug(f"Channel {i}: camera_id={channel.camera_id}, has_handle={channel.get_window_handle() is not None}")

        # 카메라 ID를 기준으로 매칭
        for camera_id, stream in self.camera_list.camera_streams.items():
            # 해당 카메라 ID를 가진 채널 찾기
            window_handle_assigned = False
            for i, channel in enumerate(self.grid_view.channels[:16]):
                if channel.camera_id == camera_id:
                    window_handle = channel.get_window_handle()
                    if window_handle:
                        stream.window_handle = window_handle
                        logger.success(f"✓ Assigned window handle to {camera_id} (channel {i}): {window_handle}")
                        window_handle_assigned = True
                    else:
                        logger.warning(f"✗ No window handle available for {camera_id} (channel {i})")
                    break

            if not window_handle_assigned:
                logger.warning(f"✗ Camera {camera_id} not assigned to any channel")

    def _update_window_handles_after_layout_change(self):
        """레이아웃 변경 후 윈도우 핸들 재할당 및 파이프라인 업데이트"""
        logger.info("Updating window handles after layout change...")

        # 먼저 카메라를 새 채널에 재할당
        cameras = self.config_manager.get_enabled_cameras()

        # 연결된 스트림 임시 저장
        connected_streams = {}
        for camera in cameras[:len(self.grid_view.channels)]:
            stream = self.camera_list.get_camera_stream(camera.camera_id)
            if stream and stream.is_connected():
                connected_streams[camera.camera_id] = stream
                logger.info(f"Temporarily storing connected stream: {camera.camera_id}")

        # 모든 스트림 정지 (레이아웃 변경 중)
        for camera_id, stream in connected_streams.items():
            if stream.pipeline_manager:
                logger.info(f"Stopping pipeline for layout change: {camera_id}")
                stream.disconnect()

        # UI 업데이트를 위해 QTimer 사용 (비동기 처리)
        from PyQt5.QtCore import QTimer

        def reconnect_streams():
            # 새 채널에 카메라 재할당 및 파이프라인 재시작
            for i, camera in enumerate(cameras[:len(self.grid_view.channels)]):
                channel = self.grid_view.get_channel(i)
                if channel:
                    # 채널에 카메라 정보 업데이트
                    channel.update_camera_info(camera.camera_id, camera.name)

                    # 이전에 연결되어 있던 스트림이면 재연결
                    if camera.camera_id in connected_streams:
                        stream = connected_streams[camera.camera_id]
                        # 새 윈도우 핸들 가져오기
                        new_window_handle = channel.get_window_handle()

                        if new_window_handle:
                            # 스트림에 윈도우 핸들 설정하고 재연결
                            stream.window_handle = new_window_handle
                            logger.info(f"Reconnecting camera {camera.camera_id} with new window handle")

                            # 파이프라인 재시작
                            if stream.connect():
                                channel.set_connected(True)
                                logger.success(f"✓ Reconnected {camera.camera_id} after layout change")
                            else:
                                logger.error(f"✗ Failed to reconnect {camera.camera_id} after layout change")
                        else:
                            logger.warning(f"No window handle available for {camera.camera_id}")

            logger.success("Layout change completed - streams reconnected")

        # 500ms 후에 재연결 시작 (파이프라인 정리 완료 대기)
        QTimer.singleShot(500, reconnect_streams)

    def _on_camera_selected(self, camera_id: str):
        """Handle camera selection from list"""
        logger.debug(f"Camera selected: {camera_id}")

    def _on_camera_added(self, camera_config):
        """Handle camera added"""
        logger.info(f"Camera added: {camera_config.name}")
        self._auto_assign_cameras()
        # Add to recording control
        if hasattr(camera_config, 'rtsp_url'):
            self.recording_control.add_camera(
                camera_config.camera_id,
                camera_config.name,
                camera_config.rtsp_url
            )

    def _on_camera_removed(self, camera_id: str):
        """Handle camera removed"""
        logger.info(f"Camera removed: {camera_id}")
        # Clear channel if assigned
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.update_camera_info("", "No Camera")
                channel.set_connected(False)
        # Remove from recording control
        self.recording_control.remove_camera(camera_id)

    def _on_camera_connected(self, camera_id: str):
        """Handle camera connected"""
        logger.info(f"Camera connected: {camera_id}")

        # Get camera stream
        stream = self.camera_list.get_camera_stream(camera_id)
        if not stream:
            logger.warning(f"No stream found for camera {camera_id}")
            return

        # Find channel with this camera and update
        channel_found = False
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel_found = True
                # Get window handle and set it on the pipeline
                window_handle = channel.get_window_handle()
                if window_handle and stream.pipeline_manager:
                    # Set video sink to render in widget
                    stream.pipeline_manager.set_window_handle(window_handle)
                    logger.info(f"Set window handle for camera {camera_id}: {window_handle}")
                else:
                    logger.warning(f"Could not set window handle for {camera_id} - handle: {window_handle}, pipeline: {stream.pipeline_manager}")

                channel.set_connected(True)
                break

        if not channel_found:
            logger.warning(f"No channel found for camera {camera_id}")

    def _on_camera_disconnected(self, camera_id: str):
        """Handle camera disconnected"""
        logger.info(f"Camera disconnected: {camera_id}")

        # Find channel with this camera and update
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_connected(False)
                break

    def _on_channel_double_clicked(self, channel_index: int):
        """Handle channel double-click"""
        logger.debug(f"Channel {channel_index} double-clicked")

    def _on_layout_changed(self, layout: tuple):
        """Handle layout change"""
        rows, cols = layout
        # Single camera - always show "Single Camera"
        self.layout_label.setText("Layout: Single Camera")
        logger.info(f"Single camera mode - layout fixed at 1x1")

        # 레이아웃 변경 시 윈도우 핸들 재할당 및 파이프라인 업데이트
        self._update_window_handles_after_layout_change()

    def _populate_recording_control(self):
        """Populate recording control with cameras"""
        cameras = self.config_manager.get_all_cameras()
        for camera in cameras:
            if hasattr(camera, 'rtsp_url'):
                self.recording_control.add_camera(
                    camera.camera_id,
                    camera.name,
                    camera.rtsp_url
                )
                logger.debug(f"Added camera to recording control: {camera.name}")

    def _on_recording_started(self, camera_id: str):
        """Handle recording started"""
        logger.info(f"Recording started for camera: {camera_id}")
        # Update channel indicator
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_recording(True)
                break

    def _on_recording_stopped(self, camera_id: str):
        """Handle recording stopped"""
        logger.info(f"Recording stopped for camera: {camera_id}")
        # Update channel indicator
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_recording(False)
                break

    def _add_camera(self):
        """Show add camera dialog"""
        self.camera_list._add_camera()

    def _show_basic_setting(self):
        """Show basic setting dialog"""
        QMessageBox.information(
            self,
            "Basic Setting",
            "Basic Setting 기능은 아직 준비되지 않았습니다."
        )

    def _show_hotkey_setting(self):
        """Show hotkey setting dialog"""
        QMessageBox.information(
            self,
            "HotKey Setting",
            "HotKey Setting 기능은 아직 준비되지 않았습니다."
        )

    def _show_ptzkey_setting(self):
        """Show PTZKey setting dialog"""
        QMessageBox.information(
            self,
            "PTZKey Setting",
            "PTZKey Setting 기능은 아직 준비되지 않았습니다."
        )

    def _connect_all_cameras(self):
        """Connect all cameras"""
        logger.info("Connecting all cameras...")

        # 윈도우 핸들이 이미 할당되어 있는지 확인하고, 없으면 재할당
        self._assign_window_handles_to_streams()

        # 그 다음 연결
        self.camera_list._connect_all()

    def _disconnect_all_cameras(self):
        """Disconnect all cameras"""
        self.camera_list._disconnect_all()

    def _toggle_camera_dock(self, checked: bool):
        """Toggle camera dock visibility"""
        self.camera_dock.setVisible(checked)

    def _toggle_recording_dock(self, checked: bool):
        """Toggle recording dock visibility"""
        self.recording_dock.setVisible(checked)

    def _toggle_playback_dock(self, checked: bool):
        """Toggle playback dock visibility"""
        self.playback_dock.setVisible(checked)
        if checked:
            # 재생 독이 열릴 때 녹화 파일 스캔
            self.playback_widget.scan_recordings()

    def _on_camera_dock_visibility_changed(self, visible: bool):
        """Camera dock visibility 변경 시 메뉴 액션 동기화"""
        self.camera_dock_action.setChecked(visible)
        logger.debug(f"Camera dock visibility changed: {visible}")

    def _on_recording_dock_visibility_changed(self, visible: bool):
        """Recording dock visibility 변경 시 메뉴 액션 동기화"""
        self.recording_dock_action.setChecked(visible)
        logger.debug(f"Recording dock visibility changed: {visible}")

    def _on_playback_dock_visibility_changed(self, visible: bool):
        """Playback dock visibility 변경 시 메뉴 액션 동기화"""
        self.playback_dock_action.setChecked(visible)
        logger.debug(f"Playback dock visibility changed: {visible}")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _open_playback_mode(self):
        """재생 모드 열기"""
        logger.info("Opening playback mode...")

        # 재생 독 표시
        self.playback_dock.show()

        # 라이브 스트리밍 일시 중지 (선택적)
        if self.is_playback_mode:
            return

        self.is_playback_mode = True

        # 모든 카메라 연결 해제 (재생 모드에서는 리소스 절약)
        self.camera_list._disconnect_all()

        # 녹화 파일 스캔
        self.playback_widget.scan_recordings()

        # 상태바 업데이트
        self.status_bar.showMessage("재생 모드", 3000)

        logger.info("Playback mode opened")

    def _close_playback_mode(self):
        """재생 모드 닫기"""
        logger.info("Closing playback mode...")

        if not self.is_playback_mode:
            return

        # 재생 중인 파일 정지
        if self.playback_widget:
            self.playback_widget.stop_playback()

        # 재생 독 숨기기
        self.playback_dock.hide()

        self.is_playback_mode = False

        # 카메라 재연결 (선택적)
        # self._connect_all_cameras()

        # 상태바 업데이트
        self.status_bar.showMessage("라이브 모드", 3000)

        logger.info("Playback mode closed")

    def _refresh_recordings(self):
        """녹화 파일 목록 새로고침"""
        if self.playback_widget:
            self.playback_widget.scan_recordings()
            logger.info("Recordings refreshed")

    def _show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
        <b>Keyboard Shortcuts:</b><br><br>
        <b>General:</b><br>
        Ctrl+N - Add Camera<br>
        Ctrl+Q - Exit<br>
        F11 - Toggle Fullscreen<br><br>

        <b>View:</b><br>
        Alt+1 - Single View<br>
        F - Toggle Fullscreen<br>
        ESC - Exit Fullscreen<br><br>

        <b>Camera Control:</b><br>
        Ctrl+Shift+C - Connect Camera<br>
        Ctrl+Shift+D - Disconnect Camera<br><br>

        <b>Playback:</b><br>
        F5 - Refresh Recordings<br>
        Space - Play/Pause (in playback)<br>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.RichText)
        msg.setText(shortcuts)
        msg.exec_()

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            f"About {self.app_name}",
            f"<b>{self.app_name} - Network Video Recorder</b><br>"
            f"Version {self.app_version}<br><br>"
            "Single Camera View<br>"
            "Built with GStreamer and PyQt5<br><br>"
            "Optimized for single camera recording"
        )

    def _load_dock_state(self):
        """Load dock state from YAML configuration"""
        # Dock 표시 여부 복원 (YAML에서 로드)
        dock_state = self.config_manager.ui_config.dock_state
        camera_visible = dock_state.get("camera_visible", True)
        recording_visible = dock_state.get("recording_visible", True)
        playback_visible = dock_state.get("playback_visible", False)

        # Dock 표시 상태 설정
        self.camera_dock.setVisible(camera_visible)
        self.recording_dock.setVisible(recording_visible)
        self.playback_dock.setVisible(playback_visible)

        # 메뉴 체크 상태 동기화
        self.camera_dock_action.setChecked(camera_visible)
        self.recording_dock_action.setChecked(recording_visible)
        self.playback_dock_action.setChecked(playback_visible)

        logger.info(f"Dock state loaded from YAML - Camera: {camera_visible}, Recording: {recording_visible}, Playback: {playback_visible}")

    def _save_dock_state(self):
        """Save dock state to JSON configuration"""
        # 현재 윈도우 위치/크기 저장
        geometry = self.geometry()
        self.config_manager.update_ui_window_state(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height()
        )

        # 현재 Dock 표시 상태 저장
        self.config_manager.update_ui_dock_state(
            camera_visible=self.camera_dock.isVisible(),
            recording_visible=self.recording_dock.isVisible(),
            playback_visible=self.playback_dock.isVisible()
        )

        # JSON 파일에 저장
        self.config_manager.save_ui_config()

        logger.info(f"UI state saved to JSON - Window: {geometry.x()},{geometry.y()} {geometry.width()}x{geometry.height()}, Docks: Camera={self.camera_dock.isVisible()}, Recording={self.recording_dock.isVisible()}, Playback={self.playback_dock.isVisible()}")

    def closeEvent(self, event: QCloseEvent):
        """Handle application close event"""
        logger.info("Shutting down application...")

        # Dock 상태 저장
        self._save_dock_state()

        # Stop timers
        if self.status_timer:
            self.status_timer.stop()

        if hasattr(self, 'clock_timer') and self.clock_timer:
            self.clock_timer.stop()

        # Stop system monitoring thread
        if self.monitor_thread:
            self.monitor_thread.stop()

        # Stop playback if active
        if self.playback_widget:
            self.playback_widget.cleanup()

        # Disconnect all cameras
        self.camera_list._disconnect_all()

        # NOTE: save_config() 제거됨
        # 프로그램 종료 시 자동 저장하면 cameras가 비어있을 때 설정이 초기화되는 문제 발생
        # 설정은 UI에서 카메라 추가/제거 시에만 저장됨

        event.accept()
        logger.info("Application closed")