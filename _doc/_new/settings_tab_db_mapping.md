# Settings Dialog 탭별 DB 테이블 매핑 분석

## 개요
`ui/settings_dialog.py`는 10개의 설정 탭을 통합 관리하며, 각 탭은 `IT_RNVR.db`의 특정 테이블과 매핑됩니다.

## 설정 저장 흐름
1. **UI 변경** → 탭의 위젯에서 사용자 입력
2. **메모리 저장** → `save_settings()`: ConfigManager.config dict 업데이트
3. **DB 저장** → `_save_section_to_db()`: db_manager를 통해 SQLite에 저장
4. **적용** → `save_to_db()`: 위 2단계를 순차 실행

## 탭별 매핑 상세

### 1. Basic Settings Tab
**관리 섹션**: `ui` (+ `app` 읽기 전용)
**DB 테이블**: `ui`, `app`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **App Info (읽기 전용)** | | | | |
| app_name_label | app.app_name | app.app_name | IT_RNVR | 앱 이름 |
| version_label | app.version | app.version | 1.0.0 | 버전 |
| **UI Settings** | | | | |
| theme_combo | ui.theme | ui.theme | dark | 테마 (dark/light) |
| status_bar_cb | ui.show_status_bar | ui.show_status_bar | True | 상태바 표시 |
| fullscreen_cb | ui.fullscreen_on_start | ui.fullscreen_on_start | False | 시작 시 전체화면 |
| auto_hide_enabled_cb | ui.fullscreen_auto_hide_enabled | ui.fullscreen_auto_hide_enabled | True | 전체화면 자동숨김 |
| auto_hide_delay_spin | ui.fullscreen_auto_hide_delay_seconds | ui.fullscreen_auto_hide_delay_seconds | 10 | 자동숨김 지연시간(초) |
| **Dock Visibility** | | | | |
| camera_dock_cb | ui.dock_state.camera_visible | ui.dock_state_camera_visible | True | 카메라 목록 Dock |
| recording_dock_cb | ui.dock_state.recording_visible | ui.dock_state_recording_visible | True | 녹화 컨트롤 Dock |
| playback_dock_cb | ui.dock_state.playback_visible | ui.dock_state_playback_visible | True | 재생 Dock |
| **Window State (읽기 전용)** | | | | |
| window_info_label | ui.window_state.{x,y,width,height} | ui.window_state_{x,y,width,height} | - | 창 위치/크기 |

**저장 메서드**:
- `save_settings()`: ConfigManager.ui_config 객체 및 config["ui"] dict 업데이트
- `_save_section_to_db()`: `db_manager.save_ui_config(asdict(ui_config))`

---

### 2. Cameras Settings Tab
**관리 섹션**: `cameras`
**DB 테이블**: `cameras`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Basic Info** | | | | |
| camera_id_edit | cameras[].camera_id | cameras.camera_id | cam_xx | 카메라 ID (고유) |
| camera_name_edit | cameras[].name | cameras.name | New Camera | 카메라 이름 |
| rtsp_url_edit | cameras[].rtsp_url | cameras.rtsp_url | - | RTSP URL |
| enabled_cb | cameras[].enabled | cameras.enabled | True | 카메라 활성화 |
| **Authentication** | | | | |
| username_edit | cameras[].username | cameras.username | None | RTSP 사용자명 |
| password_edit | cameras[].password | cameras.password | None | RTSP 비밀번호 |
| **PTZ Settings** | | | | |
| ptz_type_combo | cameras[].ptz_type | cameras.ptz_type | None | PTZ 타입 (None/HIK/ONVIF) |
| ptz_port_edit | cameras[].ptz_port | cameras.ptz_port | None | PTZ 포트 |
| ptz_channel_edit | cameras[].ptz_channel | cameras.ptz_channel | None | PTZ 채널 |
| **Video Transform** | | | | |
| transform_enabled_cb | cameras[].video_transform.enabled | cameras.video_transform_enabled | False | 비디오 변환 활성화 |
| flip_combo | cameras[].video_transform.flip | cameras.video_transform_flip | none | 뒤집기 (none/horizontal/vertical/both) |
| rotation_combo | cameras[].video_transform.rotation | cameras.video_transform_rotation | 0 | 회전 (0/90/180/270) |
| **Startup Options** | | | | |
| streaming_start_cb | cameras[].streaming_enabled_start | cameras.streaming_enabled_start | False | 시작 시 스트리밍 |
| recording_start_cb | cameras[].recording_enabled_start | cameras.recording_enabled_start | False | 시작 시 녹화 |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["cameras"] 및 ConfigManager.cameras (CameraConfigData 리스트) 업데이트
- `_save_section_to_db()`: `db_manager.save_cameras(cameras_data)`

