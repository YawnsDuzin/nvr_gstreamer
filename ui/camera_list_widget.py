"""
Camera List Widget
Manages and displays list of configured cameras
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QMenu,
    QAction, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QColor, QFont
from loguru import logger

# Fix imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.camera_dialog import CameraDialog
from ui.theme import ThemedWidget
from core.config import ConfigManager, CameraConfigData
from camera.streaming import CameraStream, CameraConfig


class CameraListItem(QListWidgetItem):
    """Custom list item for camera"""

    def __init__(self, camera_config: CameraConfigData):
        super().__init__()
        self.camera_config = camera_config
        self.camera_stream = None
        self.update_display()

    def update_display(self):
        """Update item display text"""
        if not self.camera_config.enabled:
            # 비활성화: ⚫ 검은 원과 동일한 색상
            status_icon = "⚫"
            status_text = "비활성화"
            color = QColor(100, 100, 100)  # 어두운 회색
        elif self.camera_stream and self.camera_stream.is_connected():
            # 활성화 + 연결됨: 🟢 녹색 원과 동일한 색상
            status_icon = "🟢"
            status_text = "연결됨"
            color = QColor(0, 255, 0)  # 순수 녹색
        else:
            # 활성화 + 연결안됨: ⚪ 흰 원과 동일한 색상
            status_icon = "⚪"
            status_text = "대기중"
            color = QColor(255, 255, 255)  # 흰색

        display_text = f"{status_icon} {self.camera_config.name} ({self.camera_config.camera_id}) [{status_text}]"
        self.setText(display_text)
        self.setForeground(color)

    def set_camera_stream(self, stream: CameraStream):
        """Set associated camera stream"""
        self.camera_stream = stream
        self.update_display()


class CameraListWidget(ThemedWidget):
    """Widget for managing camera list"""

    # Signals
    camera_selected = pyqtSignal(str)  # Camera ID
    camera_added = pyqtSignal(CameraConfigData)
    camera_removed = pyqtSignal(str)  # Camera ID
    camera_updated = pyqtSignal(CameraConfigData)
    camera_connected = pyqtSignal(str)  # Camera ID
    camera_disconnected = pyqtSignal(str)  # Camera ID

    def __init__(self, config_manager: ConfigManager = None, parent=None):
        super().__init__(parent)
        # Get singleton instance if not provided
        self.config_manager = config_manager or ConfigManager.get_instance()
        self.camera_items = {}  # camera_id -> CameraListItem
        self.camera_streams = {}  # camera_id -> CameraStream
        self.main_window = None  # Reference to main window for grid_view access

        self._setup_ui()
        self._setup_context_menu()
        self._load_cameras()
        self._setup_timer()

    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Camera Streaming Status GroupBox
        status_group = QGroupBox("Camera Streaming Status")
        status_layout = QVBoxLayout()

        # Camera list
        self.list_widget = QListWidget()
        # Use theme from main window - no hardcoded style
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        status_layout.addWidget(self.list_widget)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Toolbar buttons
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Status bar
        self.status_label = QLabel("0 cameras configured")
        # Use theme from main window - no hardcoded style
        self.status_label.setStyleSheet("padding: 5px;")  # Keep padding only
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.setMinimumWidth(350)

    def _create_toolbar(self):
        """Create toolbar with camera actions"""
        toolbar_group = QGroupBox("Camera Controls")
        layout = QVBoxLayout()

        # Management buttons row
        management_layout = QHBoxLayout()
        management_layout.setSpacing(5)

        # Add button
        add_btn = QPushButton("➕ Add")
        add_btn.setToolTip("Add Camera")
        add_btn.clicked.connect(self._add_camera)
        management_layout.addWidget(add_btn)

        # Edit button
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.setToolTip("Edit Camera")
        edit_btn.clicked.connect(self._edit_camera)
        management_layout.addWidget(edit_btn)

        # Remove button
        remove_btn = QPushButton("🗑️ Remove")
        remove_btn.setToolTip("Remove Camera")
        remove_btn.clicked.connect(self._remove_camera)
        management_layout.addWidget(remove_btn)

        layout.addLayout(management_layout)

        # Connection buttons row
        connection_layout = QHBoxLayout()
        connection_layout.setSpacing(5)

        # Connect all button
        connect_all_btn = QPushButton("🔗 Connect All")
        connect_all_btn.clicked.connect(self._connect_all)
        connection_layout.addWidget(connect_all_btn)

        # Disconnect all button
        disconnect_all_btn = QPushButton("⛓️ Disconnect All")
        disconnect_all_btn.clicked.connect(self._disconnect_all)
        connection_layout.addWidget(disconnect_all_btn)

        layout.addLayout(connection_layout)

        toolbar_group.setLayout(layout)
        return toolbar_group

    def _setup_context_menu(self):
        """Setup context menu for camera items"""
        self.context_menu = QMenu(self)
        # Use theme from main window - no hardcoded style

        # Connect/Disconnect
        self.connect_action = QAction("Connect", self)
        self.connect_action.triggered.connect(self._connect_camera)
        self.context_menu.addAction(self.connect_action)

        self.disconnect_action = QAction("Disconnect", self)
        self.disconnect_action.triggered.connect(self._disconnect_camera)
        self.context_menu.addAction(self.disconnect_action)

        self.context_menu.addSeparator()

        # Edit
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_camera)
        self.context_menu.addAction(edit_action)

        # Enable/Disable
        self.enable_action = QAction("Enable", self)
        self.enable_action.triggered.connect(self._toggle_camera)
        self.context_menu.addAction(self.enable_action)

        self.context_menu.addSeparator()

        # Remove
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self._remove_camera)
        self.context_menu.addAction(remove_action)

    def _setup_timer(self):
        """Setup status update timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(2000)  # Update every 2 seconds

    def _load_cameras(self):
        """Load cameras from configuration"""
        self.list_widget.clear()
        self.camera_items.clear()

        for camera_config in self.config_manager.cameras:
            self._add_camera_item(camera_config)

        self._update_status()

    def _add_camera_item(self, camera_config: CameraConfigData):
        """Add camera item to list"""
        item = CameraListItem(camera_config)
        self.list_widget.addItem(item)
        self.camera_items[camera_config.camera_id] = item

        # Create camera stream object with reconnection settings from streaming config
        streaming_config = self.config_manager.get_streaming_config()
        stream_config = CameraConfig(
            camera_id=camera_config.camera_id,
            name=camera_config.name,
            rtsp_url=camera_config.rtsp_url,
            username=camera_config.username,
            password=camera_config.password,
            use_hardware_decode=camera_config.use_hardware_decode,
            reconnect_attempts=streaming_config.get("max_reconnect_attempts", 5),
            reconnect_delay=streaming_config.get("reconnect_delay_seconds", 5),
            streaming_enabled_start=camera_config.streaming_enabled_start,
            recording_enabled_start=camera_config.recording_enabled_start,
            ptz_type=camera_config.ptz_type,
            ptz_port=camera_config.ptz_port,
            ptz_channel=camera_config.ptz_channel
        )
        stream = CameraStream(stream_config)
        self.camera_streams[camera_config.camera_id] = stream
        item.set_camera_stream(stream)

    def _update_status(self):
        """Update status label and camera items"""
        total = len(self.camera_items)
        enabled = sum(1 for item in self.camera_items.values()
                     if item.camera_config.enabled)
        connected = sum(1 for item in self.camera_items.values()
                       if item.camera_stream and item.camera_stream.is_connected())

        self.status_label.setText(f"{total} cameras | {enabled} enabled | {connected} connected")

        # Update item displays
        for item in self.camera_items.values():
            item.update_display()

    def _on_item_clicked(self, item: CameraListItem):
        """Handle item click"""
        self.camera_selected.emit(item.camera_config.camera_id)

    def _on_item_double_clicked(self, item: CameraListItem):
        """Handle item double-click"""
        if item.camera_config.enabled:
            if item.camera_stream and item.camera_stream.is_connected():
                self._disconnect_camera()
            else:
                self._connect_camera()

    def _show_context_menu(self, pos):
        """Show context menu"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        # Update menu actions based on camera state
        camera_item = item
        if camera_item.camera_config.enabled:
            self.enable_action.setText("Disable")
        else:
            self.enable_action.setText("Enable")

        if camera_item.camera_stream and camera_item.camera_stream.is_connected():
            self.connect_action.setEnabled(False)
            self.disconnect_action.setEnabled(True)
        else:
            self.connect_action.setEnabled(True)
            self.disconnect_action.setEnabled(False)

        # Show menu
        self.context_menu.exec_(self.list_widget.mapToGlobal(pos))

    def _add_camera(self):
        """Add new camera"""
        dialog = CameraDialog(parent=self)
        dialog.camera_saved.connect(self._on_camera_saved)
        dialog.exec_()

    def _on_camera_saved(self, camera_config: CameraConfig):
        """Handle camera saved from dialog"""
        # Convert to config data
        config_data = CameraConfigData(
            camera_id=camera_config.camera_id,
            name=camera_config.name,
            rtsp_url=camera_config.rtsp_url,
            enabled=getattr(camera_config, 'enabled', True),
            username=camera_config.username,
            password=camera_config.password,
            use_hardware_decode=camera_config.use_hardware_decode,
            streaming_enabled_start=getattr(camera_config, 'streaming_enabled_start', False),
            recording_enabled_start=getattr(camera_config, 'recording_enabled_start', False),
            ptz_type=getattr(camera_config, 'ptz_type', None),
            ptz_port=getattr(camera_config, 'ptz_port', None),
            ptz_channel=getattr(camera_config, 'ptz_channel', None)
        )

        # Add to configuration
        if self.config_manager.add_camera(config_data):
            self.config_manager.save_config()
            self._add_camera_item(config_data)
            self.camera_added.emit(config_data)
            self._update_status()
        else:
            QMessageBox.warning(self, "Error", "Failed to add camera")

    def _edit_camera(self):
        """Edit selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_config = camera_item.camera_config

        # Convert to CameraConfig for dialog
        config = CameraConfig(
            camera_id=camera_config.camera_id,
            name=camera_config.name,
            rtsp_url=camera_config.rtsp_url,
            username=camera_config.username,
            password=camera_config.password,
            use_hardware_decode=camera_config.use_hardware_decode,
            streaming_enabled_start=camera_config.streaming_enabled_start,
            recording_enabled_start=camera_config.recording_enabled_start,
            ptz_type=camera_config.ptz_type,
            ptz_port=camera_config.ptz_port,
            ptz_channel=camera_config.ptz_channel
        )

        dialog = CameraDialog(camera_config=config, parent=self)

        def on_updated(updated_config):
            # Update configuration
            self.config_manager.update_camera(
                camera_config.camera_id,
                name=updated_config.name,
                rtsp_url=updated_config.rtsp_url,
                username=updated_config.username,
                password=updated_config.password,
                use_hardware_decode=updated_config.use_hardware_decode,
                streaming_enabled_start=getattr(updated_config, 'streaming_enabled_start', False),
                recording_enabled_start=getattr(updated_config, 'recording_enabled_start', False),
                ptz_type=getattr(updated_config, 'ptz_type', None),
                ptz_port=getattr(updated_config, 'ptz_port', None),
                ptz_channel=getattr(updated_config, 'ptz_channel', None)
            )
            self.config_manager.save_config()

            # Update item
            camera_item.camera_config = self.config_manager.get_camera(camera_config.camera_id)
            camera_item.update_display()

            self.camera_updated.emit(camera_item.camera_config)

        dialog.camera_saved.connect(on_updated)
        dialog.exec_()

    def _remove_camera(self):
        """Remove selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_id = camera_item.camera_config.camera_id

        reply = QMessageBox.question(
            self,
            "Remove Camera",
            f"Remove camera '{camera_item.camera_config.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Disconnect if connected
            if camera_item.camera_stream and camera_item.camera_stream.is_connected():
                camera_item.camera_stream.disconnect()

            # Remove from configuration
            self.config_manager.remove_camera(camera_id)
            self.config_manager.save_config()

            # Remove from lists
            self.list_widget.takeItem(self.list_widget.row(camera_item))
            del self.camera_items[camera_id]
            del self.camera_streams[camera_id]

            self.camera_removed.emit(camera_id)
            self._update_status()

    def _toggle_camera(self):
        """Enable/disable selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        camera_item.camera_config.enabled = not camera_item.camera_config.enabled

        # Update configuration
        self.config_manager.update_camera(
            camera_item.camera_config.camera_id,
            enabled=camera_item.camera_config.enabled
        )
        self.config_manager.save_config()

        camera_item.update_display()
        self.camera_updated.emit(camera_item.camera_config)
        self._update_status()

    def _connect_camera(self):
        """Connect selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        if camera_item.camera_stream and not camera_item.camera_stream.is_connected():
            # 윈도우 핸들 찾기 (main_window의 grid_view에서)
            window_handle = None
            if self.main_window and hasattr(self.main_window, 'grid_view'):
                grid_view = self.main_window.grid_view
                # 해당 카메라 ID를 가진 채널 찾기
                for channel in grid_view.channels:
                    if channel.camera_id == camera_item.camera_config.camera_id:
                        window_handle = channel.get_window_handle()
                        logger.debug(f"Found window handle for {camera_item.camera_config.camera_id}: {window_handle}")
                        break

            # 녹화 지원 여부 확인
            enable_recording = camera_item.camera_config.recording_enabled_start

            if camera_item.camera_stream.connect(window_handle=window_handle, enable_recording=enable_recording):
                self.camera_connected.emit(camera_item.camera_config.camera_id)
                camera_item.update_display()
                self._update_status()

    def _disconnect_camera(self):
        """Disconnect selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        if camera_item.camera_stream and camera_item.camera_stream.is_connected():
            camera_item.camera_stream.disconnect()
            self.camera_disconnected.emit(camera_item.camera_config.camera_id)
            camera_item.update_display()
            self._update_status()

    def _connect_all(self):
        """Connect all enabled cameras"""
        # main_window의 grid_view 가져오기
        grid_view = None
        if self.main_window and hasattr(self.main_window, 'grid_view'):
            grid_view = self.main_window.grid_view
            logger.info(f"Found grid_view with {len(grid_view.channels)} channels")
        else:
            logger.warning("Could not find grid_view from main_window")

        for camera_item in self.camera_items.values():
            if camera_item.camera_config.enabled and camera_item.camera_stream:
                if not camera_item.camera_stream.is_connected():
                    # 각 카메라에 대한 윈도우 핸들 찾기
                    window_handle = None
                    if grid_view:
                        for channel in grid_view.channels:
                            if channel.camera_id == camera_item.camera_config.camera_id:
                                window_handle = channel.get_window_handle()
                                logger.info(f"Assigning window handle to {camera_item.camera_config.camera_id}: {window_handle}")
                                break

                    if not window_handle:
                        logger.warning(f"No window handle found for {camera_item.camera_config.camera_id}")

                    # 녹화 지원 여부 확인
                    enable_recording = camera_item.camera_config.recording_enabled_start

                    if camera_item.camera_stream.connect(window_handle=window_handle, enable_recording=enable_recording):
                        self.camera_connected.emit(camera_item.camera_config.camera_id)
                        logger.success(f"Connected camera: {camera_item.camera_config.camera_id}")

        self._update_status()

    def _disconnect_all(self):
        """Disconnect all cameras"""
        for camera_item in self.camera_items.values():
            if camera_item.camera_stream and camera_item.camera_stream.is_connected():
                camera_item.camera_stream.disconnect()
                self.camera_disconnected.emit(camera_item.camera_config.camera_id)

        self._update_status()

    def get_camera_stream(self, camera_id: str) -> CameraStream:
        """Get camera stream by ID"""
        return self.camera_streams.get(camera_id)