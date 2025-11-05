"""
System Resource Monitoring Thread
Monitors CPU, memory, temperature, and disk usage with performance threshold alerts
"""

from PyQt5.QtCore import QThread, pyqtSignal
import psutil
import time
from loguru import logger

from core.config import ConfigManager
from core.enums import AlertLevel


class SystemMonitorThread(QThread):
    """시스템 리소스 모니터링 스레드 (성능 임계값 기반 경고 시스템 포함)"""

    # 상태 업데이트 시그널 (CPU, Memory, Temp, Disk)
    status_updated = pyqtSignal(float, float, float, float)

    # 경고 레벨 시그널 (AlertLevel, 메시지)
    alert_triggered = pyqtSignal(str, str)

    def __init__(self, update_interval: int = 5):
        """
        초기화

        Args:
            update_interval: 업데이트 주기 (초)
        """
        super().__init__()
        self.running = False
        self.update_interval = update_interval

        # ConfigManager에서 performance 설정 로드
        self.config_manager = ConfigManager.get_instance()
        self._load_performance_config()

        # 경고 상태 추적 (중복 경고 방지)
        self.last_alert_level = AlertLevel.NORMAL
        self.alert_counts = {
            'cpu': 0,
            'memory': 0,
            'temp': 0
        }

        # 마지막 경고 발생 시간 추적 (초 단위)
        self.last_alert_time = {
            AlertLevel.WARNING: 0,
            AlertLevel.CRITICAL: 0
        }

        logger.debug(
            f"SystemMonitorThread initialized with {update_interval}s interval\n"
            f"  Performance thresholds: "
            f"CPU={self.max_cpu_percent}%, "
            f"Memory={self.max_memory_mb}MB, "
            f"Temp={self.max_temp}°C\n"
            f"  Alert intervals: "
            f"WARNING={self.alert_warning_interval}s, "
            f"CRITICAL={self.alert_critical_interval}s"
        )

    def _load_performance_config(self):
        """performance 설정 로드"""
        try:
            config = self.config_manager.config
            perf_config = config.get('performance', {})

            # 경고 활성화 여부
            self.alert_enabled = perf_config.get('alert_enabled', True)

            # 경고 재발생 간격 (초)
            self.alert_warning_interval = perf_config.get('alert_warning_check_interval_seconds', 300)
            self.alert_critical_interval = perf_config.get('alert_critical_check_interval_seconds', 120)

            # 임계값 설정 (기본값 포함)
            self.max_cpu_percent = perf_config.get('max_cpu_percent', 80)
            self.max_memory_mb = perf_config.get('max_memory_mb', 2048)
            self.max_temp = perf_config.get('max_temp', 75)

            # 경고 임계값 (warning은 max의 80%, critical은 max의 100%)
            self.warning_cpu_percent = self.max_cpu_percent * 0.8
            self.warning_memory_mb = self.max_memory_mb * 0.8
            self.warning_temp = self.max_temp * 0.9  # 온도는 90%에서 경고

            logger.debug(
                f"Performance config loaded: "
                f"alert_enabled={self.alert_enabled}, "
                f"max_cpu={self.max_cpu_percent}%, "
                f"max_memory={self.max_memory_mb}MB, "
                f"max_temp={self.max_temp}°C, "
                f"warning_interval={self.alert_warning_interval}s, "
                f"critical_interval={self.alert_critical_interval}s"
            )

        except Exception as e:
            logger.error(f"Failed to load performance config: {e}")
            # 기본값 사용
            self.alert_enabled = True
            self.alert_warning_interval = 300
            self.alert_critical_interval = 120
            self.max_cpu_percent = 80
            self.max_memory_mb = 2048
            self.max_temp = 75
            self.warning_cpu_percent = 64
            self.warning_memory_mb = 1638
            self.warning_temp = 67.5

    def run(self):
        """주기적으로 시스템 상태 체크"""
        self.running = True
        logger.info("System monitoring thread started")

        while self.running:
            try:
                # CPU 사용률
                cpu_percent = psutil.cpu_percent(interval=1)

                # 메모리 사용량 (MB)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_mb = memory.used / (1024**2)  # MB 단위

                # 시스템 온도 (Raspberry Pi의 경우)
                temp = self._get_temperature()

                # 디스크 남은 공간 (GB)
                disk = psutil.disk_usage('/')
                disk_free_gb = disk.free / (1024**3)

                # 메인 스레드로 시그널 전송
                self.status_updated.emit(cpu_percent, memory_percent, temp, disk_free_gb)

                # 성능 임계값 체크 및 경고
                self._check_thresholds(cpu_percent, memory_mb, temp)

                logger.trace(
                    f"System status: CPU={cpu_percent:.1f}%, "
                    f"Memory={memory_percent:.1f}% ({memory_mb:.0f}MB), "
                    f"Temp={temp:.1f}°C, "
                    f"Disk={disk_free_gb:.1f}GB free"
                )

                # update_interval 초 대기 (100ms 단위로 체크하여 빠른 종료 가능)
                for _ in range(self.update_interval * 10):
                    if not self.running:
                        break
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"System monitor error: {e}")
                time.sleep(self.update_interval)

        logger.info("System monitoring thread stopped")

    def _check_thresholds(self, cpu_percent: float, memory_mb: float, temp: float):
        """
        임계값 체크 및 경고 발생

        Args:
            cpu_percent: CPU 사용률 (%)
            memory_mb: 메모리 사용량 (MB)
            temp: 온도 (°C)
        """
        alerts = []

        # CPU 체크
        if cpu_percent >= self.max_cpu_percent:
            self.alert_counts['cpu'] += 1
            alerts.append(('cpu', AlertLevel.CRITICAL,
                          f"CPU usage critical: {cpu_percent:.1f}% ≥ {self.max_cpu_percent}%"))
        elif cpu_percent >= self.warning_cpu_percent:
            alerts.append(('cpu', AlertLevel.WARNING,
                          f"CPU usage high: {cpu_percent:.1f}% (threshold: {self.max_cpu_percent}%)"))
            self.alert_counts['cpu'] = 0
        else:
            self.alert_counts['cpu'] = 0

        # 메모리 체크
        if memory_mb >= self.max_memory_mb:
            self.alert_counts['memory'] += 1
            alerts.append(('memory', AlertLevel.CRITICAL,
                          f"Memory usage critical: {memory_mb:.0f}MB ≥ {self.max_memory_mb}MB"))
        elif memory_mb >= self.warning_memory_mb:
            alerts.append(('memory', AlertLevel.WARNING,
                          f"Memory usage high: {memory_mb:.0f}MB (threshold: {self.max_memory_mb}MB)"))
            self.alert_counts['memory'] = 0
        else:
            self.alert_counts['memory'] = 0

        # 온도 체크 (온도 센서가 없으면 스킵)
        if temp > 0:
            if temp >= self.max_temp:
                self.alert_counts['temp'] += 1
                alerts.append(('temp', AlertLevel.CRITICAL,
                              f"Temperature critical: {temp:.1f}°C ≥ {self.max_temp}°C"))
            elif temp >= self.warning_temp:
                alerts.append(('temp', AlertLevel.WARNING,
                              f"Temperature high: {temp:.1f}°C (threshold: {self.max_temp}°C)"))
                self.alert_counts['temp'] = 0
            else:
                self.alert_counts['temp'] = 0

        # 경고 발생
        if alerts:
            # 경고가 비활성화되어 있으면 스킵
            if not self.alert_enabled:
                return

            # 가장 심각한 경고 레벨 결정
            max_level = AlertLevel.NORMAL
            for _, level, _ in alerts:
                if level == AlertLevel.CRITICAL:
                    max_level = AlertLevel.CRITICAL
                    break
                elif level == AlertLevel.WARNING and max_level == AlertLevel.NORMAL:
                    max_level = AlertLevel.WARNING

            # 경고 메시지 생성
            messages = [msg for _, _, msg in alerts]
            combined_message = "\n".join(messages)

            # 현재 시간
            current_time = time.time()

            # 경고 재발생 간격 체크
            should_alert = False

            if max_level != self.last_alert_level:
                # 경고 레벨이 변경된 경우 항상 알림
                should_alert = True
            else:
                # 동일 레벨인 경우 재발생 간격 체크
                last_time = self.last_alert_time.get(max_level, 0)
                interval = self.alert_critical_interval if max_level == AlertLevel.CRITICAL else self.alert_warning_interval

                if current_time - last_time >= interval:
                    should_alert = True

            # 경고 발생
            if should_alert:
                if max_level == AlertLevel.CRITICAL:
                    logger.critical(combined_message)
                elif max_level == AlertLevel.WARNING:
                    logger.warning(combined_message)

                # UI로 경고 시그널 전송
                self.alert_triggered.emit(max_level.value, combined_message)
                self.last_alert_level = max_level
                self.last_alert_time[max_level] = current_time

        else:
            # 모든 항목이 정상 범위로 돌아온 경우
            if self.last_alert_level != AlertLevel.NORMAL:
                logger.info("System resources returned to normal levels")
                self.alert_triggered.emit(AlertLevel.NORMAL.value, "System resources normal")
                self.last_alert_level = AlertLevel.NORMAL
                # 경고 시간 초기화
                self.last_alert_time[AlertLevel.WARNING] = 0
                self.last_alert_time[AlertLevel.CRITICAL] = 0

    def _get_temperature(self) -> float:
        """
        시스템 온도 가져오기

        Returns:
            온도 (섭씨), 온도를 가져올 수 없으면 0.0
        """
        try:
            # Raspberry Pi
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
                return temp
        except:
            # Windows/Linux - psutil 사용
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # 첫 번째 센서의 첫 번째 온도 값 사용
                    for name, entries in temps.items():
                        if entries:
                            return entries[0].current
            except AttributeError:
                # sensors_temperatures()가 지원되지 않는 플랫폼
                pass
            except Exception as e:
                logger.trace(f"Temperature sensor not available: {e}")

            return 0.0

    def stop(self):
        """스레드 종료"""
        logger.info("Stopping system monitoring thread...")
        self.running = False
        self.wait()
        logger.info("System monitoring thread stopped")