**특징**:
- 카메라 리스트 관리 (추가/삭제/복제)
- 좌측 리스트, 우측 상세 설정 패널 구조
- `_apply_camera_changes()`: 현재 편집 중인 카메라 데이터 적용

---

### 3. Streaming Settings Tab
**관리 섹션**: `streaming`
**DB 테이블**: `streaming`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Display Layout** | | | | |
| default_layout_combo | streaming.default_layout | streaming.default_layout | 1x1 | 기본 레이아웃 (1x1/2x2/3x3/4x4) |
| **OSD Settings** | | | | |
| show_timestamp_cb | streaming.show_timestamp | streaming.show_timestamp | True | 타임스탬프 표시 |
| show_camera_name_cb | streaming.show_camera_name | streaming.show_camera_name | True | 카메라명 표시 |
| osd_font_size_spin | streaming.osd_font_size | streaming.osd_font_size | 14 | 폰트 크기 |
| osd_font_color_btn | streaming.osd_font_color | streaming.osd_font_color | [255,255,255] | 폰트 색상 (RGB) |
| osd_valignment_combo | streaming.osd_valignment | streaming.osd_valignment | top | 수직 정렬 |
| osd_halignment_combo | streaming.osd_halignment | streaming.osd_halignment | left | 수평 정렬 |
| osd_xpad_spin | streaming.osd_xpad | streaming.osd_xpad | 20 | 수평 패딩 |
| osd_ypad_spin | streaming.osd_ypad | streaming.osd_ypad | 15 | 수직 패딩 |
| **Hardware Acceleration** | | | | |
| use_hw_accel_cb | streaming.use_hardware_acceleration | streaming.use_hardware_acceleration | True | 하드웨어 가속 사용 |
| decoder_list | streaming.decoder_preference | streaming.decoder_preference | [v4l2h264dec, omxh264dec, avdec_h264] | 디코더 우선순위 (드래그 가능) |
| **Network & Buffering** | | | | |
| buffer_size_spin | streaming.buffer_size | streaming.buffer_size | 10485760 | 버퍼 크기 (bytes) |
| latency_spin | streaming.latency_ms | streaming.latency_ms | 200 | 최대 레이턴시 (ms) |
| tcp_timeout_spin | streaming.tcp_timeout | streaming.tcp_timeout | 10000 | TCP 타임아웃 (ms) |
| connection_timeout_spin | streaming.connection_timeout | streaming.connection_timeout | 10 | 연결 타임아웃 (초) |
| **Auto Reconnection** | | | | |
| auto_reconnect_cb | streaming.auto_reconnect | streaming.auto_reconnect | True | 자동 재연결 활성화 |
| max_reconnect_spin | streaming.max_reconnect_attempts | streaming.max_reconnect_attempts | 5 | 최대 재연결 시도 |
| reconnect_delay_spin | streaming.reconnect_delay_seconds | streaming.reconnect_delay_seconds | 5 | 재연결 지연 (초) |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["streaming"] 및 ConfigManager.streaming_config 업데이트
- `_save_section_to_db()`: `db_manager.save_streaming_config(config["streaming"])`

**특징**:
- ColorPickerButton: RGB 리스트로 색상 저장
- decoder_list: QListWidget 드래그로 우선순위 설정

---

### 4. Recording Settings Tab
**관리 섹션**: `recording`
**DB 테이블**: `recording`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Recording Format** | | | | |
| file_format_combo | recording.file_format | recording.file_format | mkv | 파일 포맷 (mkv/mp4/avi) |
| codec_combo | recording.codec | recording.codec | h264 | 코덱 (h264/h265) |
| fragment_duration_spin | recording.fragment_duration_ms | recording.fragment_duration_ms | 1000 | Fragment 간격 (ms) |
| **File Rotation** | | | | |
| rotation_minutes_spin | recording.rotation_minutes | recording.rotation_minutes | 60 | 파일 분할 간격 (분) |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["recording"] 및 ConfigManager.recording_config 업데이트
- `_save_section_to_db()`: `db_manager.save_recording_config(config["recording"])`

