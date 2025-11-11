"""
Database Manager
SQLite 데이터베이스 기반 설정 관리
"""

import sqlite3
import threading
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger


class DBManager:
    """
    SQLite 데이터베이스 관리 클래스
    설정 정보를 데이터베이스에 저장하고 조회하는 기능 제공
    """

    def __init__(self, db_path: str = "IT_RNVR.db"):
        """
        DBManager 초기화

        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.lock = threading.RLock()  # 멀티스레드 안전성을 위한 RLock (재진입 가능)

        # 데이터베이스 연결 (타임아웃 30초로 설정)
        self.conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환

        # WAL 모드 활성화 (읽기/쓰기 동시 처리 가능)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")  # WAL 모드에서 성능 최적화
        logger.debug("WAL mode enabled for database")

        # 스키마 초기화
        self._init_schema()

        logger.info(f"DBManager initialized: {db_path}")

    def _init_schema(self):
        """데이터베이스 스키마 초기화"""
        schema_file = Path(__file__).parent / "db_schema.sql"

        if not schema_file.exists():
            logger.warning(f"Schema file not found: {schema_file}")
            return

        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            with self.lock:
                self.conn.executescript(schema_sql)
                self.conn.commit()

            logger.debug("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")

    def begin_transaction(self):
        """트랜잭션 시작"""
        with self.lock:
            self.conn.execute("BEGIN TRANSACTION")

    def commit(self):
        """트랜잭션 커밋"""
        with self.lock:
            self.conn.commit()

    def rollback(self):
        """트랜잭션 롤백"""
        with self.lock:
            self.conn.rollback()

    def get_record_count(self, table_name: str) -> int:
        """
        테이블의 레코드 개수 반환

        Args:
            table_name: 테이블 이름

        Returns:
            레코드 개수
        """
        try:
            with self.lock:
                cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get record count from {table_name}: {e}")
            return 0

    # ========== 데이터 타입 변환 유틸리티 ==========

    def _serialize_list(self, data: list, dtype=str) -> str:
        """
        리스트를 CSV 문자열로 변환

        Args:
            data: 변환할 리스트
            dtype: 요소 데이터 타입 (str, int, float)

        Returns:
            CSV 문자열 (예: "255,255,255")
        """
        if not data:
            return ""
        return ",".join(str(item) for item in data)

    def _deserialize_list(self, data: str, dtype=str) -> list:
        """
        CSV 문자열을 리스트로 변환

        Args:
            data: CSV 문자열
            dtype: 요소 데이터 타입 (str, int, float)

        Returns:
            리스트 (예: [255, 255, 255])
        """
        if not data or data == "":
            return []

        items = data.split(",")

        if dtype == int:
            return [int(item.strip()) for item in items]
        elif dtype == float:
            return [float(item.strip()) for item in items]
        else:
            return [item.strip() for item in items]

    def _flatten_window_state(self, window_state: dict) -> dict:
        """
        window_state nested dict → flat dict 변환

        Args:
            window_state: {"x": 0, "y": 0, "width": 1920, "height": 1080}

        Returns:
            {"window_state_x": 0, "window_state_y": 0, ...}
        """
        return {
            "window_state_x": window_state.get("x", 0),
            "window_state_y": window_state.get("y", 0),
            "window_state_width": window_state.get("width", 1920),
            "window_state_height": window_state.get("height", 1080),
        }

    def _unflatten_window_state(self, data: dict) -> dict:
        """
        flat dict → window_state nested dict 변환

        Args:
            data: {"window_state_x": 0, "window_state_y": 0, ...}

        Returns:
            {"x": 0, "y": 0, "width": 1920, "height": 1080}
        """
        return {
            "x": data.get("window_state_x", 0),
            "y": data.get("window_state_y", 0),
            "width": data.get("window_state_width", 1920),
            "height": data.get("window_state_height", 1080),
        }

    def _flatten_dock_state(self, dock_state: dict) -> dict:
        """
        dock_state nested dict → flat dict 변환

        Args:
            dock_state: {"camera_visible": True, "recording_visible": True, ...}

        Returns:
            {"dock_state_camera_visible": True, ...}
        """
        return {
            "dock_state_camera_visible": dock_state.get("camera_visible", True),
            "dock_state_recording_visible": dock_state.get("recording_visible", True),
            "dock_state_playback_visible": dock_state.get("playback_visible", True),
        }

    def _unflatten_dock_state(self, data: dict) -> dict:
        """
        flat dict → dock_state nested dict 변환

        Args:
            data: {"dock_state_camera_visible": True, ...}

        Returns:
            {"camera_visible": True, "recording_visible": True, ...}
        """
        return {
            "camera_visible": data.get("dock_state_camera_visible", True),
            "recording_visible": data.get("dock_state_recording_visible", True),
            "playback_visible": data.get("dock_state_playback_visible", True),
        }

    def _flatten_video_transform(self, video_transform: dict) -> dict:
        """
        video_transform nested dict → flat dict 변환

        Args:
            video_transform: {"enabled": True, "flip": "vertical", "rotation": 90}

        Returns:
            {"video_transform_enabled": True, ...}
        """
        return {
            "video_transform_enabled": video_transform.get("enabled", False),
            "video_transform_flip": video_transform.get("flip", "none"),
            "video_transform_rotation": video_transform.get("rotation", 0),
        }

    def _unflatten_video_transform(self, data: dict) -> dict:
        """
        flat dict → video_transform nested dict 변환

        Args:
            data: {"video_transform_enabled": True, ...}

        Returns:
            {"enabled": True, "flip": "vertical", "rotation": 90}
        """
        return {
            "enabled": bool(data.get("video_transform_enabled", False)),
            "flip": data.get("video_transform_flip", "none"),
            "rotation": data.get("video_transform_rotation", 0),
        }

    def _flatten_logging_config(self, logging_config: dict) -> dict:
        """
        logging nested dict → flat dict 변환

        Args:
            logging_config: {"enabled": True, "console": {...}, "file": {...}, ...}

        Returns:
            flat dict
        """
        flat = {
            "enabled": logging_config.get("enabled", True),
            "log_path": logging_config.get("log_path", "./logs"),
        }

        # console
        console = logging_config.get("console", {})
        flat["console_enabled"] = console.get("enabled", True)
        flat["console_level"] = console.get("level", "DEBUG")
        flat["console_colorize"] = console.get("colorize", True)
        flat["console_format"] = console.get("format", "")

        # file
        file_config = logging_config.get("file", {})
        flat["file_enabled"] = file_config.get("enabled", True)
        flat["file_level"] = file_config.get("level", "DEBUG")
        flat["file_filename"] = file_config.get("filename", "pynvr_{time:YYYY-MM-DD}.log")
        flat["file_format"] = file_config.get("format", "")
        flat["file_rotation"] = file_config.get("rotation", "1 day")
        flat["file_retention"] = file_config.get("retention", "7 days")
        flat["file_compression"] = file_config.get("compression", "zip")
        flat["file_max_size_mb"] = file_config.get("max_size_mb", 100)
        flat["file_rotation_count"] = file_config.get("rotation_count", 10)

        # error_log
        error_log = logging_config.get("error_log", {})
        flat["error_log_enabled"] = error_log.get("enabled", True)
        flat["error_log_filename"] = error_log.get("filename", "pynvr_errors_{time:YYYY-MM-DD}.log")
        flat["error_log_level"] = error_log.get("level", "ERROR")
        flat["error_log_rotation"] = error_log.get("rotation", "10 MB")
        flat["error_log_retention"] = error_log.get("retention", "30 days")

        # json_log
        json_log = logging_config.get("json_log", {})
        flat["json_log_enabled"] = json_log.get("enabled", False)
        flat["json_log_filename"] = json_log.get("filename", "pynvr_{time:YYYY-MM-DD}.json")
        flat["json_log_serialize"] = json_log.get("serialize", True)

        return flat

    def _unflatten_logging_config(self, data: dict) -> dict:
        """
        flat dict → logging nested dict 변환

        Args:
            data: flat dict

        Returns:
            {"enabled": True, "console": {...}, "file": {...}, ...}
        """
        return {
            "enabled": bool(data.get("enabled", True)),
            "log_path": data.get("log_path", "./logs"),
            "console": {
                "enabled": bool(data.get("console_enabled", True)),
                "level": data.get("console_level", "DEBUG"),
                "colorize": bool(data.get("console_colorize", True)),
                "format": data.get("console_format", ""),
            },
            "file": {
                "enabled": bool(data.get("file_enabled", True)),
                "level": data.get("file_level", "DEBUG"),
                "filename": data.get("file_filename", "pynvr_{time:YYYY-MM-DD}.log"),
                "format": data.get("file_format", ""),
                "rotation": data.get("file_rotation", "1 day"),
                "retention": data.get("file_retention", "7 days"),
                "compression": data.get("file_compression", "zip"),
                "max_size_mb": data.get("file_max_size_mb", 100),
                "rotation_count": data.get("file_rotation_count", 10),
            },
            "error_log": {
                "enabled": bool(data.get("error_log_enabled", True)),
                "filename": data.get("error_log_filename", "pynvr_errors_{time:YYYY-MM-DD}.log"),
                "level": data.get("error_log_level", "ERROR"),
                "rotation": data.get("error_log_rotation", "10 MB"),
                "retention": data.get("error_log_retention", "30 days"),
            },
            "json_log": {
                "enabled": bool(data.get("json_log_enabled", False)),
                "filename": data.get("json_log_filename", "pynvr_{time:YYYY-MM-DD}.json"),
                "serialize": bool(data.get("json_log_serialize", True)),
            }
        }

    # ========== DB 읽기 메서드 ==========

    def get_app_config(self) -> dict:
        """
        app 테이블 → dict 반환

        Returns:
            {"app_name": "IT_RNVR", "version": "1.0.0"}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM app LIMIT 1")
                row = cursor.fetchone()

                if row:
                    return {
                        "app_name": row["app_name"],
                        "version": row["version"],
                    }
                else:
                    # 기본값 반환
                    return {
                        "app_name": "IT_RNVR",
                        "version": "1.0.0",
                    }
        except Exception as e:
            logger.error(f"Failed to get app config: {e}")
            return {"app_name": "IT_RNVR", "version": "1.0.0"}

    def get_ui_config(self) -> dict:
        """
        ui 테이블 → dict 반환 (nested 구조로 변환)

        Returns:
            {"theme": "dark", "window_state": {...}, "dock_state": {...}, ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM ui LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "theme": data["theme"],
                        "show_status_bar": bool(data["show_status_bar"]),
                        "fullscreen_on_start": bool(data["fullscreen_on_start"]),
                        "fullscreen_auto_hide_enabled": bool(data["fullscreen_auto_hide_enabled"]),
                        "fullscreen_auto_hide_delay_seconds": data["fullscreen_auto_hide_delay_seconds"],
                        "window_state": self._unflatten_window_state(data),
                        "dock_state": self._unflatten_dock_state(data),
                    }
                else:
                    # 기본값 반환
                    return {
                        "theme": "dark",
                        "show_status_bar": True,
                        "fullscreen_on_start": False,
                        "fullscreen_auto_hide_enabled": True,
                        "fullscreen_auto_hide_delay_seconds": 10,
                        "window_state": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                        "dock_state": {"camera_visible": True, "recording_visible": True, "playback_visible": True},
                    }
        except Exception as e:
            logger.error(f"Failed to get ui config: {e}")
            return {
                "theme": "dark",
                "show_status_bar": True,
                "fullscreen_on_start": False,
                "fullscreen_auto_hide_enabled": True,
                "fullscreen_auto_hide_delay_seconds": 10,
                "window_state": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                "dock_state": {"camera_visible": True, "recording_visible": True, "playback_visible": True},
            }

    def get_streaming_config(self) -> dict:
        """
        streaming 테이블 → dict 반환 (배열 필드 변환)

        Returns:
            {"osd_font_color": [255, 255, 255], "decoder_preference": ["avdec_h264", ...], ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM streaming LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "default_layout": data["default_layout"],
                        "show_timestamp": bool(data["show_timestamp"]),
                        "show_camera_name": bool(data["show_camera_name"]),
                        "osd_font_size": data["osd_font_size"],
                        "osd_font_color": self._deserialize_list(data["osd_font_color"], int),
                        "osd_valignment": data["osd_valignment"],
                        "osd_halignment": data["osd_halignment"],
                        "osd_xpad": data["osd_xpad"],
                        "osd_ypad": data["osd_ypad"],
                        "use_hardware_acceleration": bool(data["use_hardware_acceleration"]),
                        "decoder_preference": self._deserialize_list(data["decoder_preference"], str),
                        "buffer_size": data["buffer_size"],
                        "latency_ms": data["latency_ms"],
                        "tcp_timeout": data["tcp_timeout"],
                        "keepalive_timeout": data["keepalive_timeout"],
                        "connection_timeout": data["connection_timeout"],
                        "auto_reconnect": bool(data["auto_reconnect"]),
                        "max_reconnect_attempts": data["max_reconnect_attempts"],
                        "reconnect_delay_seconds": data["reconnect_delay_seconds"],
                    }
                else:
                    # 기본값 반환
                    return {
                        "default_layout": "1x1",
                        "show_timestamp": True,
                        "show_camera_name": True,
                        "osd_font_size": 14,
                        "osd_font_color": [255, 255, 255],
                        "osd_valignment": "top",
                        "osd_halignment": "left",
                        "osd_xpad": 20,
                        "osd_ypad": 15,
                        "use_hardware_acceleration": True,
                        "decoder_preference": ["avdec_h264", "omxh264dec", "v4l2h264dec"],
                        "buffer_size": 10485760,
                        "latency_ms": 100,
                        "tcp_timeout": 10000,
                        "keepalive_timeout": 5,
                        "connection_timeout": 10,
                        "auto_reconnect": True,
                        "max_reconnect_attempts": 5,
                        "reconnect_delay_seconds": 5,
                    }
        except Exception as e:
            logger.error(f"Failed to get streaming config: {e}")
            return {}

    def get_cameras(self) -> List[dict]:
        """
        cameras 테이블 → list[dict] 반환 (display_order 정렬, nested 구조)

        Returns:
            [{"camera_id": "cam_01", "video_transform": {...}, ...}]
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM cameras ORDER BY display_order")
                rows = cursor.fetchall()

                cameras = []
                for row in rows:
                    data = dict(row)
                    camera = {
                        "camera_id": data["camera_id"],
                        "name": data["name"],
                        "rtsp_url": data["rtsp_url"],
                        "enabled": bool(data["enabled"]),
                        "username": data.get("username"),
                        "password": data.get("password"),
                        "use_hardware_decode": bool(data["use_hardware_decode"]),
                        "streaming_enabled_start": bool(data["streaming_enabled_start"]),
                        "recording_enabled_start": bool(data["recording_enabled_start"]),
                        "motion_detection": bool(data["motion_detection"]),
                        "ptz_type": data.get("ptz_type"),
                        "ptz_port": data.get("ptz_port"),
                        "ptz_channel": data.get("ptz_channel"),
                        "video_transform": self._unflatten_video_transform(data),
                    }
                    cameras.append(camera)

                return cameras
        except Exception as e:
            logger.error(f"Failed to get cameras: {e}")
            return []

    def get_recording_config(self) -> dict:
        """
        recording 테이블 → dict

        Returns:
            {"file_format": "mkv", "rotation_minutes": 2, ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM recording LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "file_format": data["file_format"],
                        "rotation_minutes": data["rotation_minutes"],
                        "codec": data["codec"],
                        "fragment_duration_ms": data["fragment_duration_ms"],
                    }
                else:
                    return {
                        "file_format": "mkv",
                        "rotation_minutes": 2,
                        "codec": "h264",
                        "fragment_duration_ms": 1000,
                    }
        except Exception as e:
            logger.error(f"Failed to get recording config: {e}")
            return {}

    def get_storage_config(self) -> dict:
        """
        storage 테이블 → dict

        Returns:
            {"recording_path": "./recordings", ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM storage LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "recording_path": data["recording_path"],
                        "auto_cleanup_enabled": bool(data["auto_cleanup_enabled"]),
                        "cleanup_interval_hours": data["cleanup_interval_hours"],
                        "cleanup_on_startup": bool(data["cleanup_on_startup"]),
                        "min_free_space_gb": data["min_free_space_gb"],
                        "min_free_space_percent": data["min_free_space_percent"],
                        "cleanup_threshold_percent": data["cleanup_threshold_percent"],
                        "retention_days": data["retention_days"],
                        "delete_batch_size": data["delete_batch_size"],
                        "delete_batch_delay_seconds": data["delete_batch_delay_seconds"],
                        "auto_delete_priority": data["auto_delete_priority"],
                    }
                else:
                    return {
                        "recording_path": "./recordings",
                        "auto_cleanup_enabled": True,
                        "cleanup_interval_hours": 1,
                        "cleanup_on_startup": True,
                        "min_free_space_gb": 1.0,
                        "min_free_space_percent": 5,
                        "cleanup_threshold_percent": 90,
                        "retention_days": 30,
                        "delete_batch_size": 5,
                        "delete_batch_delay_seconds": 0,
                        "auto_delete_priority": "oldest_first",
                    }
        except Exception as e:
            logger.error(f"Failed to get storage config: {e}")
            return {}

    def get_backup_config(self) -> dict:
        """
        backup 테이블 → dict

        Returns:
            {"destination_path": "/path/to/backup", ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM backup LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "destination_path": data["destination_path"],
                        "delete_after_backup": bool(data["delete_after_backup"]),
                        "verification": bool(data["verification"]),
                    }
                else:
                    return {
                        "destination_path": "",
                        "delete_after_backup": False,
                        "verification": True,
                    }
        except Exception as e:
            logger.error(f"Failed to get backup config: {e}")
            return {}

    def get_menu_keys(self) -> dict:
        """
        menu_keys 테이블 → dict

        Returns:
            {"camera_connect": "F1", ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM menu_keys LIMIT 1")
                row = cursor.fetchone()

                if row:
                    # 모든 컬럼을 dict로 변환 (idx 제외)
                    data = dict(row)
                    data.pop("menu_keys_idx", None)
                    return data
                else:
                    return {
                        "camera_connect": "F1",
                        "camera_stop": "F2",
                        "prev_group": "N",
                        "camera_connect_all": "F3",
                        "camera_stop_all": "F4",
                        "next_group": "M",
                        "prev_config": "F5",
                        "record_start": "F7",
                        "screen_rotate": "F9",
                        "next_config": "F6",
                        "record_stop": "F8",
                        "screen_flip": "F10",
                        "screen_hide": "Esc",
                        "menu_open": "F11",
                        "program_exit": "F12",
                    }
        except Exception as e:
            logger.error(f"Failed to get menu_keys: {e}")
            return {}

    def get_ptz_keys(self) -> dict:
        """
        ptz_keys 테이블 → dict

        Returns:
            {"pan_left": "Q", ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM ptz_keys LIMIT 1")
                row = cursor.fetchone()

                if row:
                    # 모든 컬럼을 dict로 변환 (idx 제외)
                    data = dict(row)
                    data.pop("ptz_keys_idx", None)
                    return data
                else:
                    return {
                        "pan_left": "Q",
                        "up": "W",
                        "right_up": "E",
                        "left": "A",
                        "stop": "S",
                        "right": "D",
                        "pan_down": "Z",
                        "down": "X",
                        "right_down": "C",
                        "zoom_in": "V",
                        "zoom_out": "B",
                        "ptz_speed_up": "R",
                        "ptz_speed_down": "T",
                    }
        except Exception as e:
            logger.error(f"Failed to get ptz_keys: {e}")
            return {}

    def get_logging_config(self) -> dict:
        """
        logging 테이블 → dict (nested 구조)

        Returns:
            {"enabled": True, "console": {...}, "file": {...}, ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM logging LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return self._unflatten_logging_config(data)
                else:
                    # 기본값 반환
                    return {
                        "enabled": True,
                        "log_path": "./logs",
                        "console": {
                            "enabled": True,
                            "level": "DEBUG",
                            "colorize": True,
                            "format": "",
                        },
                        "file": {
                            "enabled": True,
                            "level": "DEBUG",
                            "filename": "pynvr_{time:YYYY-MM-DD}.log",
                            "format": "",
                            "rotation": "1 day",
                            "retention": "7 days",
                            "compression": "zip",
                            "max_size_mb": 100,
                            "rotation_count": 10,
                        },
                        "error_log": {
                            "enabled": True,
                            "filename": "pynvr_errors_{time:YYYY-MM-DD}.log",
                            "level": "ERROR",
                            "rotation": "10 MB",
                            "retention": "30 days",
                        },
                        "json_log": {
                            "enabled": False,
                            "filename": "pynvr_{time:YYYY-MM-DD}.json",
                            "serialize": True,
                        }
                    }
        except Exception as e:
            logger.error(f"Failed to get logging config: {e}")
            return {}

    def get_performance_config(self) -> dict:
        """
        performance 테이블 → dict

        Returns:
            {"alert_enabled": False, ...}
        """
        try:
            with self.lock:
                cursor = self.conn.execute("SELECT * FROM performance LIMIT 1")
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    return {
                        "alert_enabled": bool(data["alert_enabled"]),
                        "alert_warning_check_interval_seconds": data["alert_warning_check_interval_seconds"],
                        "alert_critical_check_interval_seconds": data["alert_critical_check_interval_seconds"],
                        "max_cpu_percent": data["max_cpu_percent"],
                        "max_memory_mb": data["max_memory_mb"],
                        "max_temp": data["max_temp"],
                    }
                else:
                    return {
                        "alert_enabled": False,
                        "alert_warning_check_interval_seconds": 30,
                        "alert_critical_check_interval_seconds": 15,
                        "max_cpu_percent": 80,
                        "max_memory_mb": 6144,
                        "max_temp": 71,
                    }
        except Exception as e:
            logger.error(f"Failed to get performance config: {e}")
            return {}

    # ========== DB 쓰기 메서드 ==========

    def save_app_config(self, data: dict):
        """
        dict → app 테이블 UPDATE/INSERT

        Args:
            data: {"app_name": "IT_RNVR", "version": "1.0.0"}
        """
        try:
            with self.lock:
                # 기존 레코드가 있으면 UPDATE, 없으면 INSERT
                count = self.get_record_count("app")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE app SET
                            app_name = ?,
                            version = ?
                        WHERE app_idx = (SELECT MIN(app_idx) FROM app)
                        """,
                        (data.get("app_name", "IT_RNVR"), data.get("version", "1.0.0"))
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO app (app_name, version)
                        VALUES (?, ?)
                        """,
                        (data.get("app_name", "IT_RNVR"), data.get("version", "1.0.0"))
                    )

                self.conn.commit()
                logger.debug("app config saved")
        except Exception as e:
            logger.error(f"Failed to save app config: {e}")
            raise

    def save_ui_config(self, data: dict):
        """
        dict → ui 테이블 UPDATE/INSERT (flat 구조로 변환)

        Args:
            data: {"theme": "dark", "window_state": {...}, "dock_state": {...}, ...}
        """
        try:
            with self.lock:
                # nested dict → flat dict 변환
                flat = {
                    "theme": data.get("theme", "dark"),
                    "show_status_bar": data.get("show_status_bar", True),
                    "fullscreen_on_start": data.get("fullscreen_on_start", False),
                    "fullscreen_auto_hide_enabled": data.get("fullscreen_auto_hide_enabled", True),
                    "fullscreen_auto_hide_delay_seconds": data.get("fullscreen_auto_hide_delay_seconds", 10),
                }

                # window_state flatten
                window_state = data.get("window_state", {})
                flat.update(self._flatten_window_state(window_state))

                # dock_state flatten
                dock_state = data.get("dock_state", {})
                flat.update(self._flatten_dock_state(dock_state))

                # 기존 레코드가 있으면 UPDATE, 없으면 INSERT
                count = self.get_record_count("ui")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE ui SET
                            theme = ?,
                            show_status_bar = ?,
                            fullscreen_on_start = ?,
                            fullscreen_auto_hide_enabled = ?,
                            fullscreen_auto_hide_delay_seconds = ?,
                            window_state_x = ?,
                            window_state_y = ?,
                            window_state_width = ?,
                            window_state_height = ?,
                            dock_state_camera_visible = ?,
                            dock_state_recording_visible = ?,
                            dock_state_playback_visible = ?
                        WHERE ui_idx = (SELECT MIN(ui_idx) FROM ui)
                        """,
                        (
                            flat["theme"],
                            flat["show_status_bar"],
                            flat["fullscreen_on_start"],
                            flat["fullscreen_auto_hide_enabled"],
                            flat["fullscreen_auto_hide_delay_seconds"],
                            flat["window_state_x"],
                            flat["window_state_y"],
                            flat["window_state_width"],
                            flat["window_state_height"],
                            flat["dock_state_camera_visible"],
                            flat["dock_state_recording_visible"],
                            flat["dock_state_playback_visible"],
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO ui (
                            theme, show_status_bar, fullscreen_on_start,
                            fullscreen_auto_hide_enabled, fullscreen_auto_hide_delay_seconds,
                            window_state_x, window_state_y, window_state_width, window_state_height,
                            dock_state_camera_visible, dock_state_recording_visible, dock_state_playback_visible
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            flat["theme"],
                            flat["show_status_bar"],
                            flat["fullscreen_on_start"],
                            flat["fullscreen_auto_hide_enabled"],
                            flat["fullscreen_auto_hide_delay_seconds"],
                            flat["window_state_x"],
                            flat["window_state_y"],
                            flat["window_state_width"],
                            flat["window_state_height"],
                            flat["dock_state_camera_visible"],
                            flat["dock_state_recording_visible"],
                            flat["dock_state_playback_visible"],
                        )
                    )

                self.conn.commit()
                logger.debug("ui config saved")
        except Exception as e:
            logger.error(f"Failed to save ui config: {e}")
            raise

    def save_cameras(self, cameras: List[dict]):
        """
        list[dict] → cameras 테이블 전체 교체 (DELETE + INSERT)

        Args:
            cameras: [{"camera_id": "cam_01", "video_transform": {...}, ...}]
        """
        try:
            with self.lock:
                # 기존 데이터 삭제
                self.conn.execute("DELETE FROM cameras")

                # 새 데이터 삽입
                for idx, camera in enumerate(cameras):
                    # video_transform flatten
                    video_transform = camera.get("video_transform", {})
                    flat_transform = self._flatten_video_transform(video_transform)

                    self.conn.execute(
                        """
                        INSERT INTO cameras (
                            camera_id, name, rtsp_url, enabled, username, password,
                            use_hardware_decode, streaming_enabled_start, recording_enabled_start,
                            motion_detection, ptz_type, ptz_port, ptz_channel,
                            display_order, video_transform_enabled, video_transform_flip,
                            video_transform_rotation
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            camera.get("camera_id", ""),
                            camera.get("name", ""),
                            camera.get("rtsp_url", ""),
                            camera.get("enabled", True),
                            camera.get("username"),
                            camera.get("password"),
                            camera.get("use_hardware_decode", False),
                            camera.get("streaming_enabled_start", False),
                            camera.get("recording_enabled_start", False),
                            camera.get("motion_detection", False),
                            camera.get("ptz_type"),
                            camera.get("ptz_port"),
                            camera.get("ptz_channel"),
                            idx,  # display_order
                            flat_transform["video_transform_enabled"],
                            flat_transform["video_transform_flip"],
                            flat_transform["video_transform_rotation"],
                        )
                    )

                self.conn.commit()
                logger.debug(f"cameras saved: {len(cameras)} cameras")
        except Exception as e:
            logger.error(f"Failed to save cameras: {e}")
            raise

    def save_streaming_config(self, data: dict):
        """
        dict → streaming 테이블 UPDATE/INSERT (배열 필드 변환)

        Args:
            data: {"osd_font_color": [255, 255, 255], "decoder_preference": [...], ...}
        """
        try:
            with self.lock:
                # 배열 필드를 CSV 문자열로 변환
                osd_font_color_str = self._serialize_list(data.get("osd_font_color", [255, 255, 255]), int)
                decoder_preference_str = self._serialize_list(
                    data.get("decoder_preference", ["avdec_h264", "omxh264dec", "v4l2h264dec"]), str
                )

                count = self.get_record_count("streaming")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE streaming SET
                            default_layout = ?, show_timestamp = ?, show_camera_name = ?,
                            osd_font_size = ?, osd_font_color = ?, osd_valignment = ?, osd_halignment = ?,
                            osd_xpad = ?, osd_ypad = ?, use_hardware_acceleration = ?,
                            decoder_preference = ?, buffer_size = ?, latency_ms = ?, tcp_timeout = ?,
                            keepalive_timeout = ?, connection_timeout = ?, auto_reconnect = ?,
                            max_reconnect_attempts = ?, reconnect_delay_seconds = ?
                        WHERE streaming_idx = (SELECT MIN(streaming_idx) FROM streaming)
                        """,
                        (
                            data.get("default_layout", "1x1"),
                            data.get("show_timestamp", True),
                            data.get("show_camera_name", True),
                            data.get("osd_font_size", 14),
                            osd_font_color_str,
                            data.get("osd_valignment", "top"),
                            data.get("osd_halignment", "left"),
                            data.get("osd_xpad", 20),
                            data.get("osd_ypad", 15),
                            data.get("use_hardware_acceleration", True),
                            decoder_preference_str,
                            data.get("buffer_size", 10485760),
                            data.get("latency_ms", 100),
                            data.get("tcp_timeout", 10000),
                            data.get("keepalive_timeout", 5),
                            data.get("connection_timeout", 10),
                            data.get("auto_reconnect", True),
                            data.get("max_reconnect_attempts", 5),
                            data.get("reconnect_delay_seconds", 5),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO streaming (
                            default_layout, show_timestamp, show_camera_name,
                            osd_font_size, osd_font_color, osd_valignment, osd_halignment,
                            osd_xpad, osd_ypad, use_hardware_acceleration,
                            decoder_preference, buffer_size, latency_ms, tcp_timeout,
                            keepalive_timeout, connection_timeout, auto_reconnect,
                            max_reconnect_attempts, reconnect_delay_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("default_layout", "1x1"),
                            data.get("show_timestamp", True),
                            data.get("show_camera_name", True),
                            data.get("osd_font_size", 14),
                            osd_font_color_str,
                            data.get("osd_valignment", "top"),
                            data.get("osd_halignment", "left"),
                            data.get("osd_xpad", 20),
                            data.get("osd_ypad", 15),
                            data.get("use_hardware_acceleration", True),
                            decoder_preference_str,
                            data.get("buffer_size", 10485760),
                            data.get("latency_ms", 100),
                            data.get("tcp_timeout", 10000),
                            data.get("keepalive_timeout", 5),
                            data.get("connection_timeout", 10),
                            data.get("auto_reconnect", True),
                            data.get("max_reconnect_attempts", 5),
                            data.get("reconnect_delay_seconds", 5),
                        )
                    )

                self.conn.commit()
                logger.debug("streaming config saved")
        except Exception as e:
            logger.error(f"Failed to save streaming config: {e}")
            raise

    def save_recording_config(self, data: dict):
        """dict → recording 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("recording")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE recording SET
                            file_format = ?, rotation_minutes = ?, codec = ?, fragment_duration_ms = ?
                        WHERE recording_idx = (SELECT MIN(recording_idx) FROM recording)
                        """,
                        (
                            data.get("file_format", "mkv"),
                            data.get("rotation_minutes", 2),
                            data.get("codec", "h264"),
                            data.get("fragment_duration_ms", 1000),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO recording (file_format, rotation_minutes, codec, fragment_duration_ms)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            data.get("file_format", "mkv"),
                            data.get("rotation_minutes", 2),
                            data.get("codec", "h264"),
                            data.get("fragment_duration_ms", 1000),
                        )
                    )

                self.conn.commit()
                logger.debug("recording config saved")
        except Exception as e:
            logger.error(f"Failed to save recording config: {e}")
            raise

    def save_storage_config(self, data: dict):
        """dict → storage 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("storage")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE storage SET
                            recording_path = ?, auto_cleanup_enabled = ?, cleanup_interval_hours = ?,
                            cleanup_on_startup = ?, min_free_space_gb = ?, min_free_space_percent = ?,
                            cleanup_threshold_percent = ?, retention_days = ?, delete_batch_size = ?,
                            delete_batch_delay_seconds = ?, auto_delete_priority = ?
                        WHERE storage_idx = (SELECT MIN(storage_idx) FROM storage)
                        """,
                        (
                            data.get("recording_path", "./recordings"),
                            data.get("auto_cleanup_enabled", True),
                            data.get("cleanup_interval_hours", 1),
                            data.get("cleanup_on_startup", True),
                            data.get("min_free_space_gb", 1.0),
                            data.get("min_free_space_percent", 5),
                            data.get("cleanup_threshold_percent", 90),
                            data.get("retention_days", 30),
                            data.get("delete_batch_size", 5),
                            data.get("delete_batch_delay_seconds", 0),
                            data.get("auto_delete_priority", "oldest_first"),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO storage (
                            recording_path, auto_cleanup_enabled, cleanup_interval_hours,
                            cleanup_on_startup, min_free_space_gb, min_free_space_percent,
                            cleanup_threshold_percent, retention_days, delete_batch_size,
                            delete_batch_delay_seconds, auto_delete_priority
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("recording_path", "./recordings"),
                            data.get("auto_cleanup_enabled", True),
                            data.get("cleanup_interval_hours", 1),
                            data.get("cleanup_on_startup", True),
                            data.get("min_free_space_gb", 1.0),
                            data.get("min_free_space_percent", 5),
                            data.get("cleanup_threshold_percent", 90),
                            data.get("retention_days", 30),
                            data.get("delete_batch_size", 5),
                            data.get("delete_batch_delay_seconds", 0),
                            data.get("auto_delete_priority", "oldest_first"),
                        )
                    )

                self.conn.commit()
                logger.debug("storage config saved")
        except Exception as e:
            logger.error(f"Failed to save storage config: {e}")
            raise

    def save_backup_config(self, data: dict):
        """dict → backup 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("backup")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE backup SET
                            destination_path = ?, delete_after_backup = ?, verification = ?
                        WHERE backup_idx = (SELECT MIN(backup_idx) FROM backup)
                        """,
                        (
                            data.get("destination_path", ""),
                            data.get("delete_after_backup", False),
                            data.get("verification", True),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO backup (destination_path, delete_after_backup, verification)
                        VALUES (?, ?, ?)
                        """,
                        (
                            data.get("destination_path", ""),
                            data.get("delete_after_backup", False),
                            data.get("verification", True),
                        )
                    )

                self.conn.commit()
                logger.debug("backup config saved")
        except Exception as e:
            logger.error(f"Failed to save backup config: {e}")
            raise

    def save_menu_keys(self, data: dict):
        """dict → menu_keys 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("menu_keys")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE menu_keys SET
                            camera_connect = ?, camera_stop = ?, prev_group = ?,
                            camera_connect_all = ?, camera_stop_all = ?, next_group = ?,
                            prev_config = ?, record_start = ?, screen_rotate = ?,
                            next_config = ?, record_stop = ?, screen_flip = ?,
                            screen_hide = ?, menu_open = ?, program_exit = ?
                        WHERE menu_keys_idx = (SELECT MIN(menu_keys_idx) FROM menu_keys)
                        """,
                        (
                            data.get("camera_connect", "F1"),
                            data.get("camera_stop", "F2"),
                            data.get("prev_group", "N"),
                            data.get("camera_connect_all", "F3"),
                            data.get("camera_stop_all", "F4"),
                            data.get("next_group", "M"),
                            data.get("prev_config", "F5"),
                            data.get("record_start", "F7"),
                            data.get("screen_rotate", "F9"),
                            data.get("next_config", "F6"),
                            data.get("record_stop", "F8"),
                            data.get("screen_flip", "F10"),
                            data.get("screen_hide", "Esc"),
                            data.get("menu_open", "F11"),
                            data.get("program_exit", "F12"),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO menu_keys (
                            camera_connect, camera_stop, prev_group,
                            camera_connect_all, camera_stop_all, next_group,
                            prev_config, record_start, screen_rotate,
                            next_config, record_stop, screen_flip,
                            screen_hide, menu_open, program_exit
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("camera_connect", "F1"),
                            data.get("camera_stop", "F2"),
                            data.get("prev_group", "N"),
                            data.get("camera_connect_all", "F3"),
                            data.get("camera_stop_all", "F4"),
                            data.get("next_group", "M"),
                            data.get("prev_config", "F5"),
                            data.get("record_start", "F7"),
                            data.get("screen_rotate", "F9"),
                            data.get("next_config", "F6"),
                            data.get("record_stop", "F8"),
                            data.get("screen_flip", "F10"),
                            data.get("screen_hide", "Esc"),
                            data.get("menu_open", "F11"),
                            data.get("program_exit", "F12"),
                        )
                    )

                self.conn.commit()
                logger.debug("menu_keys saved")
        except Exception as e:
            logger.error(f"Failed to save menu_keys: {e}")
            raise

    def save_ptz_keys(self, data: dict):
        """dict → ptz_keys 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("ptz_keys")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE ptz_keys SET
                            pan_left = ?, up = ?, right_up = ?, left = ?, stop = ?, right = ?,
                            pan_down = ?, down = ?, right_down = ?, zoom_in = ?, zoom_out = ?,
                            ptz_speed_up = ?, ptz_speed_down = ?
                        WHERE ptz_keys_idx = (SELECT MIN(ptz_keys_idx) FROM ptz_keys)
                        """,
                        (
                            data.get("pan_left", "Q"),
                            data.get("up", "W"),
                            data.get("right_up", "E"),
                            data.get("left", "A"),
                            data.get("stop", "S"),
                            data.get("right", "D"),
                            data.get("pan_down", "Z"),
                            data.get("down", "X"),
                            data.get("right_down", "C"),
                            data.get("zoom_in", "V"),
                            data.get("zoom_out", "B"),
                            data.get("ptz_speed_up", "R"),
                            data.get("ptz_speed_down", "T"),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO ptz_keys (
                            pan_left, up, right_up, left, stop, right,
                            pan_down, down, right_down, zoom_in, zoom_out,
                            ptz_speed_up, ptz_speed_down
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("pan_left", "Q"),
                            data.get("up", "W"),
                            data.get("right_up", "E"),
                            data.get("left", "A"),
                            data.get("stop", "S"),
                            data.get("right", "D"),
                            data.get("pan_down", "Z"),
                            data.get("down", "X"),
                            data.get("right_down", "C"),
                            data.get("zoom_in", "V"),
                            data.get("zoom_out", "B"),
                            data.get("ptz_speed_up", "R"),
                            data.get("ptz_speed_down", "T"),
                        )
                    )

                self.conn.commit()
                logger.debug("ptz_keys saved")
        except Exception as e:
            logger.error(f"Failed to save ptz_keys: {e}")
            raise

    def save_logging_config(self, data: dict):
        """dict → logging 테이블 UPDATE/INSERT (nested 구조를 flat으로 변환)"""
        try:
            with self.lock:
                flat = self._flatten_logging_config(data)
                count = self.get_record_count("logging")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE logging SET
                            enabled = ?, log_path = ?,
                            console_enabled = ?, console_level = ?, console_colorize = ?, console_format = ?,
                            file_enabled = ?, file_level = ?, file_filename = ?, file_format = ?,
                            file_rotation = ?, file_retention = ?, file_compression = ?,
                            file_max_size_mb = ?, file_rotation_count = ?,
                            error_log_enabled = ?, error_log_filename = ?, error_log_level = ?,
                            error_log_rotation = ?, error_log_retention = ?,
                            json_log_enabled = ?, json_log_filename = ?, json_log_serialize = ?
                        WHERE logging_idx = (SELECT MIN(logging_idx) FROM logging)
                        """,
                        (
                            flat["enabled"],
                            flat["log_path"],
                            flat["console_enabled"],
                            flat["console_level"],
                            flat["console_colorize"],
                            flat["console_format"],
                            flat["file_enabled"],
                            flat["file_level"],
                            flat["file_filename"],
                            flat["file_format"],
                            flat["file_rotation"],
                            flat["file_retention"],
                            flat["file_compression"],
                            flat["file_max_size_mb"],
                            flat["file_rotation_count"],
                            flat["error_log_enabled"],
                            flat["error_log_filename"],
                            flat["error_log_level"],
                            flat["error_log_rotation"],
                            flat["error_log_retention"],
                            flat["json_log_enabled"],
                            flat["json_log_filename"],
                            flat["json_log_serialize"],
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO logging (
                            enabled, log_path,
                            console_enabled, console_level, console_colorize, console_format,
                            file_enabled, file_level, file_filename, file_format,
                            file_rotation, file_retention, file_compression,
                            file_max_size_mb, file_rotation_count,
                            error_log_enabled, error_log_filename, error_log_level,
                            error_log_rotation, error_log_retention,
                            json_log_enabled, json_log_filename, json_log_serialize
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            flat["enabled"],
                            flat["log_path"],
                            flat["console_enabled"],
                            flat["console_level"],
                            flat["console_colorize"],
                            flat["console_format"],
                            flat["file_enabled"],
                            flat["file_level"],
                            flat["file_filename"],
                            flat["file_format"],
                            flat["file_rotation"],
                            flat["file_retention"],
                            flat["file_compression"],
                            flat["file_max_size_mb"],
                            flat["file_rotation_count"],
                            flat["error_log_enabled"],
                            flat["error_log_filename"],
                            flat["error_log_level"],
                            flat["error_log_rotation"],
                            flat["error_log_retention"],
                            flat["json_log_enabled"],
                            flat["json_log_filename"],
                            flat["json_log_serialize"],
                        )
                    )

                self.conn.commit()
                logger.debug("logging config saved")
        except Exception as e:
            logger.error(f"Failed to save logging config: {e}")
            raise

    def save_performance_config(self, data: dict):
        """dict → performance 테이블 UPDATE/INSERT"""
        try:
            with self.lock:
                count = self.get_record_count("performance")

                if count > 0:
                    self.conn.execute(
                        """
                        UPDATE performance SET
                            alert_enabled = ?, alert_warning_check_interval_seconds = ?,
                            alert_critical_check_interval_seconds = ?, max_cpu_percent = ?,
                            max_memory_mb = ?, max_temp = ?
                        WHERE performance_idx = (SELECT MIN(performance_idx) FROM performance)
                        """,
                        (
                            data.get("alert_enabled", False),
                            data.get("alert_warning_check_interval_seconds", 30),
                            data.get("alert_critical_check_interval_seconds", 15),
                            data.get("max_cpu_percent", 80),
                            data.get("max_memory_mb", 6144),
                            data.get("max_temp", 71),
                        )
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO performance (
                            alert_enabled, alert_warning_check_interval_seconds,
                            alert_critical_check_interval_seconds, max_cpu_percent,
                            max_memory_mb, max_temp
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("alert_enabled", False),
                            data.get("alert_warning_check_interval_seconds", 30),
                            data.get("alert_critical_check_interval_seconds", 15),
                            data.get("max_cpu_percent", 80),
                            data.get("max_memory_mb", 6144),
                            data.get("max_temp", 71),
                        )
                    )

                self.conn.commit()
                logger.debug("performance config saved")
        except Exception as e:
            logger.error(f"Failed to save performance config: {e}")
            raise

    # ========== JSON 마이그레이션 메서드 ==========

    def migrate_from_json(self, json_path: str):
        """
        JSON 파일에서 DB로 데이터 마이그레이션

        Args:
            json_path: JSON 설정 파일 경로
        """
        logger.info(f"Starting JSON to DB migration: {json_path}")

        try:
            # JSON 파일 읽기
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # 트랜잭션 시작
            with self.lock:
                self.conn.execute("BEGIN TRANSACTION")

                try:
                    # 각 섹션별로 저장
                    if "app" in json_data:
                        self.save_app_config(json_data["app"])
                        logger.debug("app migrated")

                    if "ui" in json_data:
                        self.save_ui_config(json_data["ui"])
                        logger.debug("ui migrated")

                    if "streaming" in json_data:
                        self.save_streaming_config(json_data["streaming"])
                        logger.debug("streaming migrated")

                    if "cameras" in json_data:
                        self.save_cameras(json_data["cameras"])
                        logger.debug(f"cameras migrated: {len(json_data['cameras'])} cameras")

                    if "recording" in json_data:
                        self.save_recording_config(json_data["recording"])
                        logger.debug("recording migrated")

                    if "storage" in json_data:
                        self.save_storage_config(json_data["storage"])
                        logger.debug("storage migrated")

                    if "backup" in json_data:
                        self.save_backup_config(json_data["backup"])
                        logger.debug("backup migrated")

                    if "menu_keys" in json_data:
                        self.save_menu_keys(json_data["menu_keys"])
                        logger.debug("menu_keys migrated")

                    if "ptz_keys" in json_data:
                        self.save_ptz_keys(json_data["ptz_keys"])
                        logger.debug("ptz_keys migrated")

                    if "logging" in json_data:
                        self.save_logging_config(json_data["logging"])
                        logger.debug("logging migrated")

                    if "performance" in json_data:
                        self.save_performance_config(json_data["performance"])
                        logger.debug("performance migrated")

                    # 커밋
                    self.conn.commit()

                    logger.info("JSON to DB migration completed successfully")

                    # JSON 파일 백업
                    backup_path = Path(json_path).with_suffix('.json.backup')
                    if backup_path.exists():
                        # 기존 백업이 있으면 타임스탬프 추가
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_path = Path(json_path).with_suffix(f'.json.backup.{timestamp}')

                    import shutil
                    shutil.copy2(json_path, backup_path)
                    logger.info(f"JSON file backed up to: {backup_path}")

                except Exception as e:
                    self.conn.rollback()
                    logger.error(f"Migration failed, rolled back: {e}")
                    raise

        except Exception as e:
            logger.error(f"Failed to migrate from JSON: {e}")
            raise
