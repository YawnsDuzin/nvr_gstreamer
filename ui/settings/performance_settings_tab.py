"""
Performance Settings Tab
성능 모니터링 설정 탭
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QCheckBox, QSpinBox, QHBoxLayout
)
from PyQt5.QtCore import Qt
from loguru import logger

from core.config import ConfigManager
from .base_settings_tab import BaseSettingsTab


class PerformanceSettingsTab(BaseSettingsTab):
    """
    성능 모니터링 설정 탭
    - 알림 활성화/비활성화
    - CPU, 메모리, 온도 임계값 설정
    - 알림 체크 간격 설정
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(config_manager, parent)
        self._section_name = "performance"  # 이 탭이 관리하는 섹션
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # Alert Settings Group
        alert_group = QGroupBox("Alert Settings")
        alert_layout = QFormLayout()

        # Alert enabled
        self.alert_enabled_cb = QCheckBox("Enable Performance Alerts")
        self.alert_enabled_cb.setToolTip("Enable performance monitoring and alerts")
        alert_layout.addRow("Alerts:", self.alert_enabled_cb)

        # Alert intervals
        interval_layout = QHBoxLayout()

        # Warning interval
        self.warning_interval_spin = QSpinBox()
        self.warning_interval_spin.setRange(10, 300)  # 10초 ~ 5분
        self.warning_interval_spin.setSuffix(" seconds")
        self.warning_interval_spin.setToolTip("Check interval for warning alerts (10-300 seconds)")

        # Critical interval
        self.critical_interval_spin = QSpinBox()
        self.critical_interval_spin.setRange(5, 60)  # 5초 ~ 1분
        self.critical_interval_spin.setSuffix(" seconds")
        self.critical_interval_spin.setToolTip("Check interval for critical alerts (5-60 seconds)")

        interval_layout.addWidget(QLabel("Warning:"))
        interval_layout.addWidget(self.warning_interval_spin)
        interval_layout.addWidget(QLabel("Critical:"))
        interval_layout.addWidget(self.critical_interval_spin)
        interval_layout.addStretch()

        alert_layout.addRow("Check Intervals:", interval_layout)

        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)

        # Performance Thresholds Group
        threshold_group = QGroupBox("Performance Thresholds")
        threshold_layout = QFormLayout()

        # CPU threshold
        self.max_cpu_spin = QSpinBox()
        self.max_cpu_spin.setRange(10, 100)
        self.max_cpu_spin.setSuffix(" %")
        self.max_cpu_spin.setToolTip("Maximum CPU usage percentage before alert")
        threshold_layout.addRow("Max CPU:", self.max_cpu_spin)

        # Memory threshold
        self.max_memory_spin = QSpinBox()
        self.max_memory_spin.setRange(512, 16384)  # 512MB ~ 16GB
        self.max_memory_spin.setSingleStep(512)
        self.max_memory_spin.setSuffix(" MB")
        self.max_memory_spin.setToolTip("Maximum memory usage in MB before alert")
        threshold_layout.addRow("Max Memory:", self.max_memory_spin)

        # Temperature threshold
        self.max_temp_spin = QSpinBox()
        self.max_temp_spin.setRange(40, 100)
        self.max_temp_spin.setSuffix(" °C")
        self.max_temp_spin.setToolTip("Maximum temperature in Celsius before alert")
        threshold_layout.addRow("Max Temperature:", self.max_temp_spin)

        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)

        # Info label
        info_label = QLabel(
            "Note: Performance monitoring helps detect system resource issues.\n"
            "Alerts will be shown when thresholds are exceeded.\n"
            "Critical alerts check more frequently than warning alerts."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { color: #888; }")
        layout.addWidget(info_label)

        layout.addStretch()

        # Connect signals for validation
        self.warning_interval_spin.valueChanged.connect(self._validate_intervals)
        self.critical_interval_spin.valueChanged.connect(self._validate_intervals)

    def _validate_intervals(self):
        """간격 값 유효성 검사 - Critical이 Warning보다 작거나 같아야 함"""
        warning = self.warning_interval_spin.value()
        critical = self.critical_interval_spin.value()

        if critical > warning:
            # Critical이 Warning보다 크면 Warning 값으로 조정
            self.critical_interval_spin.setValue(min(critical, warning))

    def load_settings(self):
        """설정 로드"""
        config = self.config_manager.config
        performance = config.get('performance', {})

        # Alert settings
        self.alert_enabled_cb.setChecked(performance.get('alert_enabled', False))
        self.warning_interval_spin.setValue(
            performance.get('alert_warning_check_interval_seconds', 30)
        )
        self.critical_interval_spin.setValue(
            performance.get('alert_critical_check_interval_seconds', 15)
        )

        # Thresholds
        self.max_cpu_spin.setValue(performance.get('max_cpu_percent', 80))
        self.max_memory_spin.setValue(performance.get('max_memory_mb', 2048))
        self.max_temp_spin.setValue(performance.get('max_temp', 75))

        # Store original data
        self._store_original_data({
            'alert_enabled': performance.get('alert_enabled', False),
            'alert_warning_check_interval_seconds': performance.get('alert_warning_check_interval_seconds', 30),
            'alert_critical_check_interval_seconds': performance.get('alert_critical_check_interval_seconds', 15),
            'max_cpu_percent': performance.get('max_cpu_percent', 80),
            'max_memory_mb': performance.get('max_memory_mb', 2048),
            'max_temp': performance.get('max_temp', 75)
        })

        # 로드 완료 후 변경사항 플래그 초기화
        self.mark_as_saved()
        logger.debug("Performance settings loaded")

    def save_settings(self) -> bool:
        """설정 저장 (메모리에만)"""
        try:
            # config dict 업데이트
            performance_config = {
                'alert_enabled': self.alert_enabled_cb.isChecked(),
                'alert_warning_check_interval_seconds': self.warning_interval_spin.value(),
                'alert_critical_check_interval_seconds': self.critical_interval_spin.value(),
                'max_cpu_percent': self.max_cpu_spin.value(),
                'max_memory_mb': self.max_memory_spin.value(),
                'max_temp': self.max_temp_spin.value()
            }

            self.config_manager.config['performance'] = performance_config

            logger.debug("Performance settings saved to memory")
            return True

        except Exception as e:
            logger.error(f"Failed to save performance settings: {e}")
            return False

    def _save_section_to_db(self) -> bool:
        """performance 섹션을 DB에 저장"""
        try:
            # performance 데이터 준비
            performance_data = {
                'alert_enabled': self.alert_enabled_cb.isChecked(),
                'alert_warning_check_interval_seconds': self.warning_interval_spin.value(),
                'alert_critical_check_interval_seconds': self.critical_interval_spin.value(),
                'max_cpu_percent': self.max_cpu_spin.value(),
                'max_memory_mb': self.max_memory_spin.value(),
                'max_temp': self.max_temp_spin.value()
            }

            # DB에 저장
            self.config_manager.db_manager.save_performance_config(performance_data)
            logger.info("Performance settings saved to DB")
            return True
        except Exception as e:
            logger.error(f"Failed to save performance settings to DB: {e}")
            return False

    def _update_original_data(self):
        """현재 데이터를 원본으로 갱신"""
        self._store_original_data({
            'alert_enabled': self.alert_enabled_cb.isChecked(),
            'alert_warning_check_interval_seconds': self.warning_interval_spin.value(),
            'alert_critical_check_interval_seconds': self.critical_interval_spin.value(),
            'max_cpu_percent': self.max_cpu_spin.value(),
            'max_memory_mb': self.max_memory_spin.value(),
            'max_temp': self.max_temp_spin.value()
        })

    def validate_settings(self) -> tuple[bool, str]:
        """설정 유효성 검사"""
        # 간격 검증
        warning_interval = self.warning_interval_spin.value()
        critical_interval = self.critical_interval_spin.value()

        if critical_interval > warning_interval:
            return False, "Critical check interval must be less than or equal to warning interval"

        # CPU 검증
        cpu_percent = self.max_cpu_spin.value()
        if cpu_percent < 10 or cpu_percent > 100:
            return False, "CPU threshold must be between 10% and 100%"

        # Memory 검증
        memory_mb = self.max_memory_spin.value()
        if memory_mb < 512:
            return False, "Memory threshold must be at least 512 MB"

        # Temperature 검증
        temp = self.max_temp_spin.value()
        if temp < 40 or temp > 100:
            return False, "Temperature threshold must be between 40°C and 100°C"

        return True, ""

    def has_changes(self) -> bool:
        """변경사항 확인"""
        try:
            original = self._get_original_data()
            current = {
                'alert_enabled': self.alert_enabled_cb.isChecked(),
                'alert_warning_check_interval_seconds': self.warning_interval_spin.value(),
                'alert_critical_check_interval_seconds': self.critical_interval_spin.value(),
                'max_cpu_percent': self.max_cpu_spin.value(),
                'max_memory_mb': self.max_memory_spin.value(),
                'max_temp': self.max_temp_spin.value()
            }

            return original != current

        except Exception as e:
            logger.error(f"Failed to check changes: {e}")
            return False