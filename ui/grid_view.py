"""
Enhanced Grid View Widget
4-channel grid view with channel switching and fullscreen support
"""

from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMenu, QAction, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QCursor, QFontMetrics
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

            # 녹화 인디케이터 제거 - recording_status_label로 표시됨

            painter.end()

    def toggle_osd(self):
        """Toggle OSD display"""
        self.show_osd = not self.show_osd
        self.update()

    def set_recording(self, recording: bool):
        """Set recording state - delegated to parent StreamVideoWidget"""
        self.is_recording = recording
        # 부모 클래스의 set_recording 호출 (recording_status_label 업데이트)
        super().set_recording(recording)


class GridViewWidget(QWidget):
    """Grid view widget for multiple cameras with flexible layouts"""

    # Layout modes - support multi-camera grids
    LAYOUT_1X1 = (1, 1)
    LAYOUT_2X2 = (2, 2)
    LAYOUT_3X3 = (3, 3)
    LAYOUT_4X4 = (4, 4)

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

        # Use theme from main window - no hardcoded style

    def _create_controls_bar(self):
        """Create controls bar"""
        controls = QWidget()
        controls.setFixedHeight(40)
        # Use theme from main window - no hardcoded style
        controls.setStyleSheet("border-bottom: 1px solid #3c3c3c;")  # Keep only border

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 10, 2)  # 상하 여백 축소
        layout.setAlignment(Qt.AlignVCenter)  # 세로 중앙 정렬

        # Layout selector label
        layout_label = QLabel("Layout:")
        font = layout_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        layout_label.setFont(font)
        layout.addWidget(layout_label, 0, Qt.AlignVCenter)

        # Layout buttons with dynamic sizing
        self.layout_buttons = {}
        for layout_name, layout_size in [("1x1", (1, 1)), ("2x2", (2, 2)),
                                          ("3x3", (3, 3)), ("4x4", (4, 4))]:
            btn = QPushButton(layout_name)

            # 텍스트에 맞춰 버튼 크기를 동적으로 설정
            font = btn.font()
            font.setPointSize(11)  # 폰트 크기를 11로 증가
            btn.setFont(font)

            # QFontMetrics를 사용해 텍스트 너비 계산
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(layout_name) if hasattr(fm, 'horizontalAdvance') else fm.width(layout_name)
            padding = 24  # 텍스트 양쪽 여백도 약간 증가

            # 버튼 크기 설정 - 텍스트 너비 + 여백
            btn.setMinimumWidth(text_width + padding)
            btn.setMaximumWidth(text_width + padding + 15)  # 약간의 추가 여유
            btn.setFixedHeight(22)  # 높이 축소

            # Size policy 설정으로 유연한 크기 조절
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, size=layout_size: self.set_layout(*size))
            layout.addWidget(btn, 0, Qt.AlignVCenter)
            self.layout_buttons[layout_size] = btn

        layout.addSpacing(20)

        # Fullscreen button with dynamic sizing
        fullscreen_btn = QPushButton("Fullscreen")

        # 폰트 설정
        font = fullscreen_btn.font()
        font.setPointSize(11)  # 폰트 크기를 11로 증가
        fullscreen_btn.setFont(font)

        # 텍스트 너비 계산
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance("Fullscreen") if hasattr(fm, 'horizontalAdvance') else fm.width("Fullscreen")
        fullscreen_btn.setMinimumWidth(text_width + 24)  # 여백도 증가
        fullscreen_btn.setFixedHeight(22)  # 높이 축소

        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        layout.addWidget(fullscreen_btn, 0, Qt.AlignVCenter)

        layout.addStretch()

        # Info label
        self.info_label = QLabel("Status: Ready")
        font = self.info_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.info_label.setFont(font)
        # Use theme from main window - no hardcoded color
        layout.addWidget(self.info_label, 0, Qt.AlignVCenter)

        controls.setLayout(layout)

        # Use theme from main window - no hardcoded button style

        return controls

    def _setup_context_menu(self):
        """Setup context menu for channels"""
        self.context_menu = QMenu(self)
        # Use theme from main window - no hardcoded style

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

        # Update layout
        self.current_layout = (rows, cols)
        self.info_label.setText(f"Grid: {rows}x{cols}")

        # Update layout button states
        if hasattr(self, 'layout_buttons'):
            for layout_size, btn in self.layout_buttons.items():
                btn.setChecked(layout_size == (rows, cols))

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