-- IT_RNVR Database Schema
-- SQLite 3
-- 설정 정보를 저장하는 데이터베이스 스키마

-- 1. app 테이블: 애플리케이션 기본 정보
CREATE TABLE IF NOT EXISTS app (
    app_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    version TEXT NOT NULL,
    schema_version INTEGER DEFAULT 1
);

-- 2. ui 테이블: UI 설정
CREATE TABLE IF NOT EXISTS ui (
    ui_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    theme TEXT NOT NULL DEFAULT 'dark',
    show_status_bar BOOLEAN NOT NULL DEFAULT 1,
    fullscreen_on_start BOOLEAN NOT NULL DEFAULT 0,
    fullscreen_auto_hide_enabled BOOLEAN NOT NULL DEFAULT 1,
    fullscreen_auto_hide_delay_seconds INTEGER NOT NULL DEFAULT 10,
    window_state_x INTEGER NOT NULL DEFAULT 0,
    window_state_y INTEGER NOT NULL DEFAULT 0,
    window_state_width INTEGER NOT NULL DEFAULT 1920,
    window_state_height INTEGER NOT NULL DEFAULT 1080,
    dock_state_camera_visible BOOLEAN NOT NULL DEFAULT 1,
    dock_state_recording_visible BOOLEAN NOT NULL DEFAULT 1,
    dock_state_playback_visible BOOLEAN NOT NULL DEFAULT 1
);

-- 3. streaming 테이블: 스트리밍 설정
CREATE TABLE IF NOT EXISTS streaming (
    streaming_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    default_layout TEXT NOT NULL DEFAULT '1x1',
    show_timestamp BOOLEAN NOT NULL DEFAULT 1,
    show_camera_name BOOLEAN NOT NULL DEFAULT 1,
    osd_font_size INTEGER NOT NULL DEFAULT 14,
    osd_font_color TEXT NOT NULL DEFAULT '255,255,255',  -- CSV 형식으로 저장
    osd_valignment TEXT NOT NULL DEFAULT 'top',
    osd_halignment TEXT NOT NULL DEFAULT 'left',
    osd_xpad INTEGER NOT NULL DEFAULT 20,
    osd_ypad INTEGER NOT NULL DEFAULT 15,
    use_hardware_acceleration BOOLEAN NOT NULL DEFAULT 1,
    decoder_preference TEXT NOT NULL DEFAULT 'avdec_h264,omxh264dec,v4l2h264dec',  -- CSV 형식
    buffer_size INTEGER NOT NULL DEFAULT 10485760,
    latency_ms INTEGER NOT NULL DEFAULT 100,
    tcp_timeout INTEGER NOT NULL DEFAULT 10000,
    connection_timeout INTEGER NOT NULL DEFAULT 10,
    auto_reconnect BOOLEAN NOT NULL DEFAULT 1,
    max_reconnect_attempts INTEGER NOT NULL DEFAULT 5,
    reconnect_delay_seconds INTEGER NOT NULL DEFAULT 5
);

-- 4. cameras 테이블: 카메라 설정
CREATE TABLE IF NOT EXISTS cameras (
    cameras_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    username TEXT,
    password TEXT,
    use_hardware_decode BOOLEAN NOT NULL DEFAULT 0,
    streaming_enabled_start BOOLEAN NOT NULL DEFAULT 0,
    recording_enabled_start BOOLEAN NOT NULL DEFAULT 0,
    motion_detection BOOLEAN NOT NULL DEFAULT 0,
    ptz_type TEXT,
    ptz_port TEXT,
    ptz_channel TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    video_transform_enabled BOOLEAN NOT NULL DEFAULT 0,
    video_transform_flip TEXT DEFAULT 'none',  -- none, horizontal, vertical, both
    video_transform_rotation INTEGER DEFAULT 0  -- 0, 90, 180, 270
);

-- 5. recording 테이블: 녹화 설정
CREATE TABLE IF NOT EXISTS recording (
    recording_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    file_format TEXT NOT NULL DEFAULT 'mkv',
    rotation_minutes INTEGER NOT NULL DEFAULT 2,
    codec TEXT NOT NULL DEFAULT 'h264',
    fragment_duration_ms INTEGER NOT NULL DEFAULT 1000
);

-- 6. backup 테이블: 백업 설정
CREATE TABLE IF NOT EXISTS backup (
    backup_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_path TEXT NOT NULL DEFAULT '',
    delete_after_backup BOOLEAN NOT NULL DEFAULT 0,
    verification BOOLEAN NOT NULL DEFAULT 1
);

-- 7. storage 테이블: 저장소 관리 설정
CREATE TABLE IF NOT EXISTS storage (
    storage_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_path TEXT NOT NULL DEFAULT './recordings',
    auto_cleanup_enabled BOOLEAN NOT NULL DEFAULT 1,
    cleanup_interval_hours INTEGER NOT NULL DEFAULT 1,
    cleanup_on_startup BOOLEAN NOT NULL DEFAULT 1,
    min_free_space_gb REAL NOT NULL DEFAULT 1.0,
    min_free_space_percent INTEGER NOT NULL DEFAULT 5,
    cleanup_threshold_percent INTEGER NOT NULL DEFAULT 90,
    retention_days INTEGER NOT NULL DEFAULT 30,
    delete_batch_size INTEGER NOT NULL DEFAULT 5,
    delete_batch_delay_seconds INTEGER NOT NULL DEFAULT 0,
    auto_delete_priority TEXT NOT NULL DEFAULT 'oldest_first'
);