**참고**:
- `recording_path`는 이전에 이 탭에 있었으나 **Storage Settings Tab으로 이동**됨

---

### 5. Storage Settings Tab
**관리 섹션**: `storage`
**DB 테이블**: `storage`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Recording Path** | | | | |
| recording_path_edit | storage.recording_path | storage.recording_path | ./recordings | 녹화 파일 저장 경로 |
| **Auto Cleanup** | | | | |
| auto_cleanup_cb | storage.auto_cleanup_enabled | storage.auto_cleanup_enabled | True | 자동 정리 활성화 |
| cleanup_interval_spin | storage.cleanup_interval_hours | storage.cleanup_interval_hours | 6 | 정리 주기 (시간) |
| cleanup_on_startup_cb | storage.cleanup_on_startup | storage.cleanup_on_startup | True | 시작 시 정리 |
| delete_priority_combo | storage.auto_delete_priority | storage.auto_delete_priority | oldest_first | 삭제 우선순위 |
| **Space Management** | | | | |
| min_free_space_gb_spin | storage.min_free_space_gb | storage.min_free_space_gb | 10.0 | 최소 여유공간 (GB) |
| min_free_space_percent_spin | storage.min_free_space_percent | storage.min_free_space_percent | 5 | 최소 여유공간 (%) |
| cleanup_threshold_spin | storage.cleanup_threshold_percent | storage.cleanup_threshold_percent | 90 | 정리 임계값 (%) |
| **Retention Policy** | | | | |
| retention_days_spin | storage.retention_days | storage.retention_days | 30 | 보관 기간 (일) |
| delete_batch_size_spin | storage.delete_batch_size | storage.delete_batch_size | 5 | 배치 삭제 크기 |
| delete_batch_delay_spin | storage.delete_batch_delay_seconds | storage.delete_batch_delay_seconds | 1 | 배치 삭제 지연 (초) |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["storage"] 및 ConfigManager.storage_config 업데이트
- `_save_section_to_db()`: `db_manager.save_storage_config(config["storage"])`

**특징**:
- `_update_storage_status()`: 현재 디스크 사용량 및 녹화 파일 통계 표시
- 경로 검증 및 자동 생성

---

### 6. Backup Settings Tab
**관리 섹션**: `backup`
**DB 테이블**: `backup`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Backup Destination** | | | | |
| destination_path_edit | backup.destination_path | backup.destination_path | - | 백업 경로 |
| **Backup Options** | | | | |
| verification_cb | backup.verification | backup.verification | True | MD5 검증 |
| delete_after_cb | backup.delete_after_backup | backup.delete_after_backup | False | 백업 후 원본 삭제 |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["backup"] 및 ConfigManager.backup_config 업데이트
- `_save_section_to_db()`: `db_manager.save_backup_config(config["backup"])`

**특징**:
- `_on_path_changed()`: 경로 변경 시 여유 공간 계산 및 표시
- `_on_delete_after_toggled()`: 위험 옵션 활성화 시 경고 표시

---

### 7. Performance Settings Tab
**관리 섹션**: `performance`
**DB 테이블**: `performance`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Alert Settings** | | | | |
| alert_enabled_cb | performance.alert_enabled | performance.alert_enabled | False | 성능 알림 활성화 |
| warning_interval_spin | performance.alert_warning_check_interval_seconds | performance.alert_warning_check_interval_seconds | 30 | 경고 체크 간격 (초) |
| critical_interval_spin | performance.alert_critical_check_interval_seconds | performance.alert_critical_check_interval_seconds | 15 | 위험 체크 간격 (초) |
| **Performance Thresholds** | | | | |
| max_cpu_spin | performance.max_cpu_percent | performance.max_cpu_percent | 80 | 최대 CPU 사용률 (%) |
| max_memory_spin | performance.max_memory_mb | performance.max_memory_mb | 2048 | 최대 메모리 (MB) |
| max_temp_spin | performance.max_temp | performance.max_temp | 75 | 최대 온도 (°C) |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["performance"] 업데이트
- `_save_section_to_db()`: `db_manager.save_performance_config(performance_data)`

