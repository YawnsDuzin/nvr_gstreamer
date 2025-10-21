"""
Enhanced Grid View Widget
4-channel grid view with channel switching and fullscreen support
"""

from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QCursor
import datetime

# Fix import
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from ui.video_widget import StreamVideoWidget


class ChannelWidget(StreamVideoWidget):
    """Enhanced channel widget with additional features"""

    # Signals
    double_clicked = pyqtSignal(int)  # Channel index
    right_clicked = pyqtSignal(int, object)  # Channel index, QPoint

    def __init__(self, channel_index: int, camera_id: str = "", camera_name: str = "Camera", parent=None):
        super().__init__(camera_id, camera_name, parent)
        self.channel_index = channel_index
        self.is_selected = False
        self.is_fullscreen = False
        self.show_osd = True
        self.is_recording = False

        # Add channel number overlay
        self._setup_channel_overlay()

    def _setup_channel_overlay(self):
        """Setup channel number overlay"""
        self.channel_label = QLabel(str(self.channel_index + 1), self)
        self.channel_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 128);
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.channel_label.move(10, 40)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click for fullscreen"""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.channel_index)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Handle right-click for context menu"""
        self.right_clicked.emit(self.channel_index, event.globalPos())
        super().contextMenuEvent(event)

    def set_selected(self, selected: bool):
        """Set selection state"""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                ChannelWidget {
                    border: 2px solid #4a9eff;
                }
            """)
        else:
            self.setStyleSheet("""
                ChannelWidget {
                    border: 1px solid #333333;
                }
            """)

    def paintEvent(self, event):
        """Custom paint event for OSD overlay"""
        super().paintEvent(event)

        if self.show_osd and self.is_connected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw timestamp
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 10))

            # Draw timestamp in bottom-right corner
            text_rect = QRect(self.width() - 180, self.height() - 30, 170, 20)
            painter.fillRect(text_rect, QColor(0, 0, 0, 128))
            painter.drawText(text_rect, Qt.AlignCenter, current_time)

            # Draw recording indicator if recording
            if hasattr(self, 'is_recording') and self.is_recording:
                painter.setBrush(QColor(255, 0, 0))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(self.width() - 30, 10, 15, 15)

            painter.end()

    def toggle_osd(self):
        """Toggle OSD display"""
        self.show_osd = not self.show_osd
        self.update()

    def set_recording(self, recording: bool):
        """Set recording state"""
        self.is_recording = recording
        self.update()


class GridViewWidget(QWidget):
    """Grid view widget for single camera"""

    # Layout modes - only single view
    LAYOUT_1X1 = (1, 1)

    # Signals
    channel_double_clicked = pyqtSignal(int)
    layout_changed = pyqtSignal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels = []
        self.current_layout = None  # Initialize as None to force initial layout
        self.fullscreen_channel = None
        self.selected_channel = None

        self._setup_ui()
        self._setup_context_menu()
        self._setup_timer()

    def _setup_ui(self):
        """Setup UI components"""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Controls bar
        self.controls_bar = self._create_controls_bar()
        self.layout.addWidget(self.controls_bar)

        # Grid container
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        self.grid_layout.setSpacing(2)
        self.grid_widget.setLayout(self.grid_layout)

        self.layout.addWidget(self.grid_widget, 1)
        self.setLayout(self.layout)

        # Create initial single view
        self.set_layout(1, 1)

        # Apply dark theme
        self.setStyleSheet("background-color: #0a0a0a;")

    def _create_controls_bar(self):
        """Create controls bar"""
        controls = QWidget()
        controls.setFixedHeight(40)
        controls.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-bottom: 1px solid #333333;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        # Single camera - no layout buttons needed
        # Just show single view indicator
        single_view_label = QLabel("Single Camera View")
        single_view_label.setStyleSheet("color: #888888; font-weight: bold;")
        layout.addWidget(single_view_label)

        layout.addSpacing(20)

        # Fullscreen button
        fullscreen_btn = QPushButton("Fullscreen")
        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        layout.addWidget(fullscreen_btn)

        layout.addStretch()

        # Info label
        self.info_label = QLabel("Status: Ready")
        self.info_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.info_label)

        controls.setLayout(layout)

        # Style buttons
        button_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet(button_style)

        return controls

    def _setup_context_menu(self):
        """Setup context menu for channels"""
        self.context_menu = QMenu(self)
        self.context_menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
            }
        """)

        # Add actions
        self.fullscreen_action = QAction("Fullscreen", self)
        self.context_menu.addAction(self.fullscreen_action)

        self.context_menu.addSeparator()

        self.snapshot_action = QAction("Take Snapshot", self)
        self.context_menu.addAction(self.snapshot_action)

        self.record_action = QAction("Start Recording", self)
        self.context_menu.addAction(self.record_action)

        self.context_menu.addSeparator()

        self.properties_action = QAction("Properties", self)
        self.context_menu.addAction(self.properties_action)

    def _setup_timer(self):
        """Setup update timer for OSD"""
        # OSD 업데이트 비활성화 (깜빡임 방지)
        # Single camera - no sequence needed
        pass

    def _update_osd(self):
        """Update OSD for all channels"""
        # 깜빡임 방지를 위해 업데이트 비활성화
        pass
        # for channel in self.channels:
        #     if channel.show_osd:
        #         channel.update()

    def set_layout(self, rows: int, cols: int):
        """
        Set grid layout

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        from loguru import logger

        # 이미 같은 레이아웃이면 스킵
        if self.current_layout == (rows, cols):
            logger.info(f"Already in {rows}x{cols} layout, skipping")
            return

        # Save current camera assignments (순서대로 저장)
        saved_cameras = []
        for channel in self.channels:
            if channel.camera_id and channel.camera_id != f"cam_{channel.channel_index}":
                saved_cameras.append({
                    'camera_id': channel.camera_id,
                    'camera_name': channel.camera_name,
                    'is_connected': channel.is_connected
                })

        logger.info(f"Saving {len(saved_cameras)} active camera assignments")

        # Clear existing channels
        for channel in self.channels:
            self.grid_layout.removeWidget(channel)
            channel.setParent(None)
            channel.deleteLater()
        self.channels.clear()

        # Update layout (always 1x1 for single camera)
        self.current_layout = (rows, cols)
        self.info_label.setText("Status: Ready")

        # Create new channels
        channel_index = 0
        for row in range(rows):
            for col in range(cols):
                # 저장된 카메라를 순서대로 재할당
                if channel_index < len(saved_cameras):
                    camera_info = saved_cameras[channel_index]
                    channel = ChannelWidget(
                        channel_index,
                        camera_info['camera_id'],
                        camera_info['camera_name']
                    )
                    # 연결 상태는 일단 false로 설정 (재연결 필요)
                    channel.set_connected(False)
                    logger.debug(f"Restored camera {camera_info['camera_id']} to channel {channel_index}")
                else:
                    channel = ChannelWidget(
                        channel_index,
                        f"cam_{channel_index}",
                        f"Camera {channel_index + 1}"
                    )

                # Connect signals
                channel.double_clicked.connect(self._on_channel_double_clicked)
                channel.right_clicked.connect(self._on_channel_right_clicked)

                self.grid_layout.addWidget(channel, row, col)
                self.channels.append(channel)
                channel_index += 1

        # Emit layout changed signal with camera info for re-connection
        self.layout_changed.emit((rows, cols))

        logger.info(f"Grid layout changed to {rows}x{cols}, channels recreated with {len(saved_cameras)} cameras preserved")

    def _on_channel_double_clicked(self, channel_index: int):
        """Handle channel double-click"""
        if 0 <= channel_index < len(self.channels):
            self.show_channel_fullscreen(channel_index)

    def _on_channel_right_clicked(self, channel_index: int, pos):
        """Handle channel right-click"""
        self.selected_channel = channel_index

        # Update context menu actions
        channel = self.channels[channel_index]
        if hasattr(channel, 'is_recording') and channel.is_recording:
            self.record_action.setText("Stop Recording")
        else:
            self.record_action.setText("Start Recording")

        # Show context menu
        self.context_menu.exec_(pos)

    def show_channel_fullscreen(self, channel_index: int):
        """
        Show single channel in fullscreen

        Args:
            channel_index: Index of channel to show
        """
        if self.fullscreen_channel == channel_index:
            # Already in fullscreen, exit
            self.exit_fullscreen()
            return

        # Hide all channels except selected
        for i, channel in enumerate(self.channels):
            if i == channel_index:
                self.grid_layout.removeWidget(channel)
                self.grid_layout.addWidget(channel, 0, 0)
                channel.show()
            else:
                channel.hide()

        self.fullscreen_channel = channel_index
        self.info_label.setText(f"Fullscreen: Camera {channel_index + 1}")

    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        if self.fullscreen_channel is None:
            return

        # Restore grid layout
        rows, cols = self.current_layout
        channel_index = 0
        for row in range(rows):
            for col in range(cols):
                if channel_index < len(self.channels):
                    channel = self.channels[channel_index]
                    self.grid_layout.removeWidget(channel)
                    self.grid_layout.addWidget(channel, row, col)
                    channel.show()
                    channel_index += 1

        self.fullscreen_channel = None
        self.info_label.setText(f"Grid: {rows}x{cols}")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.fullscreen_channel is not None:
            self.exit_fullscreen()
        elif self.selected_channel is not None:
            self.show_channel_fullscreen(self.selected_channel)
        else:
            self.show_channel_fullscreen(0)

    def toggle_sequence(self):
        """Toggle sequence mode - not used for single camera"""
        pass

    def _next_sequence(self):
        """Show next channel in sequence - not used for single camera"""
        pass

    def get_channel(self, index: int) -> ChannelWidget:
        """
        Get channel by index

        Args:
            index: Channel index

        Returns:
            ChannelWidget or None
        """
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def set_channel_camera(self, channel_index: int, camera_id: str, camera_name: str):
        """
        Set camera for specific channel

        Args:
            channel_index: Channel index
            camera_id: Camera ID
            camera_name: Camera name
        """
        channel = self.get_channel(channel_index)
        if channel:
            channel.update_camera_info(camera_id, camera_name)

    def add_camera(self, camera_id: str, camera_name: str) -> ChannelWidget:
        """
        Add camera to next available channel

        Args:
            camera_id: Camera ID
            camera_name: Camera name

        Returns:
            ChannelWidget or None if no channels available
        """
        # Find first available channel
        for channel in self.channels:
            if not channel.camera_id or channel.camera_id.startswith("cam_"):
                channel.update_camera_info(camera_id, camera_name)
                return channel
        return None

    def remove_camera(self, camera_id: str):
        """
        Remove camera from grid

        Args:
            camera_id: Camera ID to remove
        """
        for channel in self.channels:
            if channel.camera_id == camera_id:
                # Reset to default
                channel.update_camera_info(f"cam_{channel.channel_index}", f"Camera {channel.channel_index + 1}")
                channel.set_connected(False)
                break

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()

        # Number keys 1-9 for channel selection
        if Qt.Key_1 <= key <= Qt.Key_9:
            channel_index = key - Qt.Key_1
            if channel_index < len(self.channels):
                self.show_channel_fullscreen(channel_index)

        # ESC to exit fullscreen
        elif key == Qt.Key_Escape:
            if self.fullscreen_channel is not None:
                self.exit_fullscreen()

        # F for fullscreen toggle
        elif key == Qt.Key_F:
            self.toggle_fullscreen()

        # S for sequence toggle
        elif key == Qt.Key_S:
            self.toggle_sequence()

        super().keyPressEvent(event)


# Alias for backward compatibility
GridView = GridViewWidget