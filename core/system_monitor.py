"""
System Resource Monitoring Thread
Monitors CPU, memory, temperature, and disk usage
"""

from PyQt5.QtCore import QThread, pyqtSignal
import psutil
import time
from loguru import logger


class SystemMonitorThread(QThread):
    """시스템 리소스 모니터링 스레드"""

    # 상태 업데이트 시그널 (CPU, Memory, Temp, Disk)
    status_updated = pyqtSignal(float, float, float, float)

    def __init__(self, update_interval: int = 5):
        """
        초기화

        Args:
            update_interval: 업데이트 주기 (초)
        """
        super().__init__()
        self.running = False
        self.update_interval = update_interval
        logger.debug(f"SystemMonitorThread initialized with {update_interval}s interval")

    def run(self):
        """주기적으로 시스템 상태 체크"""
        self.running = True
        logger.info("System monitoring thread started")

        while self.running:
            try:
                # CPU 사용률
                cpu_percent = psutil.cpu_percent(interval=1)

                # 메모리 사용률
                memory = psutil.virtual_memory()
                memory_percent = memory.percent

                # 시스템 온도 (Raspberry Pi의 경우)
                temp = self._get_temperature()

                # 디스크 남은 공간 (GB)
                disk = psutil.disk_usage('/')
                disk_free_gb = disk.free / (1024**3)

                # 메인 스레드로 시그널 전송
                self.status_updated.emit(cpu_percent, memory_percent, temp, disk_free_gb)

                logger.trace(
                    f"System status: CPU={cpu_percent:.1f}%, "
                    f"Memory={memory_percent:.1f}%, "
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