**특징**:
- `_validate_intervals()`: Critical 간격이 Warning보다 작거나 같도록 검증

---

### 8. Hot Keys Settings Tab
**관리 섹션**: `menu_keys`
**DB 테이블**: `menu_keys`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| camera_connect | menu_keys.camera_connect | menu_keys.camera_connect | F1 | 카메라 연결 |
| camera_stop | menu_keys.camera_stop | menu_keys.camera_stop | F2 | 카메라 정지 |
| camera_connect_all | menu_keys.camera_connect_all | menu_keys.camera_connect_all | F3 | 전체 연결 |
| camera_stop_all | menu_keys.camera_stop_all | menu_keys.camera_stop_all | F4 | 전체 정지 |
| prev_group | menu_keys.prev_group | menu_keys.prev_group | N | 이전 그룹 |
| next_group | menu_keys.next_group | menu_keys.next_group | M | 다음 그룹 |
| prev_config | menu_keys.prev_config | menu_keys.prev_config | F5 | 이전 설정 |
| next_config | menu_keys.next_config | menu_keys.next_config | F6 | 다음 설정 |
| record_start | menu_keys.record_start | menu_keys.record_start | F7 | 녹화 시작 |
| record_stop | menu_keys.record_stop | menu_keys.record_stop | F8 | 녹화 정지 |
| screen_rotate | menu_keys.screen_rotate | menu_keys.screen_rotate | F9 | 화면 회전 |
| screen_flip | menu_keys.screen_flip | menu_keys.screen_flip | F10 | 화면 뒤집기 |
| screen_hide | menu_keys.screen_hide | menu_keys.screen_hide | Esc | 화면 숨김 |
| menu_open | menu_keys.menu_open | menu_keys.menu_open | F11 | 메뉴 열기 |
| program_exit | menu_keys.program_exit | menu_keys.program_exit | F12 | 프로그램 종료 |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["menu_keys"] 업데이트
- `_save_section_to_db()`: `db_manager.save_menu_keys(menu_keys_data)`

**특징**:
- KeySequenceEdit 위젯으로 키 입력 받음
- `_on_key_changed()`: 실시간 중복 키 검증
- `_reset_to_defaults()`: 기본값으로 리셋

---

### 9. PTZ Keys Settings Tab
**관리 섹션**: `ptz_keys`
**DB 테이블**: `ptz_keys`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Direction Control (9-way)** | | | | |
| pan_left | ptz_keys.pan_left | ptz_keys.pan_left | Q | 좌상 (↖) |
| up | ptz_keys.up | ptz_keys.up | W | 상 (↑) |
| right_up | ptz_keys.right_up | ptz_keys.right_up | E | 우상 (↗) |
| left | ptz_keys.left | ptz_keys.left | A | 좌 (←) |
| stop | ptz_keys.stop | ptz_keys.stop | S | 정지 (■) |
| right | ptz_keys.right | ptz_keys.right | D | 우 (→) |
| pan_down | ptz_keys.pan_down | ptz_keys.pan_down | Z | 좌하 (↙) |
| down | ptz_keys.down | ptz_keys.down | X | 하 (↓) |
| right_down | ptz_keys.right_down | ptz_keys.right_down | C | 우하 (↘) |
| **Zoom Control** | | | | |
| zoom_in | ptz_keys.zoom_in | ptz_keys.zoom_in | V | 줌 인 |
| zoom_out | ptz_keys.zoom_out | ptz_keys.zoom_out | B | 줌 아웃 |
| **Speed Control** | | | | |
| ptz_speed_up | ptz_keys.ptz_speed_up | ptz_keys.ptz_speed_up | R | 속도 증가 |
| ptz_speed_down | ptz_keys.ptz_speed_down | ptz_keys.ptz_speed_down | T | 속도 감소 |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["ptz_keys"] 업데이트
- `_save_section_to_db()`: `db_manager.save_ptz_keys(ptz_keys_data)`

**특징**:
- 3x3 그리드 레이아웃으로 9방향 시각화
- KeySequenceEdit 위젯으로 키 입력
- 중복 키 검증 및 기본값 리셋 기능

