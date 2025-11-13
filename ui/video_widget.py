"""
Video Widget for displaying GStreamer streams in PyQt5
"""

import sys
import platform
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from loguru import logger

# Platform-specific imports for video rendering
if platform.system() == "Linux":
    from PyQt5.QtWidgets import QWidget as VideoWidget
else:
    # For Windows/Mac development
    from PyQt5.QtWidgets import QWidget as VideoWidget


class StreamVideoWidget(QWidget):
    """Widget for displaying video stream"""

    # Signals
    stream_connected = pyqtSignal(str)
    stream_disconnected = pyqtSignal(str)
    stream_error = pyqtSignal(str, str)

    def __init__(self, camera_id: str = "", camera_name: str = "Camera", parent=None):
        """
        Initialize video widget

        Args:
            camera_id: Camera identifier
            camera_name: Display name for camera
            parent: Parent widget
        """
        super().__init__(parent)
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.video_widget = None
        self.window_id = None
        self.is_connected = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Header with camera name
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 2, 5, 2)

        self.name_label = QLabel(self.camera_name)
        self.name_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: transparent;
                padding: 3px;
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()

        # Streaming status indicator
        self.streaming_status_label = QLabel("● Disconnected")
        self.streaming_status_label.setStyleSheet("""
            QLabel {
                color: #ff4444;
                background-color: transparent;
                padding: 3px;
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(self.streaming_status_label)

        # Recording status indicator
        self.recording_status_label = QLabel("⚫ Stop")
        self.recording_status_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                background-color: transparent;
                padding: 3px;
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(self.recording_status_label)

        # Video display area
        self.video_widget = VideoWidget()
        self.video_widget.setStyleSheet("background-color: black;")

        # Set minimum size for video widget
        self.video_widget.setMinimumSize(320, 240)

        # Placeholder for when stream is not connected
        self.placeholder_label = QLabel("No Signal")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("""
            QLabel {
                color: #666666;
                background-color: black;
                font-size: 18px;
            }
        """)

        # Add widgets to layout
        layout.addLayout(header_layout)
        layout.addWidget(self.video_widget, 1)  # Video widget takes all available space

        self.setLayout(layout)

        # Apply dark theme
        self._apply_theme()

    def _apply_theme(self):
        """Apply dark theme to widget"""
        self.setStyleSheet("""
            StreamVideoWidget {
                background-color: #1a1a1a;
                border: 1px solid #333333;
            }
        """)

    def get_window_handle(self):
        """
        Get window handle for GStreamer rendering

        Returns:
            Window ID/handle for video rendering
        """
        if platform.system() == "Linux":
            # X11 window ID
            return self.video_widget.winId()
        elif platform.system() == "Windows":
            # Windows HWND
            return int(self.video_widget.winId())
        elif platform.system() == "Darwin":
            # macOS NSView
            return int(self.video_widget.winId())
        else:
            logger.warning(f"Unsupported platform: {platform.system()}")
            return None

    def set_connected(self, connected: bool):
        """
        Update connection status

        Args:
            connected: Connection status
        """
        self.is_connected = connected

        if connected:
            self.streaming_status_label.setText("● Connected")
            self.streaming_status_label.setStyleSheet("""
                QLabel {
                    color: #44ff44;
                    background-color: rgba(0, 0, 0, 128);
                    padding: 3px;
                    border-radius: 3px;
                }
            """)
            self.stream_connected.emit(self.camera_id)
        else:
            self.streaming_status_label.setText("● Disconnected")
            self.streaming_status_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;
                    background-color: rgba(0, 0, 0, 128);
                    padding: 3px;
                    border-radius: 3px;
                }
            """)
            self.stream_disconnected.emit(self.camera_id)

    def set_error(self, error_message: str):
        """
        Set error status

        Args:
            error_message: Error description
        """
        self.streaming_status_label.setText("● Error")
        self.streaming_status_label.setStyleSheet("""
            QLabel {
                color: #ffaa00;
                background-color: rgba(0, 0, 0, 128);
                padding: 3px;
                border-radius: 3px;
            }
        """)
        self.stream_error.emit(self.camera_id, error_message)

    def update_camera_info(self, camera_id: str, camera_name: str):
        """
        Update camera information

        Args:
            camera_id: Camera identifier
            camera_name: Display name
        """
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.name_label.setText(f"{camera_name} ({camera_id})")

    def set_recording(self, recording: bool):
        """
        Set recording state

        Args:
            recording: Recording state
        """
        if recording:
            self.recording_status_label.setText("● Rec")
            self.recording_status_label.setStyleSheet("""
                QLabel {
                    color: #ff0000;
                    background-color: rgba(0, 0, 0, 128);
                    padding: 3px;
                    border-radius: 3px;
                    font-weight: bold;
                }
            """)
        else:
            self.recording_status_label.setText("● Stop")
            self.recording_status_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;
                    background-color: rgba(0, 0, 0, 128);
                    padding: 3px;
                    border-radius: 3px;
                }
            """)

    def clear_video(self):
        """Clear video display"""
        # Reset video widget to black
        if self.video_widget:
            self.video_widget.update()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        # Notify that widget has been resized if needed
        logger.debug(f"Video widget resized: {self.size()}")


class MultiStreamWidget(QWidget):
    """Widget for displaying multiple video streams in a grid"""

    def __init__(self, rows: int = 2, cols: int = 2, parent=None):
        """
        Initialize multi-stream widget

        Args:
            rows: Number of rows in grid
            cols: Number of columns in grid
            parent: Parent widget
        """
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.video_widgets = []

        self._setup_ui()

    def _setup_ui(self):
        """Setup grid layout with video widgets"""
        from PyQt5.QtWidgets import QGridLayout

        layout = QGridLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Create video widgets in grid
        widget_index = 0
        for row in range(self.rows):
            for col in range(self.cols):
                camera_name = f"Camera {widget_index + 1}"
                video_widget = StreamVideoWidget(
                    camera_id=f"cam_{widget_index}",
                    camera_name=camera_name
                )
                layout.addWidget(video_widget, row, col)
                self.video_widgets.append(video_widget)
                widget_index += 1

        self.setLayout(layout)

        # Apply dark background
        self.setStyleSheet("background-color: #0a0a0a;")

    def get_video_widget(self, index: int) -> StreamVideoWidget:
        """
        Get video widget by index

        Args:
            index: Widget index

        Returns:
            Video widget or None
        """
        if 0 <= index < len(self.video_widgets):
            return self.video_widgets[index]
        return None

    def update_layout(self, rows: int, cols: int):
        """
        Update grid layout

        Args:
            rows: New number of rows
            cols: New number of columns
        """
        # Clear existing widgets
        for widget in self.video_widgets:
            widget.deleteLater()
        self.video_widgets.clear()

        # Update dimensions
        self.rows = rows
        self.cols = cols

        # Recreate layout
        self._setup_ui()