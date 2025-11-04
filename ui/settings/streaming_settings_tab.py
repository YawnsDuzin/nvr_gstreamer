"""
Streaming Settings Tab
스트리밍 설정 탭 (streaming 항목)
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QComboBox, QCheckBox, QSpinBox, QPushButton, QListWidget,
    QScrollArea, QWidget, QColorDialog
)
from PyQt5.QtGui import QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class ColorPickerButton(QPushButton):
    """색상 선택 버튼"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(255, 255, 255)
        self.clicked.connect(self._pick_color)
        self._update_style()

    def _pick_color(self):
        """색상 선택 다이얼로그"""
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_style()

    def _update_style(self):
        """버튼 스타일 업데이트 - 색상 아이콘과 텍스트 표시"""
        # 색상 사각형 아이콘 생성
        pixmap = QPixmap(16, 16)
        pixmap.fill(self._color)
        icon = QIcon(pixmap)

        # 아이콘 설정
        self.setIcon(icon)
        self.setIconSize(pixmap.size())

        # 텍스트는 색상 코드 표시
        self.setText(self._color.name().upper())

        # 기본 버튼 스타일 유지 (테마 시스템이 적용됨)
        self.setMinimumWidth(100)
        self.setMinimumHeight(30)

    def get_color(self) -> list:
        """RGB 리스트 반환"""
        return [self._color.red(), self._color.green(), self._color.blue()]

    def set_color(self, rgb: list):
        """RGB 리스트로 색상 설정"""
        if len(rgb) >= 3:
            self._color = QColor(rgb[0], rgb[1], rgb[2])
            self._update_style()


