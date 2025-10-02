"""
Main application window for PyNVR
"""

import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QAction, QStatusBar, QMenuBar, QMenu,
    QComboBox, QLabel, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QIcon, QKeySequence
from loguru import logger

from video_widget import MultiStreamWidget
from streaming.camera_stream import CameraStream, CameraConfig


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.camera_streams = {}
        self.multi_stream_widget = None
        self.status_timer = None

        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_timers()

        logger.info("Main window initialized")

    def _setup_ui(self):
        """Setup main UI"""
        self.setWindowTitle("PyNVR - Network Video Recorder")
        self.setGeometry(100, 100, 1280, 720)

        # Central widget with video grid
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Add multi-stream widget (2x2 by default)
        self.multi_stream_widget = MultiStreamWidget(rows=2, cols=2)
        layout.addWidget(self.multi_stream_widget)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Apply dark theme
        self._apply_dark_theme()

    def _apply_dark_theme(self):
        """Apply dark theme to application"""
        dark_style = """
        QMainWindow {
            background-color: #1a1a1a;
        }
        QMenuBar {
            background-color: #2a2a2a;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #3a3a3a;
        }
        QMenu {
            background-color: #2a2a2a;
            color: #ffffff;
        }
        QMenu::item:selected {
            background-color: #3a3a3a;
        }
        QToolBar {
            background-color: #2a2a2a;
            border: none;
            spacing: 3px;
        }
        QToolButton {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            padding: 5px;
            margin: 2px;
        }
        QToolButton:hover {
            background-color: #4a4a4a;
        }
        QStatusBar {
            background-color: #2a2a2a;
            color: #ffffff;
        }
        QPushButton {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            padding: 5px 10px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QComboBox {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            padding: 3px;
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
        add_camera_action.triggered.connect(self.add_camera)
        file_menu.addAction(add_camera_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        layout_1x1 = QAction("1x1 Layout", self)
        layout_1x1.triggered.connect(lambda: self.change_layout(1, 1))
        view_menu.addAction(layout_1x1)

        layout_2x2 = QAction("2x2 Layout", self)
        layout_2x2.triggered.connect(lambda: self.change_layout(2, 2))
        view_menu.addAction(layout_2x2)

        layout_3x3 = QAction("3x3 Layout", self)
        layout_3x3.triggered.connect(lambda: self.change_layout(3, 3))
        view_menu.addAction(layout_3x3)

        # Camera menu
        camera_menu = menubar.addMenu("Camera")

        connect_all_action = QAction("Connect All", self)
        connect_all_action.triggered.connect(self.connect_all_cameras)
        camera_menu.addAction(connect_all_action)

        disconnect_all_action = QAction("Disconnect All", self)
        disconnect_all_action.triggered.connect(self.disconnect_all_cameras)
        camera_menu.addAction(disconnect_all_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Setup toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Add camera button
        add_camera_btn = QPushButton("Add Camera")
        add_camera_btn.clicked.connect(self.add_camera)
        toolbar.addWidget(add_camera_btn)

        toolbar.addSeparator()

        # Layout selector
        toolbar.addWidget(QLabel("Layout:"))
        layout_combo = QComboBox()
        layout_combo.addItems(["1x1", "2x2", "3x3", "4x4"])
        layout_combo.setCurrentIndex(1)  # Default to 2x2
        layout_combo.currentTextChanged.connect(self._on_layout_changed)
        toolbar.addWidget(layout_combo)

        toolbar.addSeparator()

        # Connect/Disconnect buttons
        connect_btn = QPushButton("Connect All")
        connect_btn.clicked.connect(self.connect_all_cameras)
        toolbar.addWidget(connect_btn)

        disconnect_btn = QPushButton("Disconnect All")
        disconnect_btn.clicked.connect(self.disconnect_all_cameras)
        toolbar.addWidget(disconnect_btn)

        toolbar.addSeparator()

        # Recording button (placeholder for future)
        record_btn = QPushButton("Start Recording")
        record_btn.setEnabled(False)  # Disabled for now
        toolbar.addWidget(record_btn)

    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status labels
        self.connection_label = QLabel("Cameras: 0/0 connected")
        self.status_bar.addWidget(self.connection_label)

        self.cpu_label = QLabel("CPU: 0%")
        self.status_bar.addPermanentWidget(self.cpu_label)

        self.memory_label = QLabel("Memory: 0%")
        self.status_bar.addPermanentWidget(self.memory_label)

    def _setup_timers(self):
        """Setup update timers"""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # Update every second

    def _update_status(self):
        """Update status bar information"""
        # Update connection count
        connected = sum(1 for stream in self.camera_streams.values() if stream.is_connected())
        total = len(self.camera_streams)
        self.connection_label.setText(f"Cameras: {connected}/{total} connected")

        # TODO: Update CPU and memory usage
        # This would require psutil or similar library

    @pyqtSlot(str)
    def _on_layout_changed(self, layout_text: str):
        """Handle layout change from combo box"""
        if layout_text == "1x1":
            self.change_layout(1, 1)
        elif layout_text == "2x2":
            self.change_layout(2, 2)
        elif layout_text == "3x3":
            self.change_layout(3, 3)
        elif layout_text == "4x4":
            self.change_layout(4, 4)

    def change_layout(self, rows: int, cols: int):
        """
        Change video grid layout

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        logger.info(f"Changing layout to {rows}x{cols}")
        self.multi_stream_widget.update_layout(rows, cols)

    def add_camera(self):
        """Add new camera (placeholder for now)"""
        # TODO: Implement camera add dialog
        from PyQt5.QtWidgets import QInputDialog

        # Simple input dialog for testing
        url, ok = QInputDialog.getText(
            self,
            "Add Camera",
            "Enter RTSP URL:",
            text="rtsp://192.168.1.100:554/stream"
        )

        if ok and url:
            # Create camera config
            camera_id = f"cam_{len(self.camera_streams)}"
            config = CameraConfig(
                camera_id=camera_id,
                name=f"Camera {len(self.camera_streams) + 1}",
                rtsp_url=url,
                use_hardware_decode=False  # Auto-detect later
            )

            # Create camera stream
            stream = CameraStream(config)
            self.camera_streams[camera_id] = stream

            # Connect to first available video widget
            widget_index = len(self.camera_streams) - 1
            video_widget = self.multi_stream_widget.get_video_widget(widget_index)
            if video_widget:
                video_widget.update_camera_info(camera_id, config.name)
                # Connect the stream
                if stream.connect():
                    video_widget.set_connected(True)
                else:
                    video_widget.set_error("Connection failed")

            logger.info(f"Added camera: {config.name}")

    def connect_all_cameras(self):
        """Connect all cameras"""
        logger.info("Connecting all cameras...")
        for camera_id, stream in self.camera_streams.items():
            if not stream.is_connected():
                stream.connect()
                # Update UI
                for i, widget in enumerate(self.multi_stream_widget.video_widgets):
                    if widget.camera_id == camera_id:
                        widget.set_connected(stream.is_connected())
                        break

    def disconnect_all_cameras(self):
        """Disconnect all cameras"""
        logger.info("Disconnecting all cameras...")
        for camera_id, stream in self.camera_streams.items():
            if stream.is_connected():
                stream.disconnect()
                # Update UI
                for widget in self.multi_stream_widget.video_widgets:
                    if widget.camera_id == camera_id:
                        widget.set_connected(False)
                        break

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About PyNVR",
            "PyNVR - Network Video Recorder\n"
            "Version 0.1.0\n\n"
            "A lightweight NVR system for Raspberry Pi\n"
            "Built with GStreamer and PyQt5"
        )

    def closeEvent(self, event):
        """Handle application close event"""
        logger.info("Shutting down application...")

        # Stop all timers
        if self.status_timer:
            self.status_timer.stop()

        # Disconnect all cameras
        for stream in self.camera_streams.values():
            stream.disconnect()

        event.accept()
        logger.info("Application closed")