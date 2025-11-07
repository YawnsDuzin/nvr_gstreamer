"""
Enhanced Main Window with 4-channel grid view
Integrates camera list, grid view, and configuration management
"""

import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QAction,
    QMessageBox, QDockWidget, QLabel, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QDateTime, QEvent
from PyQt5.QtGui import QKeySequence, QCloseEvent
from loguru import logger

# Fix imports with full paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.grid_view import GridViewWidget
from ui.camera_list_widget import CameraListWidget
from ui.camera_dialog import CameraDialog
from ui.recording_control_widget import RecordingControlWidget
from ui.playback_widget import PlaybackWidget
from ui.theme import ThemeManager
from core.config import ConfigManager
from core.storage import StorageService
from core.system_monitor import SystemMonitorThread
from camera.streaming import CameraStream
from camera.playback import PlaybackManager
from camera.ptz_controller import PTZController


class MainWindow(QMainWindow):
    """Main application window with camera grid view"""

    def __init__(self):
        super().__init__()
        # Get singleton instance
        self.config_manager = ConfigManager.get_instance()
        self.playback_manager = PlaybackManager()

        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Initialize core services
        self.storage_service = StorageService()

        self.grid_view = None
        self.camera_list = None
        self.recording_control = None
        self.playback_widget = None
        self.is_playback_mode = False

        # Get app name and version from config
        self.app_name = self.config_manager.app_config.app_name
        self.app_version = self.config_manager.app_config.version
        self.app_display_name = f"{self.app_name}/{self.app_version}"

        self.monitor_thread = None

        # 전체화면 자동 UI 숨김/표시 기능 관련 변수
        self.ui_hide_timer = None
        self.ui_hidden = False
        self.last_activity_time = QDateTime.currentDateTime()

        # PTZ 제어 관련 변수
        self.ptz_controller = None
        self.ptz_speed = 5  # 기본 PTZ 속도 (1-9)
        self.ptz_keys = {}  # PTZ 키 설정

        # 메뉴 키 설정
        self.menu_keys = {}  # 메뉴 단축키 설정

        self._setup_ui()
        self._setup_menus()
        self._setup_status_bar()
        self._load_dock_state()  # Dock 상태를 먼저 로드
        self._load_ptz_keys()  # PTZ 키 설정 로드
        self._load_menu_keys()  # 메뉴 키 설정 로드
        self._setup_connections()  # 그 다음 시그널 연결
        self._setup_cleanup_timer()  # 자동 정리 타이머 설정
        self._setup_fullscreen_auto_hide()  # 전체화면 자동 UI 숨김 설정

        # fullscreen_on_start 설정 적용 (모든 UI 설정 완료 후)
        if self.config_manager.ui_config.fullscreen_on_start:
            self.showFullScreen()
            self.fullscreen_action.setChecked(True)
            logger.info("Window shown in fullscreen mode")

        logger.info("Enhanced main window initialized")

    def _setup_ui(self):
        """Setup main UI with splitter layout"""
        self.setWindowTitle(f"{self.app_display_name} - Network Video Recorder (Single Camera)")

        # UI 설정에서 window_state 및 fullscreen_on_start 가져오기
        ui_config = self.config_manager.ui_config
        ws = ui_config.window_state

        if ui_config.fullscreen_on_start:
            # 전체화면으로 시작
            logger.info("Starting in fullscreen mode (fullscreen_on_start=true)")
            # 먼저 기본 geometry 설정 (전체화면 전에 필요)
            self.setGeometry(100, 100, 1024, 768)
        else:
            # window_state 설정값 적용
            self.setGeometry(ws.get('x', 100), ws.get('y', 100),
                            ws.get('width', 1200), ws.get('height', 700))
            logger.info(f"Starting with window state: x={ws.get('x', 100)}, y={ws.get('y', 100)}, w={ws.get('width', 1200)}, h={ws.get('height', 700)}")

        # Central widget with splitter
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Camera list (as dock widget)
        self.camera_dock = QDockWidget("Cameras", self)
        self.camera_dock.setObjectName("camera_dock")  # 객체 이름 설정 (저장/복원에 필요)
        self.camera_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.camera_list = CameraListWidget(self.config_manager)
        self.camera_list.main_window = self  # Set reference to main window for grid_view access
        self.camera_dock.setWidget(self.camera_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.camera_dock)

        # Right panel - Recording control (as dock widget)
        self.recording_dock = QDockWidget("Recording Control", self)
        self.recording_dock.setObjectName("recording_dock")  # 객체 이름 설정
        self.recording_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.recording_control = RecordingControlWidget()
        self.recording_control.main_window = self  # MainWindow 참조 설정
        self.recording_dock.setWidget(self.recording_control)
        self.addDockWidget(Qt.RightDockWidgetArea, self.recording_dock)

        # Bottom panel - Playback widget (as dock widget)
        self.playback_dock = QDockWidget("Playback", self)
        self.playback_dock.setObjectName("playback_dock")  # 객체 이름 설정
        self.playback_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.playback_widget = PlaybackWidget()
        self.playback_dock.setWidget(self.playback_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.playback_dock)

        # Set initial playback dock height to 30% of window height
        self._update_playback_dock_size()

        # Main area - Grid view
        self.grid_view = GridViewWidget()
        splitter.addWidget(self.grid_view)

        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Apply theme from config
        self._apply_theme()

        # Load default layout from streaming config
        rows, cols = self.config_manager.get_default_layout()
        self.grid_view.set_layout(rows, cols)
        logger.info(f"Set initial grid layout to {rows}x{cols} from config")

    def _apply_theme(self):
        """Apply theme based on UI configuration"""
        ui_config = self.config_manager.ui_config
        theme = ui_config.theme if ui_config.theme in ['dark', 'light'] else 'dark'

        # Set theme in ThemeManager (force_update=True for initial setup)
        self.theme_manager.set_theme(theme, force_update=True)

        # Apply stylesheet to entire application (not just main window)
        app = QApplication.instance()
        if app:
            stylesheet = self.theme_manager.get_application_stylesheet()
            # 디버깅: 스타일시트 처음 100자 출력
            logger.debug(f"Stylesheet preview (first 200 chars): {stylesheet[:200]}")
            app.setStyleSheet(stylesheet)
            logger.info(f"Applied theme to application: {theme}")
        else:
            logger.warning("QApplication instance not found - applying theme to main window only")
            self.setStyleSheet(self.theme_manager.get_application_stylesheet())

    def _on_theme_changed(self, theme: str):
        """Handle theme changed signal from ThemeManager"""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self.theme_manager.get_application_stylesheet())
            logger.info(f"Theme changed to: {theme}")
        else:
            self.setStyleSheet(self.theme_manager.get_application_stylesheet())

    def _setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        # Single camera - no layout submenu needed
        # Just keep 1x1 layout option for consistency
        single_view = QAction("Single View", self)
        single_view.setShortcut(QKeySequence("Alt+1"))
        single_view.setEnabled(False)  # Already in single view
        view_menu.addAction(single_view)

        view_menu.addSeparator()

        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)

        view_menu.addSeparator()

        # Dock visibility
        self.camera_dock_action = QAction("Show Camera List", self)
        self.camera_dock_action.setCheckable(True)
        self.camera_dock_action.triggered.connect(self._toggle_camera_dock)
        view_menu.addAction(self.camera_dock_action)

        self.recording_dock_action = QAction("Show Recording Control", self)
        self.recording_dock_action.setCheckable(True)
        self.recording_dock_action.triggered.connect(self._toggle_recording_dock)
        view_menu.addAction(self.recording_dock_action)

        self.playback_dock_action = QAction("Show Playback", self)
        self.playback_dock_action.setCheckable(True)
        self.playback_dock_action.triggered.connect(self._toggle_playback_dock)
        view_menu.addAction(self.playback_dock_action)

        # Camera menu
        camera_menu = menubar.addMenu("Camera")

        connect_all_action = QAction("Connect All", self)
        connect_all_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        connect_all_action.triggered.connect(self._connect_all_cameras)
        camera_menu.addAction(connect_all_action)

        disconnect_all_action = QAction("Disconnect All", self)
        disconnect_all_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        disconnect_all_action.triggered.connect(self._disconnect_all_cameras)
        camera_menu.addAction(disconnect_all_action)

        camera_menu.addSeparator()

        sequence_action = QAction("Start Sequence", self)
        sequence_action.setShortcut(QKeySequence("Ctrl+S"))
        sequence_action.triggered.connect(self.grid_view.toggle_sequence)
        camera_menu.addAction(sequence_action)

        # Setting menu
        setting_menu = menubar.addMenu("Setting")

        settings_action = QAction("Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_settings_dialog)
        setting_menu.addAction(settings_action)

        # Logs menu
        logs_menu = menubar.addMenu("Logs")

        log_search_action = QAction("Log Search...", self)
        log_search_action.setShortcut(QKeySequence("Ctrl+L"))
        log_search_action.triggered.connect(self._show_log_viewer)
        logs_menu.addAction(log_search_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_connections(self):
        """Setup signal connections between components"""
        # Camera list signals
        self.camera_list.camera_selected.connect(self._on_camera_selected)
        self.camera_list.camera_added.connect(self._on_camera_added)
        self.camera_list.camera_removed.connect(self._on_camera_removed)
        self.camera_list.camera_connected.connect(self._on_camera_connected)
        self.camera_list.camera_disconnected.connect(self._on_camera_disconnected)

        # Grid view signals
        self.grid_view.channel_double_clicked.connect(self._on_channel_double_clicked)
        self.grid_view.layout_changed.connect(self._on_layout_changed)

        # Recording control signals
        self.recording_control.recording_started.connect(self._on_recording_started)
        self.recording_control.recording_stopped.connect(self._on_recording_stopped)

        # F5 키 단축키 설정 (Refresh Recordings)
        refresh_shortcut = QAction(self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self._refresh_recordings)
        self.addAction(refresh_shortcut)

        # Dock visibility 시그널 연결 (Dock이 닫힐 때 메뉴 체크 상태 동기화)
        self.camera_dock.visibilityChanged.connect(self._on_camera_dock_visibility_changed)
        self.recording_dock.visibilityChanged.connect(self._on_recording_dock_visibility_changed)
        self.playback_dock.visibilityChanged.connect(self._on_playback_dock_visibility_changed)

        # Auto-assign cameras to channels first
        self._auto_assign_cameras()
        # Then assign window handles to camera streams
        self._assign_window_handles_to_streams()
        # Finally populate recording control
        self._populate_recording_control()

        # Auto-connect cameras with streaming_enabled_start=true
        self._auto_connect_cameras()

    def _setup_cleanup_timer(self):
        """자동 정리 타이머 설정"""
        recording_config = self.config_manager.get_recording_config()

        if not recording_config.get('auto_cleanup_enabled', True):
            logger.info("Auto cleanup disabled")
            return

        interval_hours = recording_config.get('cleanup_interval_hours', 6)
        interval_ms = interval_hours * 60 * 60 * 1000

        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self._run_auto_cleanup)
        self.cleanup_timer.start(interval_ms)

        logger.info(f"Auto cleanup timer started: interval={interval_hours}h")

        # 시작 시 정리 실행
        if recording_config.get('cleanup_on_startup', True):
            QTimer.singleShot(30000, self._run_auto_cleanup)  # 30초 후
            logger.info("Cleanup on startup scheduled (30s delay)")

    def _run_auto_cleanup(self):
        """자동 정리 실행"""
        try:
            logger.info("Starting auto cleanup...")
            deleted_count = self.storage_service.auto_cleanup()

            if deleted_count > 0:
                logger.success(f"Auto cleanup completed: {deleted_count} files deleted")
            else:
                logger.info("Auto cleanup: no files to delete")
        except Exception as e:
            logger.error(f"Auto cleanup failed: {e}")

    def _setup_fullscreen_auto_hide(self):
        """전체화면 모드에서 UI 자동 숨김/표시 설정"""
        # 설정에서 자동 숨김 기능 활성화 여부 확인
        if not self.config_manager.ui_config.fullscreen_auto_hide_enabled:
            logger.info("Fullscreen auto-hide feature is disabled in settings")
            return

        # 마우스 추적 활성화 (마우스 움직임 이벤트를 받기 위해 필수)
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)

        # 모든 자식 위젯에도 마우스 추적 활성화
        for widget in self.findChildren(QWidget):
            widget.setMouseTracking(True)

        # 이벤트 필터 설치 (모든 이벤트 감지)
        self.installEventFilter(self)

        # 비활동 체크 타이머 시작
        self.ui_hide_timer = QTimer(self)
        self.ui_hide_timer.timeout.connect(self._check_inactivity)
        self.ui_hide_timer.start(1000)  # 1초마다 체크

        delay = self.config_manager.ui_config.fullscreen_auto_hide_delay_seconds
        logger.info(f"Fullscreen auto-hide feature initialized (delay: {delay}s)")

    def eventFilter(self, obj, event):
        """이벤트 필터: 마우스 활동 감지 (키보드는 제외)"""
        # 전체화면 모드일 때만 동작
        if self.isFullScreen():
            # 마우스 이동 또는 클릭만 감지 (키보드 이벤트는 제외)
            if event.type() in [QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease]:
                self._on_user_activity()

        return super().eventFilter(obj, event)

    def _on_user_activity(self):
        """사용자 활동 감지 시 호출"""
        self.last_activity_time = QDateTime.currentDateTime()

        # UI가 숨겨진 상태였다면 다시 표시
        if self.ui_hidden:
            self._show_ui()

    def _check_inactivity(self):
        """비활동 시간 체크 (타이머에서 1초마다 호출)"""
        # 전체화면 모드가 아니면 무시
        if not self.isFullScreen():
            # 전체화면 아닐 때는 UI 표시
            if self.ui_hidden:
                self._show_ui()
            return

        # 마지막 활동 이후 경과 시간 계산
        elapsed_seconds = self.last_activity_time.secsTo(QDateTime.currentDateTime())

        # 설정된 지연 시간 이상 비활동 시 UI 숨김
        delay = self.config_manager.ui_config.fullscreen_auto_hide_delay_seconds
        if elapsed_seconds >= delay and not self.ui_hidden:
            self._hide_ui()

    def _hide_ui(self):
        """메뉴바, Dock 위젯 및 controls_bar 숨김"""
        self.menuBar().hide()
        self.camera_dock.hide()
        self.recording_dock.hide()
        self.playback_dock.hide()

        # Grid view의 controls_bar도 숨김
        if self.grid_view and hasattr(self.grid_view, 'controls_bar'):
            self.grid_view.controls_bar.hide()

        self.ui_hidden = True
        logger.debug("UI hidden (fullscreen auto-hide)")

    def _show_ui(self):
        """메뉴바, Dock 위젯 및 controls_bar 표시"""
        self.menuBar().show()

        # Dock 상태 복원 (원래 표시 상태였던 것만 표시)
        dock_state = self.config_manager.ui_config.dock_state
        if dock_state.get("camera_visible", True):
            self.camera_dock.show()
        if dock_state.get("recording_visible", True):
            self.recording_dock.show()
        if dock_state.get("playback_visible", False):
            self.playback_dock.show()

        # Grid view의 controls_bar도 표시
        if self.grid_view and hasattr(self.grid_view, 'controls_bar'):
            self.grid_view.controls_bar.show()

        self.ui_hidden = False
        logger.debug("UI shown (user activity detected)")

    def _setup_status_bar(self):
        """Setup status bar with system monitoring"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 타이머와 스레드 변수 초기화 (closeEvent에서 참조되므로 항상 필요)
        self.status_timer = None
        self.clock_timer = None
        self.monitor_thread = None

        # show_status_bar 설정에 따라 표시/숨김
        ui_config = self.config_manager.ui_config
        if not ui_config.show_status_bar:
            self.status_bar.hide()
            logger.info("Status bar hidden (show_status_bar=false)")
            return

        # 상태바 스타일 (메인 테마와 일관성 유지)
        # 메인 테마의 QStatusBar 스타일이 적용되므로 별도 스타일 불필요

        # Connection status
        self.connection_label = QLabel("No cameras connected")
        self.status_bar.addWidget(self.connection_label)

        # Separator
        # self.status_bar.addWidget(QLabel(" | "))

        # Layout info
        self.layout_label = QLabel("Layout: Single Camera")
        self.status_bar.addWidget(self.layout_label)

        # Separator
        # self.status_bar.addWidget(QLabel(" | "))

        # System monitoring labels
        self.cpu_label = QLabel("CPU: --%")
        self.memory_label = QLabel("Memory: --%")
        self.temp_label = QLabel("Temp: --°C")
        self.disk_label = QLabel("Disk: -- GB free")
        self.clock_label = QLabel("")

        self.status_bar.addWidget(self.cpu_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.memory_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.temp_label)
        # self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.disk_label)
        self.status_bar.addPermanentWidget(self.clock_label)

        # 초기 시계 설정
        self._update_clock()

        # 시스템 모니터링 스레드 시작
        self.monitor_thread = SystemMonitorThread(update_interval=5)
        self.monitor_thread.status_updated.connect(self._update_system_status)
        self.monitor_thread.alert_triggered.connect(self._on_system_alert)
        self.monitor_thread.start()

        # 시계 업데이트 타이머 (1초마다)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

        # Connection status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)

        logger.info("Status bar with system monitoring initialized")

    def _update_status(self):
        """Update camera connection status"""
        # Get connection stats from camera list
        connected = 0
        total = 0

        for camera_id, camera_item in self.camera_list.camera_items.items():
            total += 1
            if camera_item.camera_stream and camera_item.camera_stream.is_connected():
                connected += 1

        if connected > 0:
            self.connection_label.setText(f"{connected}/{total} cameras connected")
        else:
            self.connection_label.setText("No cameras connected")

    def _update_system_status(self, cpu: float, memory: float, temp: float, disk_free: float):
        """
        시스템 상태 업데이트 (모니터링 스레드에서 호출)

        Args:
            cpu: CPU 사용률 (%)
            memory: 메모리 사용률 (%)
            temp: 시스템 온도 (°C)
            disk_free: 남은 디스크 공간 (GB)
        """
        # Performance config에서 임계값 가져오기
        perf_config = self.config_manager.config.get('performance', {})
        max_cpu = perf_config.get('max_cpu_percent', 80)
        max_memory_mb = perf_config.get('max_memory_mb', 2048)
        max_temp = perf_config.get('max_temp', 75)

        # 메모리를 MB로 변환 (memory는 퍼센트이므로 실제 MB로 변환)
        import psutil
        memory_info = psutil.virtual_memory()
        memory_mb = memory_info.used / (1024**2)

        # Warning 임계값 (80%)
        warning_cpu = max_cpu * 0.8
        warning_memory_mb = max_memory_mb * 0.8
        warning_temp = max_temp * 0.9

        # CPU 상태 표시
        if cpu >= max_cpu:
            self.cpu_label.setStyleSheet("color: #ff4444; font-weight: bold;")  # CRITICAL
        elif cpu >= warning_cpu:
            self.cpu_label.setStyleSheet("color: #ffaa00; font-weight: bold;")  # WARNING
        else:
            self.cpu_label.setStyleSheet("")  # NORMAL
        self.cpu_label.setText(f"CPU: {cpu:.1f}%")

        # 메모리 상태 표시
        if memory_mb >= max_memory_mb:
            self.memory_label.setStyleSheet("color: #ff4444; font-weight: bold;")  # CRITICAL
        elif memory_mb >= warning_memory_mb:
            self.memory_label.setStyleSheet("color: #ffaa00; font-weight: bold;")  # WARNING
        else:
            self.memory_label.setStyleSheet("")  # NORMAL
        self.memory_label.setText(f"Memory: {memory:.1f}%")

        # 온도 표시
        if temp > 0:
            if temp >= max_temp:
                self.temp_label.setStyleSheet("color: #ff4444; font-weight: bold;")  # CRITICAL
            elif temp >= warning_temp:
                self.temp_label.setStyleSheet("color: #ffaa00; font-weight: bold;")  # WARNING
            else:
                self.temp_label.setStyleSheet("")  # NORMAL
            self.temp_label.setText(f"Temp: {temp:.1f}°C")
        else:
            self.temp_label.setStyleSheet("")
            self.temp_label.setText("Temp: N/A")

        # 디스크 경고 (10GB 미만)
        if disk_free < 10:
            self.disk_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.disk_label.setStyleSheet("")
        self.disk_label.setText(f"Disk: {disk_free:.1f}GB free")

    def _on_system_alert(self, alert_level: str, message: str):
        """
        시스템 경고 발생 시 호출

        Args:
            alert_level: 경고 레벨 ('normal', 'warning', 'critical')
            message: 경고 메시지
        """
        from core.enums import AlertLevel

        # 상태바에 경고 메시지 표시 (5초 동안)
        if alert_level == AlertLevel.CRITICAL.value:
            # Critical 경고는 팝업으로도 표시
            self.status_bar.showMessage(f"⚠ CRITICAL: {message}", 10000)
            logger.critical(f"System Alert - {message}")

            # 사용자에게 알림 (선택적)
            # QMessageBox.critical(self, "System Critical Alert", message)

        elif alert_level == AlertLevel.WARNING.value:
            self.status_bar.showMessage(f"⚠ WARNING: {message}", 7000)
            logger.warning(f"System Alert - {message}")

        elif alert_level == AlertLevel.NORMAL.value:
            self.status_bar.showMessage("✓ System resources normal", 3000)
            logger.info("System Alert - Resources returned to normal")

    def _update_clock(self):
        """시계 업데이트"""
        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.clock_label.setText(f"  {current_time}")

    def _auto_assign_cameras(self):
        """Auto-assign cameras from config to grid channels"""
        # 디버그 로그 추가
        logger.info(f"ConfigManager cameras list: {self.config_manager.cameras}")
        logger.info(f"ConfigManager cameras count: {len(self.config_manager.cameras)}")

        cameras = self.config_manager.get_enabled_cameras()
        logger.info(f"Enabled cameras count: {len(cameras)}")

        if cameras:
            for cam in cameras:
                logger.info(f"Camera found: {cam.camera_id} - {cam.name} - enabled: {cam.enabled}")

        # Single camera setup - only use first camera
        if cameras:
            camera = cameras[0]
            channel = self.grid_view.get_channel(0)
            if channel:
                channel.update_camera_info(camera.camera_id, camera.name)
                logger.debug(f"Assigned {camera.camera_id} to single channel")
        else:
            logger.warning("No enabled cameras found in configuration!")

    def _assign_window_handles_to_streams(self):
        """Assign window handles from grid channels to camera streams"""
        logger.info("Assigning window handles to camera streams...")

        # 디버깅을 위해 모든 채널과 카메라 정보 출력
        logger.debug(f"Total channels: {len(self.grid_view.channels)}")
        logger.debug(f"Total camera streams: {len(self.camera_list.camera_streams)}")

        # 먼저 모든 채널 정보 확인
        for i, channel in enumerate(self.grid_view.channels[:16]):
            logger.debug(f"Channel {i}: camera_id={channel.camera_id}, has_handle={channel.get_window_handle() is not None}")

        # 카메라 ID를 기준으로 매칭
        for camera_id, stream in self.camera_list.camera_streams.items():
            # 해당 카메라 ID를 가진 채널 찾기
            window_handle_assigned = False
            for i, channel in enumerate(self.grid_view.channels[:16]):
                if channel.camera_id == camera_id:
                    window_handle = channel.get_window_handle()
                    if window_handle:
                        stream.window_handle = window_handle
                        logger.success(f"✓ Assigned window handle to {camera_id} (channel {i}): {window_handle}")
                        window_handle_assigned = True
                    else:
                        logger.warning(f"✗ No window handle available for {camera_id} (channel {i})")
                    break

            if not window_handle_assigned:
                logger.warning(f"✗ Camera {camera_id} not assigned to any channel")

    def _auto_connect_cameras(self):
        """
        프로그램 시작 시 streaming_enabled_start=true인 카메라 자동 연결
        camera_list_widget의 _connect_camera() 기능 재사용

        Note: 녹화 자동 시작은 _on_camera_connected()에서 recording_enabled_start 설정을 확인하여 처리
        """
        logger.info("Auto-connecting cameras with streaming_enabled_start=true...")

        cameras = self.config_manager.get_enabled_cameras()

        # streaming_enabled_start가 true인 카메라들을 찾아서 연결
        auto_connect_count = 0

        for camera in cameras:
            if hasattr(camera, 'streaming_enabled_start') and camera.streaming_enabled_start:
                logger.info(f"Auto-connecting camera: {camera.name} ({camera.camera_id})")

                # camera_list에서 해당 camera_item 찾기 및 선택
                if camera.camera_id in self.camera_list.camera_items:
                    camera_item = self.camera_list.camera_items[camera.camera_id]

                    # 아이템 선택 (camera_list_widget의 _connect_camera가 선택된 아이템 사용)
                    self.camera_list.list_widget.setCurrentItem(camera_item)

                    # camera_list_widget의 Connect 기능 재사용
                    # 녹화 자동 시작은 _on_camera_connected()에서 처리
                    self.camera_list._connect_camera()
                    auto_connect_count += 1
                else:
                    logger.warning(f"Camera {camera.camera_id} not found in camera list")

        if auto_connect_count > 0:
            logger.info(f"Auto-connected {auto_connect_count} camera(s)")
        else:
            logger.info("No cameras with streaming_enabled_start=true found")

    def _auto_start_recording(self, camera_id: str):
        """
        자동 녹화 시작 (RecordingControlWidget의 start_recording() 직접 호출)

        Args:
            camera_id: 카메라 ID
        """
        # 이미 녹화 중인지 확인
        if self.recording_control.is_recording(camera_id):
            logger.info(f"Recording already started for {camera_id} (skipping auto-start)")
            return

        # RecordingControlWidget의 start_recording() 메서드 직접 호출
        # (UI 메시지 표시 없이 녹화만 시작)
        if camera_id in self.recording_control.cameras:
            if self.recording_control.start_recording(camera_id):
                logger.success(f"✓ Auto-started recording for camera: {camera_id}")
                # 녹화 시작 후 즉시 UI 상태 업데이트
                self.recording_control.update_recording_status(camera_id, True)
            else:
                logger.error(f"✗ Failed to auto-start recording for camera: {camera_id}")
        else:
            logger.error(f"✗ Camera {camera_id} not found in recording control widget")

    def _update_window_handles_after_layout_change(self):
        """레이아웃 변경 후 윈도우 핸들 재할당 및 파이프라인 재연결"""
        logger.info("Updating window handles after layout change...")

        # 먼저 카메라를 새 채널에 재할당
        cameras = self.config_manager.get_enabled_cameras()

        # 연결된 스트림 임시 저장
        connected_streams = {}
        for camera in cameras[:len(self.grid_view.channels)]:
            stream = self.camera_list.get_camera_stream(camera.camera_id)
            if stream and stream.is_connected():
                connected_streams[camera.camera_id] = stream
                logger.info(f"Temporarily storing connected stream: {camera.camera_id}")

        # 모든 스트림 정지 (레이아웃 변경 중)
        for camera_id, stream in connected_streams.items():
            if stream.gst_pipeline:
                logger.info(f"Stopping pipeline for layout change: {camera_id}")
                stream.disconnect()

        # UI 업데이트를 위해 QTimer 사용 (비동기 처리)
        from PyQt5.QtCore import QTimer

        def reconnect_streams():
            # 새 채널에 카메라 재할당 및 파이프라인 재시작
            for i, camera in enumerate(cameras[:len(self.grid_view.channels)]):
                channel = self.grid_view.get_channel(i)
                if channel:
                    # 채널에 카메라 정보 업데이트
                    channel.update_camera_info(camera.camera_id, camera.name)

                    # 이전에 연결되어 있던 스트림이면 재연결
                    if camera.camera_id in connected_streams:
                        stream = connected_streams[camera.camera_id]
                        # 새 윈도우 핸들 가져오기
                        new_window_handle = channel.get_window_handle()

                        if new_window_handle:
                            # 스트림에 윈도우 핸들 설정하고 재연결
                            stream.window_handle = new_window_handle
                            logger.info(f"Reconnecting camera {camera.camera_id} with new window handle")

                            # 파이프라인 재시작
                            if stream.connect():
                                channel.set_connected(True)
                                logger.success(f"✓ Reconnected {camera.camera_id} after layout change")
                            else:
                                logger.error(f"✗ Failed to reconnect {camera.camera_id} after layout change")
                        else:
                            logger.warning(f"No window handle available for {camera.camera_id}")

            logger.success("Layout change completed - streams reconnected")

        # 300ms 후에 재연결 시작 (위젯 생성 및 파이프라인 정리 완료 대기)
        QTimer.singleShot(300, reconnect_streams)

    def _load_ptz_keys(self):
        """PTZ 키 설정 로드"""
        self.ptz_keys = self.config_manager.config.get("ptz_keys", {})
        logger.info(f"PTZ keys loaded: {len(self.ptz_keys)} keys")

    def _load_menu_keys(self):
        """메뉴 키 설정 로드"""
        self.menu_keys = self.config_manager.config.get("menu_keys", {})
        logger.info(f"Menu keys loaded: {len(self.menu_keys)} keys")

        # 디버그용 로그
        if "program_exit" in self.menu_keys:
            logger.debug(f"Program exit key: {self.menu_keys['program_exit']}")

    def _update_playback_dock_size(self):
        """Update playback dock height to 30% of window height"""
        if not self.playback_dock:
            return

        # Only resize if dock is in bottom area and not floating
        if self.dockWidgetArea(self.playback_dock) == Qt.BottomDockWidgetArea and not self.playback_dock.isFloating():
            window_height = self.height()
            # Calculate 30% of window height
            target_height = int(window_height * 0.3)

            # Use resizeDocks to set the height
            self.resizeDocks([self.playback_dock], [target_height], Qt.Vertical)
            logger.debug(f"Playback dock height set to {target_height}px (30% of {window_height}px)")

    def resizeEvent(self, event):
        """Handle window resize event to update playback dock size"""
        super().resizeEvent(event)

        # Update playback dock size when window is resized
        if hasattr(self, 'playback_dock'):
            self._update_playback_dock_size()

    def _on_camera_selected(self, camera_id: str):
        """Handle camera selection from list"""
        logger.debug(f"Camera selected: {camera_id}")

        # PTZ Controller 생성 (카메라가 PTZ 지원하는 경우)
        camera = self.config_manager.get_camera(camera_id)
        if camera and camera.ptz_type and camera.ptz_type.upper() != "NONE":
            try:
                self.ptz_controller = PTZController(camera)
                logger.info(f"PTZ Controller created for camera: {camera_id} (type: {camera.ptz_type})")
            except Exception as e:
                logger.error(f"Failed to create PTZ Controller: {e}")
                self.ptz_controller = None
        else:
            self.ptz_controller = None
            logger.debug(f"Camera {camera_id} does not support PTZ")

    def _on_camera_added(self, camera_config):
        """Handle camera added"""
        logger.info(f"Camera added: {camera_config.name}")
        self._auto_assign_cameras()
        # Add to recording control
        if hasattr(camera_config, 'rtsp_url'):
            self.recording_control.add_camera(
                camera_config.camera_id,
                camera_config.name,
                camera_config.rtsp_url,
                camera_config.enabled
            )

    def _on_camera_removed(self, camera_id: str):
        """Handle camera removed"""
        logger.info(f"Camera removed: {camera_id}")
        # Clear channel if assigned
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.update_camera_info("", "No Camera")
                channel.set_connected(False)
        # Remove from recording control
        self.recording_control.remove_camera(camera_id)

    def _on_camera_connected(self, camera_id: str):
        """Handle camera connected"""
        logger.info(f"Camera connected: {camera_id}")

        # PTZ Controller 생성 (연결된 카메라가 PTZ 지원하는 경우)
        camera = self.config_manager.get_camera(camera_id)
        if camera and camera.ptz_type and camera.ptz_type.upper() != "NONE":
            try:
                self.ptz_controller = PTZController(camera)
                # Grid View에 PTZ Controller 전달
                if self.grid_view:
                    self.grid_view.ptz_controller = self.ptz_controller
                    self.grid_view.ptz_speed = self.ptz_speed
                logger.success(f"✓ PTZ Controller activated for camera: {camera_id} (type: {camera.ptz_type})")
            except Exception as e:
                logger.error(f"Failed to create PTZ Controller: {e}")
                self.ptz_controller = None
        else:
            self.ptz_controller = None
            if self.grid_view:
                self.grid_view.ptz_controller = None
            logger.debug(f"Camera {camera_id} does not support PTZ")

        # Get camera stream
        stream = self.camera_list.get_camera_stream(camera_id)
        if not stream:
            logger.warning(f"No stream found for camera {camera_id}")
            return

        # Find channel with this camera and update
        channel_found = False
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel_found = True
                # Get window handle and set it on the pipeline
                window_handle = channel.get_window_handle()
                if window_handle and stream.gst_pipeline:
                    # Set video sink to render in widget
                    if stream.gst_pipeline.video_sink:
                        try:
                            stream.gst_pipeline.video_sink.set_window_handle(int(window_handle))
                            logger.info(f"Set window handle for camera {camera_id}: {window_handle}")
                        except Exception as e:
                            logger.warning(f"Failed to set window handle for {camera_id}: {e}")
                else:
                    logger.warning(f"Could not set window handle for {camera_id} - handle: {window_handle}, pipeline: {stream.gst_pipeline}")

                channel.set_connected(True)
                break

        if not channel_found:
            logger.warning(f"No channel found for camera {camera_id}")

        # Update RecordingStatusItem 연결 상태
        if camera_id in self.recording_control.camera_items:
            self.recording_control.camera_items[camera_id].set_connected(True)
            logger.debug(f"[UI SYNC] Updated RecordingStatusItem connection status for {camera_id}: True")

        # 녹화 상태 콜백 등록 (start_recording()에서 자동으로 콜백 호출)
        if stream and stream.gst_pipeline:
            def on_recording_state_change(cam_id: str, is_recording: bool):
                """파이프라인에서 녹화 상태 변경 시 UI 업데이트"""
                logger.debug(f"[UI SYNC] Recording state callback: {cam_id} -> {is_recording}")

                # Update Grid View (streaming UI)
                for channel in self.grid_view.channels:
                    if channel.camera_id == cam_id:
                        channel.set_recording(is_recording)
                        logger.debug(f"[UI SYNC] Updated Grid View for {cam_id}: recording={is_recording}")
                        break

                # Update Recording Control Widget
                self.recording_control.update_recording_status(cam_id, is_recording)

                # Emit signal for recording control widget
                if is_recording:
                    self.recording_control.recording_started.emit(cam_id)
                else:
                    self.recording_control.recording_stopped.emit(cam_id)

            stream.gst_pipeline.register_recording_callback(on_recording_state_change)
            logger.debug(f"[UI SYNC] Registered recording callback for {camera_id}")

            # 연결 상태 콜백 등록
            def on_connection_state_change(cam_id: str, is_connected: bool):
                """파이프라인에서 연결 상태 변경 시 UI 업데이트"""
                logger.debug(f"[CONNECTION SYNC] Connection state callback: {cam_id} -> {is_connected}")

                # Update Grid View
                for channel in self.grid_view.channels:
                    if channel.camera_id == cam_id:
                        channel.set_connected(is_connected)
                        logger.debug(f"[CONNECTION SYNC] Updated Grid View for {cam_id}: connected={is_connected}")
                        break

                # Update Recording Control Widget
                if cam_id in self.recording_control.camera_items:
                    self.recording_control.camera_items[cam_id].set_connected(is_connected)
                    logger.debug(f"[CONNECTION SYNC] Updated RecordingStatusItem for {cam_id}: connected={is_connected}")

            stream.gst_pipeline.register_connection_callback(on_connection_state_change)
            logger.debug(f"[CONNECTION SYNC] Registered connection callback for {camera_id}")

        # 자동 녹화 시작 (recording_enabled_start 설정 확인)
        camera_config = self.config_manager.get_camera(camera_id)
        if camera_config and camera_config.recording_enabled_start:
            logger.info(f"Auto-recording enabled for {camera_config.name} ({camera_id})")
            # 파이프라인 안정화를 위해 500ms 지연 후 녹화 시작
            # start_recording()이 valve를 열고 콜백을 호출하여 UI 업데이트
            QTimer.singleShot(500, lambda: self._auto_start_recording(camera_id))

    def _on_camera_disconnected(self, camera_id: str):
        """Handle camera disconnected"""
        logger.info(f"Camera disconnected: {camera_id}")

        # Find channel with this camera and update
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_connected(False)
                break

        # Update RecordingStatusItem 연결 상태
        if camera_id in self.recording_control.camera_items:
            self.recording_control.camera_items[camera_id].set_connected(False)
            logger.debug(f"[UI SYNC] Updated RecordingStatusItem connection status for {camera_id}: False")

    def _on_channel_double_clicked(self, channel_index: int):
        """Handle channel double-click"""
        logger.debug(f"Channel {channel_index} double-clicked")

    def _on_layout_changed(self, layout: tuple):
        """Handle layout change"""
        rows, cols = layout
        # Single camera - always show "Single Camera"
        self.layout_label.setText("Layout: Single Camera")
        logger.info(f"Single camera mode - layout fixed at 1x1")

        # 레이아웃 변경 시 윈도우 핸들 재할당 및 파이프라인 업데이트
        self._update_window_handles_after_layout_change()

    def _populate_recording_control(self):
        """Populate recording control with cameras"""
        cameras = self.config_manager.get_all_cameras()
        for camera in cameras:
            if hasattr(camera, 'rtsp_url'):
                self.recording_control.add_camera(
                    camera.camera_id,
                    camera.name,
                    camera.rtsp_url,
                    camera.enabled
                )
                logger.debug(f"Added camera to recording control: {camera.name}")

    def _on_recording_started(self, camera_id: str):
        """Handle recording started"""
        logger.info(f"Recording started for camera: {camera_id}")

        # Update channel indicator
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_recording(True)
                break

        # Update recording control widget UI
        if camera_id in self.recording_control.camera_items:
            self.recording_control.camera_items[camera_id].set_recording(True)
            logger.debug(f"Updated recording control widget for {camera_id} (started)")

    def _on_recording_stopped(self, camera_id: str):
        """Handle recording stopped"""
        logger.info(f"Recording stopped for camera: {camera_id}")

        # Update channel indicator
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_recording(False)
                break

        # Update recording control widget UI
        if camera_id in self.recording_control.camera_items:
            self.recording_control.camera_items[camera_id].set_recording(False)
            logger.debug(f"Updated recording control widget for {camera_id} (stopped)")

    def _add_camera(self):
        """Show add camera dialog"""
        self.camera_list._add_camera()

    def _show_settings_dialog(self):
        """Show integrated settings dialog"""
        from ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec_()

    def _show_log_viewer(self):
        """Show log viewer dialog"""
        from ui.log_viewer_dialog import LogViewerDialog

        dialog = LogViewerDialog(self.config_manager, self)
        dialog.exec_()

    def _on_settings_changed(self):
        """Handle settings changes"""
        logger.info("Settings changed - reloading configuration")

        # 설정 변경 후 필요한 처리
        # 예: 테마 적용, 레이아웃 변경, 상태바 표시 등

        # 테마 재적용
        self._apply_theme()

        # 상태바 표시 상태 업데이트
        ui_config = self.config_manager.ui_config
        if ui_config.show_status_bar:
            self.status_bar.show()
        else:
            self.status_bar.hide()

        # Dock 상태 업데이트
        dock_state = ui_config.dock_state
        self.camera_dock.setVisible(dock_state.get("camera_visible", True))
        self.recording_dock.setVisible(dock_state.get("recording_visible", True))
        self.playback_dock.setVisible(dock_state.get("playback_visible", False))

        # 레이아웃 재적용
        rows, cols = self.config_manager.get_default_layout()
        self.grid_view.set_layout(rows, cols)

        logger.info("Settings applied successfully")

    def _connect_all_cameras(self):
        """Connect all cameras"""
        logger.info("Connecting all cameras...")

        # 윈도우 핸들이 이미 할당되어 있는지 확인하고, 없으면 재할당
        self._assign_window_handles_to_streams()

        # 그 다음 연결
        self.camera_list._connect_all()

    def _disconnect_all_cameras(self):
        """Disconnect all cameras"""
        self.camera_list._disconnect_all()

    def _toggle_camera_dock(self, checked: bool):
        """Toggle camera dock visibility"""
        self.camera_dock.setVisible(checked)

    def _toggle_recording_dock(self, checked: bool):
        """Toggle recording dock visibility"""
        self.recording_dock.setVisible(checked)

    def _toggle_playback_dock(self, checked: bool):
        """Toggle playback dock visibility"""
        self.playback_dock.setVisible(checked)
        # 재생 독이 열릴 때 자동 스캔 제거 (사용자가 수동으로 새로고침)

    def _on_camera_dock_visibility_changed(self, visible: bool):
        """Camera dock visibility 변경 시 메뉴 액션 동기화"""
        self.camera_dock_action.setChecked(visible)
        logger.debug(f"Camera dock visibility changed: {visible}")

    def _on_recording_dock_visibility_changed(self, visible: bool):
        """Recording dock visibility 변경 시 메뉴 액션 동기화"""
        self.recording_dock_action.setChecked(visible)
        logger.debug(f"Recording dock visibility changed: {visible}")

    def _on_playback_dock_visibility_changed(self, visible: bool):
        """Playback dock visibility 변경 시 메뉴 액션 동기화"""
        self.playback_dock_action.setChecked(visible)
        logger.debug(f"Playback dock visibility changed: {visible}")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_action.setChecked(False)
        else:
            self.showFullScreen()
            self.fullscreen_action.setChecked(True)

    def _open_playback_mode(self):
        """재생 모드 열기"""
        logger.info("Opening playback mode...")

        # 재생 독 표시
        self.playback_dock.show()

        # 라이브 스트리밍 일시 중지 (선택적)
        if self.is_playback_mode:
            return

        self.is_playback_mode = True

        # 모든 카메라 연결 해제 (재생 모드에서는 리소스 절약)
        self.camera_list._disconnect_all()

        # 녹화 파일 자동 스캔 제거 (사용자가 수동으로 새로고침)
        # self.playback_widget.scan_recordings()

        # 상태바 업데이트
        self.status_bar.showMessage("재생 모드", 3000)

        logger.info("Playback mode opened")

    def _close_playback_mode(self):
        """재생 모드 닫기"""
        logger.info("Closing playback mode...")

        if not self.is_playback_mode:
            return

        # 재생 중인 파일 정지
        if self.playback_widget:
            self.playback_widget.stop_playback()

        # 재생 독 숨기기
        self.playback_dock.hide()

        self.is_playback_mode = False

        # 카메라 재연결 (선택적)
        # self._connect_all_cameras()

        # 상태바 업데이트
        self.status_bar.showMessage("라이브 모드", 3000)

        logger.info("Playback mode closed")

    def _refresh_recordings(self):
        """녹화 파일 목록 새로고침"""
        if self.playback_widget:
            self.playback_widget.scan_recordings()
            logger.info("Recordings refreshed")

    def _show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
        <b>Keyboard Shortcuts:</b><br><br>
        <b>General:</b><br>
        Ctrl+N - Add Camera<br>
        Ctrl+Q - Exit<br>
        F11 - Toggle Fullscreen<br><br>

        <b>View:</b><br>
        Alt+1 - Single View<br>
        F - Toggle Fullscreen<br>
        ESC - Exit Fullscreen<br><br>

        <b>Camera Control:</b><br>
        Ctrl+Shift+C - Connect Camera<br>
        Ctrl+Shift+D - Disconnect Camera<br><br>

        <b>Playback:</b><br>
        F5 - Refresh Recordings<br>
        Space - Play/Pause (in playback)<br>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.RichText)
        msg.setText(shortcuts)
        msg.exec_()

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            f"About {self.app_name}",
            f"<b>{self.app_name} - Network Video Recorder</b><br>"
            f"Version {self.app_version}<br><br>"
            "Single Camera View<br>"
            "Built with GStreamer and PyQt5<br><br>"
            "Optimized for single camera recording"
        )

    def _load_dock_state(self):
        """Load dock state from YAML configuration"""
        # Dock 표시 여부 복원 (YAML에서 로드)
        dock_state = self.config_manager.ui_config.dock_state
        camera_visible = dock_state.get("camera_visible", True)
        recording_visible = dock_state.get("recording_visible", True)
        playback_visible = dock_state.get("playback_visible", False)

        # Dock 표시 상태 설정
        self.camera_dock.setVisible(camera_visible)
        self.recording_dock.setVisible(recording_visible)
        self.playback_dock.setVisible(playback_visible)

        # 메뉴 체크 상태 동기화
        self.camera_dock_action.setChecked(camera_visible)
        self.recording_dock_action.setChecked(recording_visible)
        self.playback_dock_action.setChecked(playback_visible)

        logger.info(f"Dock state loaded from YAML - Camera: {camera_visible}, Recording: {recording_visible}, Playback: {playback_visible}")

    def _save_dock_state(self):
        """Save dock state to JSON configuration"""
        # 현재 윈도우 위치/크기 저장
        geometry = self.geometry()
        self.config_manager.update_ui_window_state(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height()
        )

        # 현재 Dock 표시 상태 저장
        self.config_manager.update_ui_dock_state(
            camera_visible=self.camera_dock.isVisible(),
            recording_visible=self.recording_dock.isVisible(),
            playback_visible=self.playback_dock.isVisible()
        )

        # JSON 파일에 저장
        self.config_manager.save_ui_config()

        logger.info(f"UI state saved to JSON - Window: {geometry.x()},{geometry.y()} {geometry.width()}x{geometry.height()}, Docks: Camera={self.camera_dock.isVisible()}, Recording={self.recording_dock.isVisible()}, Playback={self.playback_dock.isVisible()}")

    def keyPressEvent(self, event):
        """키보드 누름 이벤트 처리 (메뉴 키 및 PTZ 제어)"""
        # 자동 반복 이벤트는 무시
        if event.isAutoRepeat():
            event.accept()
            return

        # 먼저 menu_keys 확인 (F1-F12, Esc 등 특수 키)
        key_str = self._get_key_string(event)

        # menu_keys 처리
        for action, config_key in self.menu_keys.items():
            if config_key.upper() == key_str.upper():
                logger.debug(f"Menu key detected: {action} = {config_key}")
                if self._execute_menu_action(action):
                    event.accept()
                    return

        # 일반 문자 키 처리 (PTZ 키)
        key = event.text().upper()

        # PTZ 키 액션 찾기
        ptz_action = None
        for action, config_key in self.ptz_keys.items():
            if config_key.upper() == key:
                ptz_action = action
                break

        if ptz_action:
            self._execute_ptz_action(ptz_action, pressed=True)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """키보드 뗌 이벤트 처리 (PTZ 제어)"""
        # 자동 반복 이벤트는 무시
        if event.isAutoRepeat():
            event.accept()
            return

        key = event.text().upper()

        # PTZ 키 액션 찾기
        ptz_action = None
        for action, config_key in self.ptz_keys.items():
            if config_key.upper() == key:
                ptz_action = action
                break

        if ptz_action:
            self._execute_ptz_action(ptz_action, pressed=False)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def _execute_ptz_action(self, action: str, pressed: bool):
        """
        PTZ 액션 실행

        Args:
            action: PTZ 액션 (zoom_in, zoom_out, up, down 등)
            pressed: True=키 누름, False=키 뗌
        """
        if not self.ptz_controller:
            logger.debug("PTZ Controller not available")
            return

        # 키를 뗄 때
        if not pressed:
            # Zoom 명령의 경우 STOP 전송
            if action in ['zoom_in', 'zoom_out']:
                self.ptz_controller.zoom_stop()
                logger.debug(f"PTZ action released: {action} -> ZOOMSTOP")
            # 방향키도 STOP 전송
            elif action in ['pan_left', 'up', 'right_up', 'left', 'right', 'pan_down', 'down', 'right_down']:
                self.ptz_controller.stop()
                logger.debug(f"PTZ action released: {action} -> STOP")
            return

        # 키를 누를 때
        if action == 'zoom_in':
            self.ptz_controller.zoom_in(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Zoom In (Speed: {self.ptz_speed})", 1000)
        elif action == 'zoom_out':
            self.ptz_controller.zoom_out(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Zoom Out (Speed: {self.ptz_speed})", 1000)
        elif action == 'ptz_speed_up':
            self.ptz_speed = min(9, self.ptz_speed + 1)
            self.statusBar().showMessage(f"PTZ Speed: {self.ptz_speed}/9", 2000)
            logger.info(f"PTZ speed increased: {self.ptz_speed}/9")
        elif action == 'ptz_speed_down':
            self.ptz_speed = max(1, self.ptz_speed - 1)
            self.statusBar().showMessage(f"PTZ Speed: {self.ptz_speed}/9", 2000)
            logger.info(f"PTZ speed decreased: {self.ptz_speed}/9")
        elif action == 'up':
            self.ptz_controller.move_up(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Up", 1000)
        elif action == 'down':
            self.ptz_controller.move_down(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Down", 1000)
        elif action == 'left':
            self.ptz_controller.move_left(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Left", 1000)
        elif action == 'right':
            self.ptz_controller.move_right(self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Right", 1000)
        elif action == 'pan_left':
            self.ptz_controller.send_command("UPLEFT", self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Up-Left", 1000)
        elif action == 'right_up':
            self.ptz_controller.send_command("UPRIGHT", self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Up-Right", 1000)
        elif action == 'pan_down':
            self.ptz_controller.send_command("DOWNLEFT", self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Down-Left", 1000)
        elif action == 'right_down':
            self.ptz_controller.send_command("DOWNRIGHT", self.ptz_speed)
            self.statusBar().showMessage(f"PTZ: Down-Right", 1000)
        elif action == 'stop':
            self.ptz_controller.stop()
            self.statusBar().showMessage(f"PTZ: Stop", 1000)

        logger.debug(f"PTZ action executed: {action} (pressed={pressed}, speed={self.ptz_speed})")

    def _get_key_string(self, event):
        """
        키 이벤트를 문자열로 변환
        F1-F12, Esc 등 특수 키를 처리
        """
        key = event.key()

        # F1-F12 키 처리
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f"F{key - Qt.Key_F1 + 1}"

        # 특수 키 매핑
        special_keys = {
            Qt.Key_Escape: "Esc",
            Qt.Key_Return: "Enter",
            Qt.Key_Enter: "Enter",
            Qt.Key_Tab: "Tab",
            Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Delete",
            Qt.Key_Home: "Home",
            Qt.Key_End: "End",
            Qt.Key_PageUp: "PageUp",
            Qt.Key_PageDown: "PageDown",
            Qt.Key_Up: "Up",
            Qt.Key_Down: "Down",
            Qt.Key_Left: "Left",
            Qt.Key_Right: "Right",
            Qt.Key_Space: "Space"
        }

        if key in special_keys:
            return special_keys[key]

        # 일반 문자 키
        return event.text()

    def _execute_menu_action(self, action: str) -> bool:
        """
        메뉴 액션 실행

        Args:
            action: 실행할 액션 이름

        Returns:
            bool: 액션이 처리되었으면 True
        """
        logger.info(f"Executing menu action: {action}")

        # program_exit 처리
        if action == "program_exit":
            logger.info("Program exit requested via hotkey")
            self.close()
            return True

        # camera_connect 처리
        elif action == "camera_connect":
            if self.camera_list.current_camera_id:
                self.camera_list._connect_camera()
            return True

        # camera_stop 처리
        elif action == "camera_stop":
            if self.camera_list.current_camera_id:
                self.camera_list._disconnect_camera()
            return True

        # camera_connect_all 처리
        elif action == "camera_connect_all":
            self.camera_list._connect_all()
            return True

        # camera_stop_all 처리
        elif action == "camera_stop_all":
            self.camera_list._disconnect_all()
            return True

        # record_start 처리
        elif action == "record_start":
            self.recording_control._start_recording()
            return True

        # record_stop 처리
        elif action == "record_stop":
            self.recording_control._stop_recording()
            return True

        # screen_hide 처리
        elif action == "screen_hide":
            # 전체화면 모드에서 나가기
            if self.isFullScreen():
                self.grid_view.exit_fullscreen()
            return True

        # menu_open 처리 (F11 - 전체화면 토글)
        elif action == "menu_open":
            self.toggle_fullscreen()
            return True

        # TODO: 다른 액션들 구현
        # prev_group, next_group, prev_config, next_config
        # screen_rotate, screen_flip

        logger.warning(f"Menu action not implemented: {action}")
        return False

    def closeEvent(self, event: QCloseEvent):
        """Handle application close event"""
        logger.info("Shutting down application...")

        # Dock 상태 저장
        self._save_dock_state()

        # Stop timers
        if self.status_timer:
            self.status_timer.stop()

        if hasattr(self, 'clock_timer') and self.clock_timer:
            self.clock_timer.stop()

        if hasattr(self, 'cleanup_timer') and self.cleanup_timer:
            self.cleanup_timer.stop()
            logger.info("Cleanup timer stopped")

        if hasattr(self, 'ui_hide_timer') and self.ui_hide_timer:
            self.ui_hide_timer.stop()
            logger.info("UI hide timer stopped")

        # Stop system monitoring thread
        if self.monitor_thread:
            self.monitor_thread.stop()

        # Stop playback if active
        if self.playback_widget:
            self.playback_widget.cleanup()

        # Disconnect all cameras
        self.camera_list._disconnect_all()

        # NOTE: save_config() 제거됨
        # 프로그램 종료 시 자동 저장하면 cameras가 비어있을 때 설정이 초기화되는 문제 발생
        # 설정은 UI에서 카메라 추가/제거 시에만 저장됨

        event.accept()
        logger.info("Application closed")