class StreamingSettingsTab(BaseSettingsTab):
    """
    스트리밍 설정 탭
    - 레이아웃 설정
    - OSD 설정
    - 하드웨어 가속
    - 네트워크 및 버퍼링
    - 자동 재연결
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        # 스크롤 가능하게 설정
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # Display Layout Group
        layout_group = QGroupBox("Display Layout")
        layout_form = QFormLayout()

        self.default_layout_combo = QComboBox()
        self.default_layout_combo.addItems(["1x1", "2x2", "3x3", "4x4"])
        self.default_layout_combo.setToolTip("Default camera grid layout")
        layout_form.addRow("Default Layout:", self.default_layout_combo)

        layout_group.setLayout(layout_form)
        layout.addWidget(layout_group)

        # OSD Group
        osd_group = QGroupBox("OSD (On-Screen Display)")
        osd_form = QFormLayout()

        self.show_timestamp_cb = QCheckBox("Show Timestamp")
        osd_form.addRow(self.show_timestamp_cb)

        self.show_camera_name_cb = QCheckBox("Show Camera Name")
        osd_form.addRow(self.show_camera_name_cb)

        self.osd_font_size_spin = QSpinBox()
        self.osd_font_size_spin.setRange(8, 48)
        self.osd_font_size_spin.setSuffix(" px")
        osd_form.addRow("Font Size:", self.osd_font_size_spin)

        self.osd_font_color_btn = ColorPickerButton()
        osd_form.addRow("Font Color:", self.osd_font_color_btn)

        self.osd_valignment_combo = QComboBox()
        self.osd_valignment_combo.addItems(["top", "center", "bottom"])
        osd_form.addRow("Vertical Alignment:", self.osd_valignment_combo)

        self.osd_halignment_combo = QComboBox()
        self.osd_halignment_combo.addItems(["left", "center", "right"])
        osd_form.addRow("Horizontal Alignment:", self.osd_halignment_combo)

        self.osd_xpad_spin = QSpinBox()
        self.osd_xpad_spin.setRange(0, 200)
        self.osd_xpad_spin.setSuffix(" px")
        osd_form.addRow("Horizontal Padding:", self.osd_xpad_spin)

        self.osd_ypad_spin = QSpinBox()
        self.osd_ypad_spin.setRange(0, 200)
        self.osd_ypad_spin.setSuffix(" px")
        osd_form.addRow("Vertical Padding:", self.osd_ypad_spin)

        osd_group.setLayout(osd_form)
        layout.addWidget(osd_group)

        # Hardware Acceleration Group
        hw_group = QGroupBox("Hardware Acceleration")
        hw_layout = QVBoxLayout()

        self.use_hw_accel_cb = QCheckBox("Use Hardware Acceleration")
        self.use_hw_accel_cb.setToolTip(
            "Enable hardware-accelerated video decoding (if available)"
        )
        hw_layout.addWidget(self.use_hw_accel_cb)

        hw_layout.addWidget(QLabel("Decoder Preference (drag to reorder):"))
        self.decoder_list = QListWidget()
        self.decoder_list.setToolTip(
            "Priority order for video decoders.\n"
            "System will try each decoder from top to bottom."
        )
        self.decoder_list.setMaximumHeight(100)
        self.decoder_list.setDragDropMode(QListWidget.InternalMove)
        hw_layout.addWidget(self.decoder_list)

        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)

        # Network & Buffering Group
        network_group = QGroupBox("Network & Buffering")
        network_form = QFormLayout()

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(1024, 104857600)  # 1KB ~ 100MB
        self.buffer_size_spin.setSingleStep(1048576)  # 1MB
        self.buffer_size_spin.setSuffix(" bytes")
        self.buffer_size_spin.setToolTip("Buffer size for video stream")
        network_form.addRow("Buffer Size:", self.buffer_size_spin)

        self.latency_spin = QSpinBox()
        self.latency_spin.setRange(0, 10000)
        self.latency_spin.setSingleStep(50)
        self.latency_spin.setSuffix(" ms")
        self.latency_spin.setToolTip("Maximum latency allowed")
        network_form.addRow("Latency:", self.latency_spin)

        self.tcp_timeout_spin = QSpinBox()
        self.tcp_timeout_spin.setRange(1000, 60000)
        self.tcp_timeout_spin.setSingleStep(1000)
        self.tcp_timeout_spin.setSuffix(" ms")
        self.tcp_timeout_spin.setToolTip("TCP connection timeout")
        network_form.addRow("TCP Timeout:", self.tcp_timeout_spin)

        self.connection_timeout_spin = QSpinBox()
        self.connection_timeout_spin.setRange(1, 300)
        self.connection_timeout_spin.setSuffix(" sec")
        self.connection_timeout_spin.setToolTip("Initial connection timeout")
        network_form.addRow("Connection Timeout:", self.connection_timeout_spin)

        network_group.setLayout(network_form)
        layout.addWidget(network_group)

        # Auto Reconnection Group
        reconnect_group = QGroupBox("Auto Reconnection")
        reconnect_form = QFormLayout()

        self.auto_reconnect_cb = QCheckBox("Enable Auto Reconnection")
        self.auto_reconnect_cb.setToolTip("Automatically reconnect on connection loss")
        self.auto_reconnect_cb.toggled.connect(self._on_auto_reconnect_toggled)
        reconnect_form.addRow(self.auto_reconnect_cb)

        self.max_reconnect_spin = QSpinBox()
        self.max_reconnect_spin.setRange(1, 100)
        self.max_reconnect_spin.setToolTip("Maximum number of reconnection attempts")
        reconnect_form.addRow("Max Attempts:", self.max_reconnect_spin)

        self.reconnect_delay_spin = QSpinBox()
        self.reconnect_delay_spin.setRange(1, 300)
        self.reconnect_delay_spin.setSuffix(" sec")
        self.reconnect_delay_spin.setToolTip("Delay between reconnection attempts")
        reconnect_form.addRow("Retry Delay:", self.reconnect_delay_spin)

        reconnect_group.setLayout(reconnect_form)
        layout.addWidget(reconnect_group)

        layout.addStretch()

        scroll.setWidget(scroll_content)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        logger.debug("StreamingSettingsTab UI setup complete")

    def _on_auto_reconnect_toggled(self, checked: bool):
        """자동 재연결 토글 시 관련 위젯 활성화/비활성화"""
        self.max_reconnect_spin.setEnabled(checked)
        self.reconnect_delay_spin.setEnabled(checked)

    def load_settings(self):
        """설정 로드"""
        try:
            config = self.config_manager.config
            streaming = config.get("streaming", {})

            # Default layout
            layout = streaming.get("default_layout", "1x1")
            idx = self.default_layout_combo.findText(layout)
            if idx >= 0:
                self.default_layout_combo.setCurrentIndex(idx)

            # OSD
            self.show_timestamp_cb.setChecked(streaming.get("show_timestamp", True))
            self.show_camera_name_cb.setChecked(streaming.get("show_camera_name", True))
            self.osd_font_size_spin.setValue(streaming.get("osd_font_size", 14))

            osd_color = streaming.get("osd_font_color", [255, 255, 255])
            self.osd_font_color_btn.set_color(osd_color)

            valign = streaming.get("osd_valignment", "top")
            idx = self.osd_valignment_combo.findText(valign)
            if idx >= 0:
                self.osd_valignment_combo.setCurrentIndex(idx)

            halign = streaming.get("osd_halignment", "left")
            idx = self.osd_halignment_combo.findText(halign)
            if idx >= 0:
                self.osd_halignment_combo.setCurrentIndex(idx)

            self.osd_xpad_spin.setValue(streaming.get("osd_xpad", 20))
            self.osd_ypad_spin.setValue(streaming.get("osd_ypad", 15))

            # Hardware acceleration
            self.use_hw_accel_cb.setChecked(streaming.get("use_hardware_acceleration", True))

            decoder_pref = streaming.get("decoder_preference", ["v4l2h264dec", "omxh264dec", "avdec_h264"])
            self.decoder_list.clear()
            self.decoder_list.addItems(decoder_pref)

            # Network & buffering
            self.buffer_size_spin.setValue(streaming.get("buffer_size", 10485760))
            self.latency_spin.setValue(streaming.get("latency_ms", 200))
            self.tcp_timeout_spin.setValue(streaming.get("tcp_timeout", 10000))
            self.connection_timeout_spin.setValue(streaming.get("connection_timeout", 10))

            # Auto reconnection
            auto_reconnect = streaming.get("auto_reconnect", True)
            self.auto_reconnect_cb.setChecked(auto_reconnect)
            self.max_reconnect_spin.setValue(streaming.get("max_reconnect_attempts", 5))
            self.reconnect_delay_spin.setValue(streaming.get("reconnect_delay_seconds", 5))

            # Enable/disable reconnection fields
            self._on_auto_reconnect_toggled(auto_reconnect)

            # Store original data
            self._store_original_data({
                "default_layout": layout,
                "show_timestamp": streaming.get("show_timestamp", True),
                "show_camera_name": streaming.get("show_camera_name", True),
                "osd_font_size": streaming.get("osd_font_size", 14),
                "osd_font_color": osd_color,
                "osd_valignment": valign,
                "osd_halignment": halign,
                "osd_xpad": streaming.get("osd_xpad", 20),
                "osd_ypad": streaming.get("osd_ypad", 15),
                "use_hardware_acceleration": streaming.get("use_hardware_acceleration", True),
                "decoder_preference": decoder_pref,
                "buffer_size": streaming.get("buffer_size", 10485760),
                "latency_ms": streaming.get("latency_ms", 200),
                "tcp_timeout": streaming.get("tcp_timeout", 10000),
                "connection_timeout": streaming.get("connection_timeout", 10),
                "auto_reconnect": auto_reconnect,
                "max_reconnect_attempts": streaming.get("max_reconnect_attempts", 5),
                "reconnect_delay_seconds": streaming.get("reconnect_delay_seconds", 5),
            })

            logger.debug("StreamingSettingsTab settings loaded")

        except Exception as e:
            logger.error(f"Failed to load streaming settings: {e}")

    def save_settings(self) -> bool:
        """설정 저장"""
        try:
            config = self.config_manager.config

            if "streaming" not in config:
                config["streaming"] = {}

            # Update settings
            config["streaming"]["default_layout"] = self.default_layout_combo.currentText()
            config["streaming"]["show_timestamp"] = self.show_timestamp_cb.isChecked()
            config["streaming"]["show_camera_name"] = self.show_camera_name_cb.isChecked()
            config["streaming"]["osd_font_size"] = self.osd_font_size_spin.value()
            config["streaming"]["osd_font_color"] = self.osd_font_color_btn.get_color()
            config["streaming"]["osd_valignment"] = self.osd_valignment_combo.currentText()
            config["streaming"]["osd_halignment"] = self.osd_halignment_combo.currentText()
            config["streaming"]["osd_xpad"] = self.osd_xpad_spin.value()
            config["streaming"]["osd_ypad"] = self.osd_ypad_spin.value()

            config["streaming"]["use_hardware_acceleration"] = self.use_hw_accel_cb.isChecked()

            # Decoder preference (get order from list)
            decoder_pref = []
            for i in range(self.decoder_list.count()):
                decoder_pref.append(self.decoder_list.item(i).text())
            config["streaming"]["decoder_preference"] = decoder_pref

            config["streaming"]["buffer_size"] = self.buffer_size_spin.value()
            config["streaming"]["latency_ms"] = self.latency_spin.value()
            config["streaming"]["tcp_timeout"] = self.tcp_timeout_spin.value()
            config["streaming"]["connection_timeout"] = self.connection_timeout_spin.value()

            config["streaming"]["auto_reconnect"] = self.auto_reconnect_cb.isChecked()
            config["streaming"]["max_reconnect_attempts"] = self.max_reconnect_spin.value()
            config["streaming"]["reconnect_delay_seconds"] = self.reconnect_delay_spin.value()

            self.config_manager.save_config()

            logger.info("Streaming settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save streaming settings: {e}")
            return False

    def validate_settings(self) -> tuple[bool, str]:
        """설정 검증"""
        # Buffer size validation
        buffer_size = self.buffer_size_spin.value()
        if buffer_size < 1024:
            return False, "Buffer size must be at least 1024 bytes"

        # Decoder preference validation (at least one decoder)
        if self.decoder_list.count() == 0:
            return False, "At least one decoder must be specified"

        return True, ""

    def has_changes(self) -> bool:
        """변경 사항이 있는지 확인"""
        try:
            original = self._get_original_data()

            # Get current decoder preference
            decoder_pref = []
            for i in range(self.decoder_list.count()):
                decoder_pref.append(self.decoder_list.item(i).text())

            current = {
                "default_layout": self.default_layout_combo.currentText(),
                "show_timestamp": self.show_timestamp_cb.isChecked(),
                "show_camera_name": self.show_camera_name_cb.isChecked(),
                "osd_font_size": self.osd_font_size_spin.value(),
                "osd_font_color": self.osd_font_color_btn.get_color(),
                "osd_valignment": self.osd_valignment_combo.currentText(),
                "osd_halignment": self.osd_halignment_combo.currentText(),
                "osd_xpad": self.osd_xpad_spin.value(),
                "osd_ypad": self.osd_ypad_spin.value(),
                "use_hardware_acceleration": self.use_hw_accel_cb.isChecked(),
                "decoder_preference": decoder_pref,
                "buffer_size": self.buffer_size_spin.value(),
                "latency_ms": self.latency_spin.value(),
                "tcp_timeout": self.tcp_timeout_spin.value(),
                "connection_timeout": self.connection_timeout_spin.value(),
                "auto_reconnect": self.auto_reconnect_cb.isChecked(),
                "max_reconnect_attempts": self.max_reconnect_spin.value(),
                "reconnect_delay_seconds": self.reconnect_delay_spin.value(),
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False
