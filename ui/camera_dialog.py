"""
Camera Configuration Dialog
UI for adding and editing camera settings
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QGroupBox, QDialogButtonBox,
    QMessageBox, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import re

# Fix imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streaming.camera_stream import CameraConfig


class CameraDialog(QDialog):
    """Dialog for camera configuration"""

    # Signal emitted when camera is saved
    camera_saved = pyqtSignal(CameraConfig)

    def __init__(self, camera_config=None, parent=None):
        """
        Initialize camera dialog

        Args:
            camera_config: Existing camera configuration to edit
            parent: Parent widget
        """
        super().__init__(parent)
        self.camera_config = camera_config
        self.is_edit_mode = camera_config is not None

        self._setup_ui()

        # Load existing configuration if editing
        if self.is_edit_mode:
            self._load_camera_config()

    def _setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("Edit Camera" if self.is_edit_mode else "Add Camera")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        # Basic Settings Group
        basic_group = QGroupBox("Basic Settings")
        basic_layout = QGridLayout()

        # Camera Name
        basic_layout.addWidget(QLabel("Camera Name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Front Door")
        basic_layout.addWidget(self.name_edit, 0, 1)

        # Camera ID
        basic_layout.addWidget(QLabel("Camera ID:"), 1, 0)
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g., cam_01")
        if self.is_edit_mode:
            self.id_edit.setEnabled(False)  # Can't change ID when editing
        basic_layout.addWidget(self.id_edit, 1, 1)

        # RTSP URL
        basic_layout.addWidget(QLabel("RTSP URL:"), 2, 0)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("rtsp://192.168.1.100:554/stream")
        basic_layout.addWidget(self.url_edit, 2, 1)

        # Test Connection Button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        basic_layout.addWidget(self.test_btn, 2, 2)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # Authentication Group
        auth_group = QGroupBox("Authentication (Optional)")
        auth_layout = QGridLayout()

        auth_layout.addWidget(QLabel("Username:"), 0, 0)
        self.username_edit = QLineEdit()
        auth_layout.addWidget(self.username_edit, 0, 1)

        auth_layout.addWidget(QLabel("Password:"), 1, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        auth_layout.addWidget(self.password_edit, 1, 1)

        # Show/Hide password checkbox
        self.show_password_cb = QCheckBox("Show Password")
        self.show_password_cb.toggled.connect(self._toggle_password_visibility)
        auth_layout.addWidget(self.show_password_cb, 1, 2)

        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Advanced Settings Group
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QGridLayout()

        # Hardware Decode
        self.hardware_decode_cb = QCheckBox("Use Hardware Decoding")
        self.hardware_decode_cb.setToolTip("Enable hardware acceleration (Raspberry Pi OMX)")
        advanced_layout.addWidget(self.hardware_decode_cb, 0, 0, 1, 2)

        # Recording
        self.recording_cb = QCheckBox("Enable Recording")
        advanced_layout.addWidget(self.recording_cb, 1, 0, 1, 2)

        # Motion Detection
        self.motion_detection_cb = QCheckBox("Enable Motion Detection")
        advanced_layout.addWidget(self.motion_detection_cb, 2, 0, 1, 2)

        # Reconnect Settings
        advanced_layout.addWidget(QLabel("Reconnect Attempts:"), 3, 0)
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(0, 10)
        self.reconnect_spin.setValue(3)
        advanced_layout.addWidget(self.reconnect_spin, 3, 1)

        advanced_layout.addWidget(QLabel("Reconnect Delay (sec):"), 4, 0)
        self.reconnect_delay_spin = QSpinBox()
        self.reconnect_delay_spin.setRange(1, 60)
        self.reconnect_delay_spin.setValue(5)
        advanced_layout.addWidget(self.reconnect_delay_spin, 4, 1)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Enable Camera Checkbox
        self.enabled_cb = QCheckBox("Enable Camera")
        self.enabled_cb.setChecked(True)
        layout.addWidget(self.enabled_cb)

        # Dialog Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self
        )
        buttons.accepted.connect(self._save_camera)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Apply dark theme
        self._apply_theme()

    def _apply_theme(self):
        """Apply dark theme to dialog"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLineEdit {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                padding: 5px;
                border-radius: 3px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #5a5a5a;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                padding: 5px 15px;
                border-radius: 3px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QCheckBox {
                color: #ffffff;
            }
            QSpinBox {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                padding: 3px;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
        """)

    def _load_camera_config(self):
        """Load existing camera configuration"""
        if not self.camera_config:
            return

        self.id_edit.setText(self.camera_config.camera_id)
        self.name_edit.setText(self.camera_config.name)
        self.url_edit.setText(self.camera_config.rtsp_url)

        if self.camera_config.username:
            self.username_edit.setText(self.camera_config.username)
        if self.camera_config.password:
            self.password_edit.setText(self.camera_config.password)

        self.hardware_decode_cb.setChecked(self.camera_config.use_hardware_decode)
        self.reconnect_spin.setValue(self.camera_config.reconnect_attempts)
        self.reconnect_delay_spin.setValue(self.camera_config.reconnect_delay)

        # Load additional settings if they exist
        if hasattr(self.camera_config, 'enabled'):
            self.enabled_cb.setChecked(self.camera_config.enabled)
        if hasattr(self.camera_config, 'recording_enabled'):
            self.recording_cb.setChecked(self.camera_config.recording_enabled)
        if hasattr(self.camera_config, 'motion_detection'):
            self.motion_detection_cb.setChecked(self.camera_config.motion_detection)

    def _toggle_password_visibility(self, checked):
        """Toggle password field visibility"""
        if checked:
            self.password_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)

    def _validate_inputs(self):
        """
        Validate input fields

        Returns:
            True if all inputs are valid
        """
        # Check required fields
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Camera name is required")
            return False

        if not self.id_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Camera ID is required")
            return False

        # Validate camera ID format (alphanumeric and underscore only)
        camera_id = self.id_edit.text().strip()
        if not re.match(r'^[a-zA-Z0-9_]+$', camera_id):
            QMessageBox.warning(self, "Validation Error",
                               "Camera ID must contain only letters, numbers, and underscores")
            return False

        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "RTSP URL is required")
            return False

        # Basic RTSP URL validation
        url = self.url_edit.text().strip()
        if not url.startswith('rtsp://'):
            QMessageBox.warning(self, "Validation Error",
                               "RTSP URL must start with 'rtsp://'")
            return False

        return True

    def _save_camera(self):
        """Save camera configuration"""
        if not self._validate_inputs():
            return

        # Create camera configuration
        config = CameraConfig(
            camera_id=self.id_edit.text().strip(),
            name=self.name_edit.text().strip(),
            rtsp_url=self.url_edit.text().strip(),
            username=self.username_edit.text().strip() or None,
            password=self.password_edit.text().strip() or None,
            use_hardware_decode=self.hardware_decode_cb.isChecked(),
            reconnect_attempts=self.reconnect_spin.value(),
            reconnect_delay=self.reconnect_delay_spin.value()
        )

        # Add additional attributes
        config.enabled = self.enabled_cb.isChecked()
        config.recording_enabled = self.recording_cb.isChecked()
        config.motion_detection = self.motion_detection_cb.isChecked()

        # Emit signal with configuration
        self.camera_saved.emit(config)

        # Accept dialog
        self.accept()

    def _test_connection(self):
        """Test camera connection"""
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Test Connection", "Please enter an RTSP URL")
            return

        # Build URL with credentials if provided
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if username and password:
            # Parse and insert credentials
            url_parts = url.split("://")
            if len(url_parts) == 2:
                protocol = url_parts[0]
                rest = url_parts[1]
                test_url = f"{protocol}://{username}:{password}@{rest}"
            else:
                test_url = url
        else:
            test_url = url

        # Show testing message
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")

        try:
            # Import and test with UnifiedPipeline
            from streaming.pipeline_manager import PipelineManager
            from streaming.unified_pipeline import PipelineMode

            # Create pipeline manager with unified pipeline
            pipeline = PipelineManager(
                rtsp_url=test_url,
                camera_id="test",
                camera_name="Test Camera"
            )

            # Create unified pipeline in streaming mode
            if pipeline.create_unified_pipeline(mode=PipelineMode.STREAMING_ONLY):
                # Start pipeline
                if pipeline.start():
                    # Wait briefly to check if connection works
                    import time
                    time.sleep(2)

                    # Check if pipeline is playing
                    # 테스트 모드에서는 video sink 에러를 무시하고 연결 상태만 확인
                    if pipeline.is_playing():
                        QMessageBox.information(self, "Test Connection",
                                              "Connection successful!\n\nRTSP stream is accessible.")
                    else:
                        QMessageBox.warning(self, "Test Connection",
                                           "Connection failed. Please check URL and credentials.")
                else:
                    QMessageBox.warning(self, "Test Connection",
                                       "Failed to start stream. Check URL and network.")

                # Clean up (에러가 있어도 정리)
                try:
                    pipeline.stop()
                except:
                    pass
            else:
                QMessageBox.warning(self, "Test Connection",
                                   "Failed to create pipeline. Check GStreamer installation.")

        except Exception as e:
            QMessageBox.critical(self, "Test Connection",
                                f"Connection test failed:\n{str(e)}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")

    def get_camera_config(self):
        """
        Get the camera configuration

        Returns:
            CameraConfig object or None
        """
        if self.result() == QDialog.Accepted:
            return self.camera_config
        return None

    def get_camera_info(self):
        """
        Get camera information as dictionary (for backward compatibility)

        Returns:
            Dictionary with camera information
        """
        if self.result() == QDialog.Accepted and self.camera_config:
            return {
                'id': self.camera_config.camera_id,
                'name': self.camera_config.name,
                'url': self.camera_config.rtsp_url,
                'username': self.camera_config.username,
                'password': self.camera_config.password,
                'auto_record': getattr(self.camera_config, 'recording_enabled', False),
                'enabled': getattr(self.camera_config, 'enabled', True)
            }
        return None