---

### 10. Logging Settings Tab
**관리 섹션**: `logging`
**DB 테이블**: `logging`

| UI 컨트롤 | Config Key | DB 테이블.컬럼 | 기본값 | 설명 |
|----------|-----------|--------------|--------|------|
| **Main Settings** | | | | |
| logging_enabled_cb | logging.enabled | logging.enabled | True | 로깅 활성화 |
| log_path_edit | logging.log_path | logging.log_path | ./_logs | 로그 파일 경로 |
| **Console Log** | | | | |
| console_enabled_cb | logging.console.enabled | logging.console_enabled | True | 콘솔 로그 활성화 |
| console_level_combo | logging.console.level | logging.console_level | DEBUG | 로그 레벨 |
| console_colorize_cb | logging.console.colorize | logging.console_colorize | True | 색상화 |
| console_format_edit | logging.console.format | logging.console_format | - | 포맷 문자열 |
| **File Log** | | | | |
| file_enabled_cb | logging.file.enabled | logging.file_enabled | True | 파일 로그 활성화 |
| file_level_combo | logging.file.level | logging.file_level | DEBUG | 로그 레벨 |
| file_filename_edit | logging.file.filename | logging.file_filename | pynvr_{time}.log | 파일명 패턴 |
| file_format_edit | logging.file.format | logging.file_format | - | 포맷 문자열 |
| file_rotation_edit | logging.file.rotation | logging.file_rotation | 1 day | 로테이션 주기 |
| file_retention_edit | logging.file.retention | logging.file_retention | 7 days | 보관 기간 |
| file_compression_edit | logging.file.compression | logging.file_compression | zip | 압축 형식 |
| file_max_size_spin | logging.file.max_size_mb | logging.file_max_size_mb | 100 | 최대 크기 (MB) |
| file_rotation_count_spin | logging.file.rotation_count | logging.file_rotation_count | 10 | 로테이션 파일 수 |
| **Error Log** | | | | |
| error_enabled_cb | logging.error_log.enabled | logging.error_log_enabled | True | 에러 로그 활성화 |
| error_filename_edit | logging.error_log.filename | logging.error_log_filename | pynvr_errors_{time}.log | 파일명 패턴 |
| error_level_combo | logging.error_log.level | logging.error_log_level | ERROR | 로그 레벨 |
| error_rotation_edit | logging.error_log.rotation | logging.error_log_rotation | 10 MB | 로테이션 주기 |
| error_retention_edit | logging.error_log.retention | logging.error_log_retention | 30 days | 보관 기간 |
| **JSON Log** | | | | |
| json_enabled_cb | logging.json_log.enabled | logging.json_log_enabled | False | JSON 로그 활성화 |
| json_filename_edit | logging.json_log.filename | logging.json_log_filename | pynvr_{time}.json | 파일명 패턴 |
| json_serialize_cb | logging.json_log.serialize | logging.json_log_serialize | True | 직렬화 활성화 |

**저장 메서드**:
- `save_settings()`: ConfigManager.config["logging"] 업데이트 (nested dict)
- `_save_section_to_db()`: `db_manager.save_logging_config(logging_data)`

**특징**:
- Nested 구조 (console, file, error_log, json_log)
- Loguru 포맷 문자열 지원
- 경로 검증 및 자동 생성

---

## DB 테이블별 요약

| DB 테이블 | 관리 탭 | 주요 설정 | 레코드 수 |
|----------|--------|---------|---------|
| app | Basic | 앱 이름, 버전 (읽기 전용) | 1 |
| ui | Basic | 테마, 상태바, 전체화면, Dock 표시 | 1 |
| cameras | Cameras | 카메라 목록, RTSP, PTZ, Video Transform | N (카메라 수) |
| streaming | Streaming | 레이아웃, OSD, 디코더, 버퍼링, 재연결 | 1 |
| recording | Recording | 파일 포맷, 코덱, 분할 간격 | 1 |
| storage | Storage | 녹화 경로, 자동 정리, 보관 정책 | 1 |
| backup | Backup | 백업 경로, 검증, 원본 삭제 | 1 |
| performance | Performance | 성능 알림, CPU/메모리/온도 임계값 | 1 |
| menu_keys | Hot Keys | 메뉴 단축키 (F1~F12 등) | 1 |
| ptz_keys | PTZ Keys | PTZ 방향/줌/속도 단축키 | 1 |
| logging | Logging | 로깅 활성화, 콘솔/파일/에러/JSON 로그 | 1 |

