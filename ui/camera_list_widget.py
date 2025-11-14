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
from PyQt5.QtGui import QColor
from loguru import logger

# Fix imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
        self.recording_control_widget = None  # RecordingControlWidget 참조 (스토리지 모니터링용)

        self._setup_ui()
        self._setup_context_menu()
        self._load_cameras()
        self._setup_timer()

    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Camera Streaming Status GroupBox
        status_group = QGroupBox("Camera Streaming Status")
        font = status_group.font()
        font.setPointSize(10)  # 글씨 크기
        status_group.setFont(font)
        status_layout = QVBoxLayout()

        # Camera list
        self.list_widget = QListWidget()
        font = self.list_widget.font()
        font.setPointSize(10)  # 글씨 크기
        self.list_widget.setFont(font)
        # Use theme from main window - no hardcoded style
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        status_layout.addWidget(self.list_widget)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Status bar
        self.status_label = QLabel("0 cameras configured")
        font = self.status_label.font()
        font.setPointSize(10)  # 글씨 크기
        self.status_label.setFont(font)
        # Use theme from main window - no hardcoded style
        self.status_label.setStyleSheet("padding: 5px;")  # Keep padding only
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def _setup_context_menu(self):
        """Setup context menu for camera items"""
        self.context_menu = QMenu(self)
        # Use theme from main window - no hardcoded style

        # Connect/Disconnect (Dynamic single action)
        self.connection_action = QAction("Connect", self)
        self.connection_action.triggered.connect(self._toggle_connection)
        self.context_menu.addAction(self.connection_action)

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
        stream = CameraStream(stream_config, recording_control_widget=self.recording_control_widget)
        self.camera_streams[camera_config.camera_id] = stream
        item.set_camera_stream(stream)

    def set_recording_control_widget(self, widget):
        """
        RecordingControlWidget 설정 및 기존 카메라들의 콜백 등록

        Args:
            widget: RecordingControlWidget 인스턴스
        """
        logger.info(f"[STORAGE] Setting recording_control_widget, found {len(self.camera_streams)} camera stream(s)")
        self.recording_control_widget = widget

        # 기존 CameraStream 객체들에도 위젯 설정
        for camera_id, stream in self.camera_streams.items():
            stream.recording_control_widget = widget
            logger.debug(f"[STORAGE] Set recording_control_widget for stream: {camera_id}")

            # 이미 연결된 카메라들의 스토리지 콜백 등록
            if stream.gst_pipeline:
                callback = stream.gst_pipeline.get_storage_error_callback()
                widget.register_storage_error_callback(camera_id, callback)
                logger.info(f"[STORAGE] ✓ Registered storage callback for existing connected camera: {camera_id}")
            else:
                logger.debug(f"[STORAGE] Camera {camera_id} not yet connected, will register callback on connect")

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

        # Update Connect/Disconnect text and enable state
        if camera_item.camera_stream and camera_item.camera_stream.is_connected():
            self.connection_action.setText("Disconnect")
            self.connection_action.setEnabled(True)
        else:
            self.connection_action.setText("Connect")
            # Only enable Connect if camera is enabled
            self.connection_action.setEnabled(camera_item.camera_config.enabled)

        # Show menu
        self.context_menu.exec_(self.list_widget.mapToGlobal(pos))

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

    def _toggle_connection(self):
        """Toggle connection state of selected camera"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        camera_item = current_item
        if camera_item.camera_stream and camera_item.camera_stream.is_connected():
            # Currently connected, so disconnect
            self._disconnect_camera()
        else:
            # Currently disconnected, so connect
            self._connect_camera()

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

    def update_camera_streams_config(self):
        """
        모든 CameraStream의 설정 업데이트 (효율적인 방법)

        Settings에서 카메라 설정이 변경되었을 때 호출
        기존 객체를 재사용하고 설정만 업데이트
        """
        logger.info("Updating camera stream configurations...")

        # ConfigManager에서 최신 카메라 설정 가져오기
        cameras = self.config_manager.get_all_cameras()
        streaming_config = self.config_manager.get_streaming_config()

        # 재연결이 필요한 카메라 추적
        reconnect_needed = {}  # camera_id -> (was_connected, was_recording)

        for camera in cameras:
            camera_id = camera.camera_id

            # 기존 스트림이 있는지 확인
            if camera_id not in self.camera_streams:
                # 새로운 카메라 추가된 경우 (Settings에서 Add한 경우)
                logger.info(f"New camera detected: {camera_id}, creating CameraStream...")
                self._add_camera_item(camera)
                continue

            stream = self.camera_streams[camera_id]

            # 연결 상태 저장
            was_connected = stream.is_connected()
            was_recording = False

            if stream.gst_pipeline:
                was_recording = stream.gst_pipeline._is_recording

            # 새로운 설정으로 업데이트
            new_config = CameraConfig(
                camera_id=camera.camera_id,
                name=camera.name,
                rtsp_url=camera.rtsp_url,  # ✅ 변경된 RTSP URL
                username=camera.username,
                password=camera.password,
                use_hardware_decode=camera.use_hardware_decode,
                reconnect_attempts=streaming_config.get("max_reconnect_attempts", 5),
                reconnect_delay=streaming_config.get("reconnect_delay_seconds", 5),
                streaming_enabled_start=camera.streaming_enabled_start,
                recording_enabled_start=camera.recording_enabled_start,
                ptz_type=camera.ptz_type,
                ptz_port=camera.ptz_port,
                ptz_channel=camera.ptz_channel
            )

            # ✅ 핵심: 설정만 업데이트 (객체 재생성 안 함)
            needs_reconnect = stream.update_config(new_config)

            # CameraListItem 업데이트
            if camera_id in self.camera_items:
                camera_item = self.camera_items[camera_id]
                camera_item.camera_config = camera
                camera_item.update_display()

            # 재연결이 필요한 경우만 추적
            if needs_reconnect and was_connected:
                # 연결 해제 (새 URL로 재연결 필요)
                logger.info(f"Disconnecting {camera_id} for reconnection with new URL...")
                stream.disconnect()
                reconnect_needed[camera_id] = (was_connected, was_recording)

            logger.success(f"✓ Config updated for {camera_id}")

        # 삭제된 카메라 제거 (Settings에서 Delete한 경우)
        current_camera_ids = {cam.camera_id for cam in cameras}
        for camera_id in list(self.camera_streams.keys()):
            if camera_id not in current_camera_ids:
                logger.info(f"Camera removed from config: {camera_id}, removing CameraStream...")
                stream = self.camera_streams[camera_id]
                if stream.is_connected():
                    stream.disconnect()
                del self.camera_streams[camera_id]

                if camera_id in self.camera_items:
                    # UI에서 제거
                    item = self.camera_items[camera_id]
                    row = self.list_widget.row(item)
                    self.list_widget.takeItem(row)
                    del self.camera_items[camera_id]

        # ⭐ 중요: 설정 변경 시 항상 GridView 채널 재할당 및 RecordingControlWidget 재등록
        # (카메라 추가/삭제/수정 모두 포함)
        if self.main_window:
            logger.info("Re-assigning cameras to channels and recording control after config change...")

            # GridView 채널 재할당
            self.main_window._auto_assign_cameras()

            # RecordingControlWidget 재등록
            self.main_window._populate_recording_control()

            # 윈도우 핸들 재할당
            self.main_window._assign_window_handles_to_streams()

            logger.success("✓ Camera re-assignment completed")

        # 재연결 필요한 카메라 알림
        if reconnect_needed:
            msg_text = "카메라 설정이 변경되었습니다.\n\n"
            msg_text += "다음 카메라의 연결이 해제되었습니다:\n"

            for cam_id, (was_conn, was_rec) in reconnect_needed.items():
                camera = self.config_manager.get_camera(cam_id)
                camera_name = camera.name if camera else cam_id
                msg_text += f"  • {camera_name}"

                if was_rec:
                    msg_text += " (녹화 중이었음)"

                msg_text += "\n"

            msg_text += "\n변경사항을 적용하려면 카메라를 다시 연결해주세요."

            # MainWindow를 parent로 사용
            parent = self.main_window if hasattr(self, 'main_window') and self.main_window else self
            QMessageBox.information(
                parent,
                "카메라 설정 변경됨",
                msg_text
            )

            logger.info(f"User notified: {len(reconnect_needed)} camera(s) need reconnection")

        # 상태 업데이트
        self._update_status()

        logger.success(f"✓ All camera stream configs updated")