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
        self.setWindowTitle("PyNVR - Network Video Recorder (Single Camera)")
        self.setGeometry(100, 100, 1200, 700)

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
        self.camera_list.main_window = self  # Set reference to main window for grid_view access
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

        # Set initial layout to 1x1 for single camera
        self.grid_view.set_layout(1, 1)

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

        # Auto-assign cameras to channels first
        self._auto_assign_cameras()
        # Then assign window handles to camera streams
        self._assign_window_handles_to_streams()
        # Finally populate recording control
        self._populate_recording_control()

    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Connection status
        self.connection_label = QLabel("No cameras connected")
        self.status_bar.addWidget(self.connection_label)

        # Layout info
        self.layout_label = QLabel("Layout: Single Camera")
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

        # Single camera setup - only use first camera
        if cameras:
            camera = cameras[0]
            channel = self.grid_view.get_channel(0)
            if channel:
                channel.update_camera_info(camera.camera_id, camera.name)
                logger.debug(f"Assigned {camera.camera_id} to single channel")

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

    def _show_settings(self):
        """Show settings dialog"""
        QMessageBox.information(self, "Settings", "Settings dialog not yet implemented")

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

        <b>View:</b><br>
        Alt+1 - Single View<br>
        F - Toggle Fullscreen<br>
        ESC - Exit Fullscreen<br><br>

        <b>Camera Control:</b><br>
        Ctrl+Shift+C - Connect Camera<br>
        Ctrl+Shift+D - Disconnect Camera<br>
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
            "Single Camera View<br>"
            "Built with GStreamer and PyQt5<br><br>"
            "Optimized for single camera recording"
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