-- 8. menu_keys 테이블: 메뉴 단축키 설정
CREATE TABLE IF NOT EXISTS menu_keys (
    menu_keys_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_connect TEXT NOT NULL DEFAULT 'F1',
    camera_stop TEXT NOT NULL DEFAULT 'F2',
    prev_group TEXT NOT NULL DEFAULT 'N',
    camera_connect_all TEXT NOT NULL DEFAULT 'F3',
    camera_stop_all TEXT NOT NULL DEFAULT 'F4',
    next_group TEXT NOT NULL DEFAULT 'M',
    prev_config TEXT NOT NULL DEFAULT 'F5',
    record_start TEXT NOT NULL DEFAULT 'F7',
    screen_rotate TEXT NOT NULL DEFAULT 'F9',
    next_config TEXT NOT NULL DEFAULT 'F6',
    record_stop TEXT NOT NULL DEFAULT 'F8',
    screen_flip TEXT NOT NULL DEFAULT 'F10',
    screen_hide TEXT NOT NULL DEFAULT 'Esc',
    menu_open TEXT NOT NULL DEFAULT 'F11',
    program_exit TEXT NOT NULL DEFAULT 'F12'
);

-- 9. ptz_keys 테이블: PTZ 제어 단축키 설정
CREATE TABLE IF NOT EXISTS ptz_keys (
    ptz_keys_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    pan_left TEXT NOT NULL DEFAULT 'Q',
    up TEXT NOT NULL DEFAULT 'W',
    right_up TEXT NOT NULL DEFAULT 'E',
    left TEXT NOT NULL DEFAULT 'A',
    stop TEXT NOT NULL DEFAULT 'S',
    right TEXT NOT NULL DEFAULT 'D',
    pan_down TEXT NOT NULL DEFAULT 'Z',
    down TEXT NOT NULL DEFAULT 'X',
    right_down TEXT NOT NULL DEFAULT 'C',
    zoom_in TEXT NOT NULL DEFAULT 'V',
    zoom_out TEXT NOT NULL DEFAULT 'B',
    ptz_speed_up TEXT NOT NULL DEFAULT 'R',
    ptz_speed_down TEXT NOT NULL DEFAULT 'T'
);

-- 10. logging 테이블: 로깅 설정
CREATE TABLE IF NOT EXISTS logging (
    logging_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    log_path TEXT NOT NULL DEFAULT './logs',
    console_enabled BOOLEAN NOT NULL DEFAULT 1,
    console_level TEXT NOT NULL DEFAULT 'DEBUG',
    console_colorize BOOLEAN NOT NULL DEFAULT 1,
    console_format TEXT NOT NULL DEFAULT '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>',
    file_enabled BOOLEAN NOT NULL DEFAULT 1,
    file_level TEXT NOT NULL DEFAULT 'DEBUG',
    file_filename TEXT NOT NULL DEFAULT 'pynvr_{time:YYYY-MM-DD}.log',
    file_format TEXT NOT NULL DEFAULT '{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}',
    file_rotation TEXT NOT NULL DEFAULT '1 day',
    file_retention TEXT NOT NULL DEFAULT '7 days',
    file_compression TEXT NOT NULL DEFAULT 'zip',
    file_max_size_mb INTEGER NOT NULL DEFAULT 100,
    file_rotation_count INTEGER NOT NULL DEFAULT 10,
    error_log_enabled BOOLEAN NOT NULL DEFAULT 1,
    error_log_filename TEXT NOT NULL DEFAULT 'pynvr_errors_{time:YYYY-MM-DD}.log',
    error_log_level TEXT NOT NULL DEFAULT 'ERROR',
    error_log_rotation TEXT NOT NULL DEFAULT '10 MB',
    error_log_retention TEXT NOT NULL DEFAULT '30 days',
    json_log_enabled BOOLEAN NOT NULL DEFAULT 0,
    json_log_filename TEXT NOT NULL DEFAULT 'pynvr_{time:YYYY-MM-DD}.json',
    json_log_serialize BOOLEAN NOT NULL DEFAULT 1
);

-- 11. performance 테이블: 성능 모니터링 설정
CREATE TABLE IF NOT EXISTS performance (
    performance_idx INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_enabled BOOLEAN NOT NULL DEFAULT 0,
    alert_warning_check_interval_seconds INTEGER NOT NULL DEFAULT 30,
    alert_critical_check_interval_seconds INTEGER NOT NULL DEFAULT 15,
    max_cpu_percent INTEGER NOT NULL DEFAULT 80,
    max_memory_mb INTEGER NOT NULL DEFAULT 6144,
    max_temp INTEGER NOT NULL DEFAULT 71
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_cameras_camera_id ON cameras(camera_id);
CREATE INDEX IF NOT EXISTS idx_cameras_enabled ON cameras(enabled);
CREATE INDEX IF NOT EXISTS idx_cameras_display_order ON cameras(display_order);