---

## 주요 설계 패턴

### 1. BaseSettingsTab 상속 구조
모든 탭은 `BaseSettingsTab`을 상속하여 공통 기능 구현:
- `load_settings()`: DB/메모리에서 설정 로드
- `save_settings()`: 메모리(config dict)에 저장
- `_save_section_to_db()`: DB에 저장
- `validate_settings()`: 유효성 검증
- `has_changes()`: 변경 감지
- `mark_as_saved()` / `mark_as_changed()`: 변경 플래그 관리

### 2. 2단계 저장 전략
1. **메모리 저장**: `save_settings()` → ConfigManager.config dict 업데이트
2. **DB 저장**: `_save_section_to_db()` → db_manager 메서드 호출

`save_to_db()` 메서드가 위 두 단계를 순차 실행:
```python
def save_to_db(self) -> bool:
    if not self.save_settings():  # 1단계: 메모리
        return False
    return self._save_section_to_db()  # 2단계: DB
```

### 3. 선택적 저장
`SettingsDialog._save_all_settings()`는 변경된 탭만 저장:
```python
changed_tabs = [tab for tab in tabs if tab.has_changes()]
for tab_name, tab in changed_tabs:
    tab.save_to_db()
```

### 4. 변경 감지 메커니즘
- `_original_data`: 로드 시점의 원본 데이터 저장
- `has_changes()`: 현재 UI 값과 원본 비교
- `mark_as_saved()`: 로드/저장 후 플래그 초기화
- `mark_as_changed()`: 위젯 변경 시그널 연결

---

## 이슈 및 개선 사항

### 1. ~~DB 스키마 이슈~~ (해결됨)
- ~~**backup.Des_path**: `destination_path`와 중복으로 보이는 오타 컬럼~~ → **제거 완료**
- ~~**streaming.keepalive_timeout**: DB에는 있으나 UI에 없음 (기본값: 5)~~ → **제거 완료, 코드에서 5초로 하드코딩**

### 2. 데이터 타입 불일치
- **osd_font_color**: UI에서는 RGB 리스트 `[255,255,255]`, DB에서는 문자열 `"255,255,255"`
- **decoder_preference**: UI에서는 리스트, DB에서는 쉼표로 구분된 문자열

### 3. 복잡한 Nested 구조
- **logging**: 4단계 nested dict (console, file, error_log, json_log) → DB는 flat 구조
- **cameras**: 리스트 구조 → DB는 각 카메라가 별도 row

### 4. 기본값 관리
- UI 코드에 하드코딩된 기본값
- DB 스키마의 DEFAULT 값과 불일치 가능성

---

## 권장 사항

### 1. DB 스키마 정리
- `backup.Des_path` 컬럼 삭제 또는 용도 명확화
- `streaming.keepalive_timeout` UI 추가 또는 제거

### 2. 기본값 중앙 관리
```python
# core/defaults.py
DEFAULT_CONFIG = {
    "ui": {"theme": "dark", "show_status_bar": True, ...},
    "streaming": {"default_layout": "1x1", ...},
    ...
}
```

### 3. 데이터 타입 변환 통일
- RGB 리스트 ↔ 문자열 변환 유틸 함수
- decoder_preference 리스트 ↔ 문자열 변환 통일

### 4. 유효성 검증 강화
- 경로 존재/권한 확인 (storage, backup, logging)
- 키 중복 검증 (menu_keys, ptz_keys)
- 임계값 범위 검증 (performance)

---

## 결론
Settings Dialog는 10개 탭을 통해 IT_RNVR.db의 11개 테이블을 효과적으로 관리하고 있습니다. BaseSettingsTab 상속 구조를 통해 일관된 저장/로드/검증 로직을 유지하며, 2단계 저장 전략(메모리 → DB)으로 성능과 안정성을 확보합니다. 다만 일부 DB 스키마 이슈와 데이터 타입 불일치는 개선이 필요합니다.
