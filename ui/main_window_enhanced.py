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
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QSettings
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
from config.config_manager import ConfigManager
from streaming.camera_stream import CameraStream
from recording.recording_manager import RecordingManager


class EnhancedMainWindow(QMainWindow):
    """Enhanced main application window with 4-channel grid view"""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.recording_manager = RecordingManager()
        self.grid_view = None
        self.camera_list = None
        self.recording_control = None
        self.settings = QSettings("PyNVR", "MainWindow")

        self._setup_ui()
        self._setup_menus()
        self._setup_connections()
        self._setup_status_bar()
        self._load_window_state()

        logger.info("Enhanced main window initialized")

    def _setup_ui(self):
        """Setup main UI with splitter layout"""
        self.setWindowTitle("PyNVR - Network Video Recorder (4-Channel View)")
        self.setGeometry(100, 100, 1400, 800)

        # Central widget with splitter
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Camera list (as dock widget)
        self.camera_dock = QDockWidget("Cameras", self)
        self.camera_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.camera_list = CameraListWidget(self.config_manager)
        self.camera_dock.setWidget(self.camera_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.camera_dock)

        # Right panel - Recording control (as dock widget)
        self.recording_dock = QDockWidget("Recording Control", self)
        self.recording_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.recording_control = RecordingControlWidget(self.recording_manager)
        self.recording_dock.setWidget(self.recording_control)
        self.addDockWidget(Qt.RightDockWidgetArea, self.recording_dock)

        # Main area - Grid view
        self.grid_view = GridViewWidget()
        splitter.addWidget(self.grid_view)

        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Apply dark theme
        self._apply_dark_theme()

        # Set initial layout to 2x2
        self.grid_view.set_layout(2, 2)

    def _apply_dark_theme(self):
        """Apply dark theme to application"""
        dark_style = """
        QMainWindow {
            background-color: #1a1a1a;
        }
        QMenuBar {
            background-color: #2a2a2a;
            color: #ffffff;
            border-bottom: 1px solid #3a3a3a;
        }
        QMenuBar::item:selected {
            background-color: #3a3a3a;
        }
        QMenu {
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1px solid #3a3a3a;
        }
        QMenu::item:selected {
            background-color: #3a3a3a;
        }
        QStatusBar {
            background-color: #2a2a2a;
            color: #ffffff;
            border-top: 1px solid #3a3a3a;
        }
        QDockWidget {
            background-color: #1a1a1a;
            color: #ffffff;
        }
        QDockWidget::title {
            background-color: #2a2a2a;
            padding: 5px;
            border-bottom: 1px solid #3a3a3a;
        }
        QSplitter::handle {
            background-color: #3a3a3a;
        }
        """
        self.setStyleSheet(dark_style)

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

        settings_action = QAction("Settings", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        # Layout submenu
        layout_menu = view_menu.addMenu("Layout")

        layout_1x1 = QAction("1x1", self)
        layout_1x1.setShortcut(QKeySequence("Alt+1"))
        layout_1x1.triggered.connect(lambda: self.grid_view.set_layout(1, 1))
        layout_menu.addAction(layout_1x1)

        layout_2x2 = QAction("2x2", self)
        layout_2x2.setShortcut(QKeySequence("Alt+2"))
        layout_2x2.triggered.connect(lambda: self.grid_view.set_layout(2, 2))
        layout_menu.addAction(layout_2x2)

        layout_3x3 = QAction("3x3", self)
        layout_3x3.setShortcut(QKeySequence("Alt+3"))
        layout_3x3.triggered.connect(lambda: self.grid_view.set_layout(3, 3))
        layout_menu.addAction(layout_3x3)

        layout_4x4 = QAction("4x4", self)
        layout_4x4.setShortcut(QKeySequence("Alt+4"))
        layout_4x4.triggered.connect(lambda: self.grid_view.set_layout(4, 4))
        layout_menu.addAction(layout_4x4)

        view_menu.addSeparator()

        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        # Dock visibility
        camera_dock_action = QAction("Show Camera List", self)
        camera_dock_action.setCheckable(True)
        camera_dock_action.setChecked(True)
        camera_dock_action.triggered.connect(self._toggle_camera_dock)
        view_menu.addAction(camera_dock_action)

        recording_dock_action = QAction("Show Recording Control", self)
        recording_dock_action.setCheckable(True)
        recording_dock_action.setChecked(True)
        recording_dock_action.triggered.connect(self._toggle_recording_dock)
        view_menu.addAction(recording_dock_action)

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

        # Auto-assign cameras to channels and recording control
        self._auto_assign_cameras()
        self._populate_recording_control()

    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Connection status
        self.connection_label = QLabel("No cameras connected")
        self.status_bar.addWidget(self.connection_label)

        # Layout info
        self.layout_label = QLabel("Layout: 2x2")
        self.status_bar.addPermanentWidget(self.layout_label)

        # Update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)

    def _update_status(self):
        """Update status bar"""
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

    def _auto_assign_cameras(self):
        """Auto-assign cameras from config to grid channels"""
        cameras = self.config_manager.get_enabled_cameras()

        for i, camera in enumerate(cameras[:16]):  # Max 16 channels (4x4)
            channel = self.grid_view.get_channel(i)
            if channel:
                channel.update_camera_info(camera.camera_id, camera.name)

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
            return

        # Find channel with this camera and update
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                # Get window handle and set it on the pipeline
                window_handle = channel.get_window_handle()
                if window_handle and stream.pipeline_manager:
                    # Set video sink to render in widget
                    stream.pipeline_manager.set_window_handle(window_handle)
                    logger.info(f"Set window handle for camera {camera_id}: {window_handle}")

                channel.set_connected(True)
                break

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
        self.layout_label.setText(f"Layout: {rows}x{cols}")
        logger.info(f"Layout changed to {rows}x{cols}")

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

    def _show_settings(self):
        """Show settings dialog"""
        QMessageBox.information(self, "Settings", "Settings dialog not yet implemented")

    def _connect_all_cameras(self):
        """Connect all cameras"""
        # 먼저 각 카메라에 윈도우 핸들 할당
        self._assign_window_handles_to_cameras()
        # 그 다음 연결
        self.camera_list._connect_all()

    def _disconnect_all_cameras(self):
        """Disconnect all cameras"""
        self.camera_list._disconnect_all()

    def _assign_window_handles_to_cameras(self):
        """각 카메라에 윈도우 핸들을 미리 할당"""
        cameras = self.config_manager.get_enabled_cameras()

        for i, camera in enumerate(cameras[:16]):  # 최대 16채널
            channel = self.grid_view.get_channel(i)
            if channel:
                # 채널에 카메라 정보 업데이트
                channel.update_camera_info(camera.camera_id, camera.name)

                # 윈도우 핸들 가져오기
                window_handle = channel.get_window_handle()

                # 카메라 스트림에 윈도우 핸들 미리 설정
                stream = self.camera_list.get_camera_stream(camera.camera_id)
                if stream and window_handle:
                    # 연결 전에 윈도우 핸들 저장
                    stream.window_handle = window_handle
                    logger.info(f"Pre-assigned window handle for {camera.camera_id}: {window_handle}")

    def _toggle_camera_dock(self, checked: bool):
        """Toggle camera dock visibility"""
        self.camera_dock.setVisible(checked)

    def _toggle_recording_dock(self, checked: bool):
        """Toggle recording dock visibility"""
        self.recording_dock.setVisible(checked)

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
        <b>Keyboard Shortcuts:</b><br><br>
        <b>General:</b><br>
        Ctrl+N - Add Camera<br>
        Ctrl+Q - Exit<br>
        F11 - Toggle Fullscreen<br><br>

        <b>Layout:</b><br>
        Alt+1 - 1x1 Layout<br>
        Alt+2 - 2x2 Layout<br>
        Alt+3 - 3x3 Layout<br>
        Alt+4 - 4x4 Layout<br><br>

        <b>Channels:</b><br>
        1-9 - Select Channel<br>
        F - Toggle Channel Fullscreen<br>
        S - Toggle Sequence Mode<br>
        ESC - Exit Fullscreen<br><br>

        <b>Camera Control:</b><br>
        Ctrl+Shift+C - Connect All<br>
        Ctrl+Shift+D - Disconnect All<br>
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
            "About PyNVR",
            "<b>PyNVR - Network Video Recorder</b><br>"
            "Version 0.2.0<br><br>"
            "Enhanced 4-Channel Grid View<br>"
            "Built with GStreamer and PyQt5<br><br>"
            "Designed for Raspberry Pi"
        )

    def _load_window_state(self):
        """Load window state from settings"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_window_state(self):
        """Save window state to settings"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def closeEvent(self, event: QCloseEvent):
        """Handle application close event"""
        logger.info("Shutting down application...")

        # Save window state
        self._save_window_state()

        # Stop timers
        if self.status_timer:
            self.status_timer.stop()

        # Disconnect all cameras
        self.camera_list._disconnect_all()

        # Save configuration
        self.config_manager.save_config()

        event.accept()
        logger.info("Application closed")