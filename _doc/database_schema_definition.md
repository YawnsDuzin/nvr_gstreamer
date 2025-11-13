# IT_RNVR 데이터베이스 테이블 정의서

## 개요
- **데이터베이스명**: IT_RNVR.db
- **DBMS**: SQLite 3
- **용도**: NVR 시스템 설정 정보 저장 (JSON 기반에서 DB 기반으로 마이그레이션)
- **관련 파일**:
  - `core/db_schema.sql` - 스키마 정의
  - `core/db_manager.py` - DB 접근 계층
  - `core/config.py` - 설정 관리 계층 (Singleton)

## 테이블 목록
1. [app](#1-app-테이블) - 애플리케이션 기본 정보
2. [ui](#2-ui-테이블) - UI 설정
3. [streaming](#3-streaming-테이블) - 스트리밍 설정
4. [cameras](#4-cameras-테이블) - 카메라 설정
5. [recording](#5-recording-테이블) - 녹화 설정
6. [backup](#6-backup-테이블) - 백업 설정
7. [storage](#7-storage-테이블) - 저장소 관리 설정
8. [menu_keys](#8-menu_keys-테이블) - 메뉴 단축키 설정
9. [ptz_keys](#9-ptz_keys-테이블) - PTZ 제어 단축키 설정
10. [logging](#10-logging-테이블) - 로깅 설정
11. [performance](#11-performance-테이블) - 성능 모니터링 설정

---

## 1. app 테이블

### 목적
애플리케이션의 기본 정보 및 버전 관리

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| app_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| app_name | TEXT | NO | - | NOT NULL | 애플리케이션 이름 |
| version | TEXT | NO | - | NOT NULL | 애플리케이션 버전 |
| schema_version | INTEGER | YES | 1 | - | 데이터베이스 스키마 버전 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 |
|--------|---------|-------------|
| app_name | 임의의 문자열 | "IT_RNVR" |
| version | 버전 문자열 (예: "1.0.0") | "1.0.0" |
| schema_version | 정수 (1 이상) | 1 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:338-363`)
```python
def get_app_config(self) -> dict:
    # 애플리케이션 기본 정보 조회
    # 반환: {"app_name": "IT_RNVR", "version": "1.0.0"}
```

**쓰기** (`core/db_manager.py:783-818`)
```python
def save_app_config(self, data: dict):
    # 애플리케이션 정보 저장 (UPDATE 또는 INSERT)
    # 단일 레코드만 유지 (LIMIT 1)
```

**사용처** (`core/config.py:96, 161`)
- `ConfigManager.__init__`: AppConfig dataclass로 로드
- `ConfigManager.save_config`: 전체 설정 저장 시 포함

### 비고
- 단일 레코드만 유지 (UPDATE/INSERT 로직에서 LIMIT 1 사용)
- 스키마 버전 관리를 통해 향후 DB 마이그레이션 지원 가능

---

## 2. ui 테이블

### 목적
사용자 인터페이스 설정 및 윈도우 상태 저장

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| ui_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| theme | TEXT | NO | 'dark' | NOT NULL | UI 테마 |
| show_status_bar | BOOLEAN | NO | 1 | NOT NULL | 상태바 표시 여부 |
| fullscreen_on_start | BOOLEAN | NO | 0 | NOT NULL | 시작 시 전체화면 모드 |
| fullscreen_auto_hide_enabled | BOOLEAN | NO | 1 | NOT NULL | 전체화면 자동 UI 숨김 활성화 |
| fullscreen_auto_hide_delay_seconds | INTEGER | NO | 10 | NOT NULL | 자동 UI 숨김 지연 시간 (초) |
| window_state_x | INTEGER | NO | 0 | NOT NULL | 윈도우 X 위치 |
| window_state_y | INTEGER | NO | 0 | NOT NULL | 윈도우 Y 위치 |
| window_state_width | INTEGER | NO | 1920 | NOT NULL | 윈도우 너비 |
| window_state_height | INTEGER | NO | 1080 | NOT NULL | 윈도우 높이 |
| dock_state_camera_visible | BOOLEAN | NO | 1 | NOT NULL | 카메라 독 표시 여부 |
| dock_state_recording_visible | BOOLEAN | NO | 1 | NOT NULL | 녹화 독 표시 여부 |
| dock_state_playback_visible | BOOLEAN | NO | 1 | NOT NULL | 재생 독 표시 여부 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| theme | "dark", "light" | "dark" | UI 테마 선택 |
| show_status_bar | 0 (False), 1 (True) | 1 | 상태바 표시 여부 |
| fullscreen_on_start | 0 (False), 1 (True) | 0 | 시작 시 전체화면 |
| fullscreen_auto_hide_enabled | 0 (False), 1 (True) | 1 | 자동 숨김 기능 |
| fullscreen_auto_hide_delay_seconds | 1 ~ 60 | 10 | 초 단위 |
| window_state_x | 정수 (픽셀) | 0 | 화면 좌표 |
| window_state_y | 정수 (픽셀) | 0 | 화면 좌표 |
| window_state_width | 800 ~ 7680 | 1920 | Full HD 기본 |
| window_state_height | 600 ~ 4320 | 1080 | Full HD 기본 |
| dock_state_camera_visible | 0 (False), 1 (True) | 1 | 카메라 리스트 독 |
| dock_state_recording_visible | 0 (False), 1 (True) | 1 | 녹화 제어 독 |
| dock_state_playback_visible | 0 (False), 1 (True) | 1 | 재생 독 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:365-409`)
```python
def get_ui_config(self) -> dict:
    # UI 설정 조회 (nested 구조로 변환)
    # 반환: {
    #   "theme": "dark",
    #   "window_state": {"x": 0, "y": 0, "width": 1920, "height": 1080},
    #   "dock_state": {"camera_visible": True, ...}
    # }
```

**쓰기** (`core/db_manager.py:820-912`)
```python
def save_ui_config(self, data: dict):
    # nested dict → flat dict 변환 후 저장
    # window_state, dock_state를 개별 컬럼으로 분해
```

**사용처** (`core/config.py`)
- `update_ui_window_state()`: 윈도우 위치/크기 업데이트 (line 416-432)
- `update_ui_dock_state()`: 독 표시 상태 업데이트 (line 434-448)
- `save_ui_config()`: 종료 시 UI 상태 저장 (line 257-274)

**UI 컴포넌트**
- `ui/main_window.py`: 전체화면 모드, 독 표시/숨김, 윈도우 위치 복원
- `ui/settings/basic_settings_tab.py`: 테마 설정, 전체화면 옵션

### 비고
- 단일 레코드만 유지
- window_state, dock_state는 nested dict로 관리되지만 DB에는 flat하게 저장
- 애플리케이션 종료 시 자동 저장 (`MainWindow.closeEvent`)

---

## 3. streaming 테이블

### 목적
RTSP 스트리밍 관련 설정 (OSD, 디코더, 재연결 등)

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| streaming_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| default_layout | TEXT | NO | '1x1' | NOT NULL | 기본 그리드 레이아웃 |
| show_timestamp | BOOLEAN | NO | 1 | NOT NULL | OSD 타임스탬프 표시 |
| show_camera_name | BOOLEAN | NO | 1 | NOT NULL | OSD 카메라 이름 표시 |
| osd_font_size | INTEGER | NO | 14 | NOT NULL | OSD 폰트 크기 |
| osd_font_color | TEXT | NO | '255,255,255' | NOT NULL | OSD 폰트 색상 (CSV: R,G,B) |
| osd_valignment | TEXT | NO | 'top' | NOT NULL | OSD 수직 정렬 |
| osd_halignment | TEXT | NO | 'left' | NOT NULL | OSD 수평 정렬 |
| osd_xpad | INTEGER | NO | 20 | NOT NULL | OSD X 패딩 (픽셀) |
| osd_ypad | INTEGER | NO | 15 | NOT NULL | OSD Y 패딩 (픽셀) |
| use_hardware_acceleration | BOOLEAN | NO | 1 | NOT NULL | 하드웨어 가속 사용 여부 |
| decoder_preference | TEXT | NO | 'avdec_h264,omxh264dec,v4l2h264dec' | NOT NULL | 디코더 우선순위 (CSV) |
| buffer_size | INTEGER | NO | 10485760 | NOT NULL | 버퍼 크기 (바이트) |
| latency_ms | INTEGER | NO | 100 | NOT NULL | 레이턴시 (밀리초) |
| tcp_timeout | INTEGER | NO | 10000 | NOT NULL | TCP 타임아웃 (밀리초) |
| keepalive_timeout | INTEGER | NO | 5 | NOT NULL | Keepalive 타임아웃 (초) |
| connection_timeout | INTEGER | NO | 10 | NOT NULL | 연결 타임아웃 (초) |
| auto_reconnect | BOOLEAN | NO | 1 | NOT NULL | 자동 재연결 활성화 |
| max_reconnect_attempts | INTEGER | NO | 5 | NOT NULL | 최대 재연결 시도 횟수 |
| reconnect_delay_seconds | INTEGER | NO | 5 | NOT NULL | 재연결 지연 시간 (초) |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| default_layout | "1x1", "1x2", "2x2", "3x3", "4x4" 등 | "1x1" | 그리드 레이아웃 (rows x cols) |
| show_timestamp | 0 (False), 1 (True) | 1 | OSD 타임스탬프 |
| show_camera_name | 0 (False), 1 (True) | 1 | OSD 카메라 이름 |
| osd_font_size | 8 ~ 48 | 14 | 폰트 크기 (포인트) |
| osd_font_color | "R,G,B" (0~255) | "255,255,255" | CSV 형식 (흰색) |
| osd_valignment | "top", "center", "bottom" | "top" | 수직 정렬 |
| osd_halignment | "left", "center", "right" | "left" | 수평 정렬 |
| osd_xpad | 0 ~ 100 | 20 | X축 패딩 (픽셀) |
| osd_ypad | 0 ~ 100 | 15 | Y축 패딩 (픽셀) |
| use_hardware_acceleration | 0 (False), 1 (True) | 1 | 하드웨어 가속 |
| decoder_preference | GStreamer 디코더 리스트 (CSV) | "avdec_h264,omxh264dec,v4l2h264dec" | 우선순위 순서대로 시도 |
| buffer_size | 1048576 ~ 104857600 (1MB~100MB) | 10485760 (10MB) | 바이트 단위 |
| latency_ms | 0 ~ 2000 | 100 | 밀리초 (0=최소 레이턴시) |
| tcp_timeout | 1000 ~ 60000 | 10000 | 밀리초 |
| keepalive_timeout | 1 ~ 60 | 5 | 초 단위 |
| connection_timeout | 1 ~ 60 | 10 | 초 단위 |
| auto_reconnect | 0 (False), 1 (True) | 1 | 자동 재연결 |
| max_reconnect_attempts | 1 ~ 100 | 5 | 재연결 시도 횟수 |
| reconnect_delay_seconds | 1 ~ 60 | 5 | 초 단위 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:411-471`)
```python
def get_streaming_config(self) -> dict:
    # 스트리밍 설정 조회 (배열 필드 CSV → list 변환)
    # osd_font_color: "255,255,255" → [255, 255, 255]
    # decoder_preference: "avdec_h264,..." → ["avdec_h264", ...]
```

**쓰기** (`core/db_manager.py:969-1059`)
```python
def save_streaming_config(self, data: dict):
    # 리스트 필드를 CSV 문자열로 변환하여 저장
    # [255, 255, 255] → "255,255,255"
```

**사용처**
- `camera/gst_pipeline.py`: 디코더 선택, 버퍼/타임아웃 설정
- `camera/streaming.py`: 자동 재연결 로직 (max_reconnect_attempts, reconnect_delay_seconds)
- `ui/grid_view.py`: 그리드 레이아웃 설정 (default_layout)
- `ui/settings/streaming_settings_tab.py`: 스트리밍 설정 UI

**GStreamer 파이프라인 적용**
```python
# camera/gst_pipeline.py에서 사용
decoder_preference = config.get_streaming_config()["decoder_preference"]
# ["avdec_h264", "omxh264dec", "v4l2h264dec"] 순서대로 시도

buffer_size = config.get_streaming_config()["buffer_size"]
# rtspsrc buffer-size 속성에 적용
```

### 비고
- CSV 필드 (`osd_font_color`, `decoder_preference`)는 DB에 문자열로 저장되지만 코드에서는 리스트로 변환
- 디코더 우선순위: 소프트웨어 디코더 (avdec_h264) → 하드웨어 디코더 (omxh264dec, v4l2h264dec)
- Raspberry Pi에서 하드웨어 가속 활성화 시 성능 향상 (~50% CPU 절감)

---

## 4. cameras 테이블

### 목적
카메라별 설정 정보 (RTSP URL, PTZ 설정, 영상 변환 등)

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| cameras_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| camera_id | TEXT | NO | - | NOT NULL, UNIQUE | 카메라 고유 ID (예: "cam_01") |
| name | TEXT | NO | - | NOT NULL | 카메라 이름 |
| rtsp_url | TEXT | NO | - | NOT NULL | RTSP 스트림 URL |
| enabled | BOOLEAN | NO | 1 | NOT NULL | 카메라 활성화 여부 |
| username | TEXT | YES | NULL | - | RTSP 인증 사용자명 |
| password | TEXT | YES | NULL | - | RTSP 인증 비밀번호 |
| use_hardware_decode | BOOLEAN | NO | 0 | NOT NULL | 하드웨어 디코딩 사용 여부 |
| streaming_enabled_start | BOOLEAN | NO | 0 | NOT NULL | 시작 시 스트리밍 자동 시작 |
| recording_enabled_start | BOOLEAN | NO | 0 | NOT NULL | 시작 시 녹화 자동 시작 |
| motion_detection | BOOLEAN | NO | 0 | NOT NULL | 모션 감지 활성화 (미구현) |
| ptz_type | TEXT | YES | NULL | - | PTZ 카메라 타입 (예: "HIK", "ONVIF") |
| ptz_port | TEXT | YES | NULL | - | PTZ 제어 포트 |
| ptz_channel | TEXT | YES | NULL | - | PTZ 채널 번호 |
| display_order | INTEGER | NO | 0 | NOT NULL | 화면 표시 순서 |
| video_transform_enabled | BOOLEAN | NO | 0 | NOT NULL | 영상 변환 활성화 |
| video_transform_flip | TEXT | YES | 'none' | - | 영상 반전 설정 |
| video_transform_rotation | INTEGER | YES | 0 | - | 영상 회전 각도 |

### 인덱스
- `idx_cameras_camera_id` ON `camera_id` - 카메라 ID 검색 최적화
- `idx_cameras_enabled` ON `enabled` - 활성화된 카메라 필터링 최적화
- `idx_cameras_display_order` ON `display_order` - 표시 순서 정렬 최적화

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| camera_id | 고유 문자열 (예: "cam_01", "cam_02") | - | UNIQUE 제약 |
| name | 임의의 문자열 | - | 화면 표시용 |
| rtsp_url | RTSP URL (예: "rtsp://192.168.0.100:554/stream1") | - | RTSP 프로토콜 필수 |
| enabled | 0 (False), 1 (True) | 1 | 비활성화 시 연결하지 않음 |
| username | 문자열 또는 NULL | NULL | RTSP 인증 사용자명 |
| password | 문자열 또는 NULL | NULL | **평문 저장 주의** |
| use_hardware_decode | 0 (False), 1 (True) | 0 | Raspberry Pi 전용 |
| streaming_enabled_start | 0 (False), 1 (True) | 0 | 앱 시작 시 자동 스트리밍 |
| recording_enabled_start | 0 (False), 1 (True) | 0 | 앱 시작 시 자동 녹화 |
| motion_detection | 0 (False), 1 (True) | 0 | **현재 미구현** |
| ptz_type | "HIK", "ONVIF", NULL | NULL | PTZ 카메라 제어 타입 |
| ptz_port | 포트 번호 문자열 또는 NULL | NULL | PTZ 제어 포트 |
| ptz_channel | 채널 번호 문자열 또는 NULL | NULL | PTZ 채널 |
| display_order | 정수 (0 이상) | 0 | 그리드 표시 순서 |
| video_transform_enabled | 0 (False), 1 (True) | 0 | 영상 변환 활성화 |
| video_transform_flip | "none", "horizontal", "vertical", "both" | "none" | 영상 반전 방향 |
| video_transform_rotation | 0, 90, 180, 270 | 0 | 영상 회전 각도 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:473-509`)
```python
def get_cameras(self) -> List[dict]:
    # cameras 테이블 전체 조회 (display_order 정렬)
    # video_transform 필드를 nested dict로 변환
    # 반환: [
    #   {
    #     "camera_id": "cam_01",
    #     "video_transform": {"enabled": True, "flip": "vertical", "rotation": 90}
    #   }
    # ]
```

**쓰기** (`core/db_manager.py:914-967`)
```python
def save_cameras(self, cameras: List[dict]):
    # 기존 데이터 전체 삭제 후 새로 INSERT (DELETE + INSERT)
    # video_transform nested dict를 flat 컬럼으로 분해
```

**사용처**
- `camera/streaming.py:CameraStream.__init__`: 카메라 연결 정보 로드
- `camera/gst_pipeline.py:GstPipeline.__init__`: video_transform 설정 적용
- `camera/ptz_controller.py`: PTZ 타입별 컨트롤러 생성
- `ui/camera_list_widget.py`: 카메라 리스트 표시
- `ui/camera_dialog.py`: 카메라 추가/편집 UI

**RTSP URL 예시**
```python
# 기본 형식
rtsp_url = "rtsp://192.168.0.100:554/stream1"

# 인증 포함 (username/password 필드 사용)
# 코드에서 자동으로 URL에 삽입: rtsp://user:pass@192.168.0.100:554/stream1
```

**PTZ 제어 예시**
```python
# camera/ptz_controller.py
if camera.ptz_type == "HIK":
    controller = HikPTZController(camera.rtsp_url, camera.ptz_port, camera.ptz_channel)
elif camera.ptz_type == "ONVIF":
    controller = ONVIFPTZController(camera.rtsp_url, camera.username, camera.password)
```

**영상 변환 예시**
```python
# camera/gst_pipeline.py
if camera.video_transform["enabled"]:
    flip = camera.video_transform["flip"]  # "vertical"
    rotation = camera.video_transform["rotation"]  # 90
    # GStreamer videoflip, videorotate 엘리먼트 추가
```

### 비고
- **보안 주의**: username, password는 평문으로 저장됨 (`CLAUDE.md` Known Limitations 참조)
- video_transform 관련 필드는 nested dict로 관리되지만 DB에는 flat하게 저장
- display_order는 INSERT 시 리스트 인덱스로 자동 설정
- motion_detection은 현재 미구현 상태

---

## 5. recording 테이블

### 목적
녹화 파일 형식 및 자동 분할 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| recording_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| file_format | TEXT | NO | 'mkv' | NOT NULL | 녹화 파일 형식 |
| rotation_minutes | INTEGER | NO | 2 | NOT NULL | 파일 자동 분할 주기 (분) |
| codec | TEXT | NO | 'h264' | NOT NULL | 비디오 코덱 |
| fragment_duration_ms | INTEGER | NO | 1000 | NOT NULL | MP4 fragment 길이 (밀리초) |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| file_format | "mkv", "mp4" | "mkv" | 녹화 파일 컨테이너 형식 |
| rotation_minutes | 1 ~ 60 | 2 | 분 단위 (splitmuxsink max-size-time) |
| codec | "h264", "h265" | "h264" | 비디오 코덱 (현재 h264만 지원) |
| fragment_duration_ms | 500 ~ 5000 | 1000 | 밀리초 (MP4 전용, fragment-based muxing) |

### 코드 사용 용도

**읽기** (`core/db_manager.py:511-540`)
```python
def get_recording_config(self) -> dict:
    # recording 테이블 조회
    # 반환: {"file_format": "mkv", "rotation_minutes": 2, ...}
```

**쓰기** (`core/db_manager.py:1061-1099`)
```python
def save_recording_config(self, data: dict):
    # recording 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `camera/gst_pipeline.py:_create_recording_branch()`: splitmuxsink 설정
  - `file_format`: splitmuxsink location 파일 확장자 결정
  - `rotation_minutes`: splitmuxsink max-size-time 설정 (분 → 나노초 변환)
  - `codec`: h264parse 엘리먼트 사용
  - `fragment_duration_ms`: MP4 muxer fragment-duration 설정

**GStreamer 파이프라인 적용**
```python
# camera/gst_pipeline.py
recording_config = config.get_recording_config()

# splitmuxsink 설정
max_size_time = recording_config["rotation_minutes"] * 60 * 1000000000  # 분 → 나노초
splitmuxsink.set_property("max-size-time", max_size_time)

# 파일명 패턴
file_format = recording_config["file_format"]  # "mkv"
location = f"{camera_id}_%05d.{file_format}"  # cam_01_00001.mkv
```

**파일 구조 예시**
```
recordings/
  cam_01/
    2025-01-13/
      cam_01_20250113_143000.mkv  (2분)
      cam_01_20250113_143200.mkv  (2분)
      cam_01_20250113_143400.mkv  (2분)
```

### 비고
- 단일 레코드만 유지
- splitmuxsink를 사용하여 자동 파일 분할 (수동 rotation 불필요)
- fragment_duration_ms는 MP4 format-location signal에서 사용
- 녹화 파일은 `storage.recording_path` 하위에 저장 (이 테이블이 아님!)

---

## 6. backup 테이블

### 목적
녹화 파일 백업 관련 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| backup_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| destination_path | TEXT | NO | '' | NOT NULL | 백업 대상 경로 |
| delete_after_backup | BOOLEAN | NO | 0 | NOT NULL | 백업 후 원본 삭제 여부 |
| verification | BOOLEAN | NO | 1 | NOT NULL | MD5 해시 검증 여부 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| destination_path | 절대 경로 또는 빈 문자열 | "" | 빈 문자열이면 백업 비활성화 |
| delete_after_backup | 0 (False), 1 (True) | 0 | 백업 성공 후 원본 삭제 |
| verification | 0 (False), 1 (True) | 1 | MD5 해시로 무결성 검증 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:587-614`)
```python
def get_backup_config(self) -> dict:
    # backup 테이블 조회
    # 반환: {"destination_path": "", "delete_after_backup": False, "verification": True}
```

**쓰기** (`core/db_manager.py:1162-1198`)
```python
def save_backup_config(self, data: dict):
    # backup 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `ui/backup_dialog.py:BackupDialog`: 백업 대화상자 (진행률 표시)
  - `destination_path`: 백업 대상 디렉토리
  - `verification`: MD5 해시 검증 수행 여부
  - `delete_after_backup`: 백업 완료 후 원본 파일 삭제
- `ui/settings/backup_settings_tab.py`: 백업 설정 UI

**백업 프로세스**
```python
# ui/backup_dialog.py
1. 원본 파일 복사 → destination_path
2. verification=True인 경우:
   - 원본 파일 MD5 해시 계산
   - 백업 파일 MD5 해시 계산
   - 해시 비교 (불일치 시 실패)
3. delete_after_backup=True인 경우:
   - 검증 성공 후 원본 파일 삭제
```

### 비고
- 단일 레코드만 유지
- destination_path가 빈 문자열이면 백업 기능 비활성화
- MD5 검증은 대용량 파일에서 시간 소요 가능
- 백업은 수동 작업 (자동 백업 미지원)

---

## 7. storage 테이블

### 목적
녹화 파일 저장 경로 및 자동 정리 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| storage_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| recording_path | TEXT | NO | './recordings' | NOT NULL | 녹화 파일 저장 경로 |
| auto_cleanup_enabled | BOOLEAN | NO | 1 | NOT NULL | 자동 정리 활성화 |
| cleanup_interval_hours | INTEGER | NO | 1 | NOT NULL | 정리 작업 실행 주기 (시간) |
| cleanup_on_startup | BOOLEAN | NO | 1 | NOT NULL | 시작 시 정리 작업 실행 |
| min_free_space_gb | REAL | NO | 1.0 | NOT NULL | 최소 여유 공간 (GB) |
| min_free_space_percent | INTEGER | NO | 5 | NOT NULL | 최소 여유 공간 (%) |
| cleanup_threshold_percent | INTEGER | NO | 90 | NOT NULL | 정리 시작 임계값 (%) |
| retention_days | INTEGER | NO | 30 | NOT NULL | 녹화 파일 보관 기간 (일) |
| delete_batch_size | INTEGER | NO | 5 | NOT NULL | 일괄 삭제 파일 수 |
| delete_batch_delay_seconds | INTEGER | NO | 0 | NOT NULL | 일괄 삭제 지연 시간 (초) |
| auto_delete_priority | TEXT | NO | 'oldest_first' | NOT NULL | 자동 삭제 우선순위 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| recording_path | 절대 경로 또는 상대 경로 | "./recordings" | 녹화 파일 저장 위치 |
| auto_cleanup_enabled | 0 (False), 1 (True) | 1 | 자동 정리 활성화 |
| cleanup_interval_hours | 1 ~ 24 | 1 | 시간 단위 |
| cleanup_on_startup | 0 (False), 1 (True) | 1 | 앱 시작 시 정리 실행 |
| min_free_space_gb | 0.1 ~ 1000.0 | 1.0 | GB 단위 (REAL 타입) |
| min_free_space_percent | 1 ~ 50 | 5 | 퍼센트 (%) |
| cleanup_threshold_percent | 50 ~ 99 | 90 | 퍼센트 (%) |
| retention_days | 1 ~ 365 | 30 | 일 단위 |
| delete_batch_size | 1 ~ 100 | 5 | 파일 개수 |
| delete_batch_delay_seconds | 0 ~ 60 | 0 | 초 단위 (0=지연 없음) |
| auto_delete_priority | "oldest_first", "largest_first" | "oldest_first" | 삭제 우선순위 |

### 코드 사용 용도

**읽기** (`core/db_manager.py:542-585`)
```python
def get_storage_config(self) -> dict:
    # storage 테이블 조회
    # 반환: {"recording_path": "./recordings", "auto_cleanup_enabled": True, ...}
```

**쓰기** (`core/db_manager.py:1101-1160`)
```python
def save_storage_config(self, data: dict):
    # storage 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `core/storage.py:StorageService`: 자동 정리 로직
  - `recording_path`: 녹화 파일 디렉토리
  - `auto_cleanup_enabled`: 정리 작업 활성화 여부
  - `cleanup_on_startup`: 앱 시작 시 정리 실행
  - `retention_days`: 이 기간 이상 오래된 파일 삭제
  - `min_free_space_gb`, `min_free_space_percent`: 여유 공간 부족 시 삭제
  - `cleanup_threshold_percent`: 디스크 사용률이 이 값 이상이면 정리
- `camera/gst_pipeline.py:_create_recording_branch()`: 녹화 파일 경로 설정
- `ui/playback_widget.py`: 재생할 파일 스캔

**자동 정리 로직**
```python
# core/storage.py
def auto_cleanup(self):
    if not config["auto_cleanup_enabled"]:
        return

    # 1. retention_days 기준으로 오래된 파일 삭제
    delete_files_older_than(retention_days)

    # 2. 디스크 공간 체크
    disk_usage = get_disk_usage(recording_path)

    # 3. 임계값 초과 시 추가 삭제
    if disk_usage > cleanup_threshold_percent:
        if auto_delete_priority == "oldest_first":
            delete_oldest_files(until_free_space_ok)
        else:
            delete_largest_files(until_free_space_ok)
```

**녹화 파일 경로 구조**
```
{recording_path}/
  {camera_id}/
    {YYYY-MM-DD}/
      {camera_id}_{timestamp}.{file_format}

예시:
./recordings/
  cam_01/
    2025-01-13/
      cam_01_20250113_143000.mkv
```

### 비고
- **CRITICAL**: 2025-11-04 마이그레이션으로 `recording.base_path` → `storage.recording_path`로 이동
- 단일 레코드만 유지
- auto_delete_priority는 현재 "oldest_first"만 지원 ("largest_first"는 미구현)
- delete_batch_delay_seconds는 I/O 부하 분산용 (기본값 0=즉시 삭제)

---

## 8. menu_keys 테이블

### 목적
메뉴 기능 단축키 매핑 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| menu_keys_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| camera_connect | TEXT | NO | 'F1' | NOT NULL | 카메라 연결 |
| camera_stop | TEXT | NO | 'F2' | NOT NULL | 카메라 중지 |
| prev_group | TEXT | NO | 'N' | NOT NULL | 이전 그룹 |
| camera_connect_all | TEXT | NO | 'F3' | NOT NULL | 모든 카메라 연결 |
| camera_stop_all | TEXT | NO | 'F4' | NOT NULL | 모든 카메라 중지 |
| next_group | TEXT | NO | 'M' | NOT NULL | 다음 그룹 |
| prev_config | TEXT | NO | 'F5' | NOT NULL | 이전 설정 |
| record_start | TEXT | NO | 'F7' | NOT NULL | 녹화 시작 |
| screen_rotate | TEXT | NO | 'F9' | NOT NULL | 화면 회전 |
| next_config | TEXT | NO | 'F6' | NOT NULL | 다음 설정 |
| record_stop | TEXT | NO | 'F8' | NOT NULL | 녹화 중지 |
| screen_flip | TEXT | NO | 'F10' | NOT NULL | 화면 반전 |
| screen_hide | TEXT | NO | 'Esc' | NOT NULL | 화면 숨김 (전체화면 토글) |
| menu_open | TEXT | NO | 'F11' | NOT NULL | 메뉴 열기 |
| program_exit | TEXT | NO | 'F12' | NOT NULL | 프로그램 종료 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 기능 설명 |
|--------|---------|-------------|-----------|
| camera_connect | Qt 키 문자열 | "F1" | 선택된 카메라 연결 |
| camera_stop | Qt 키 문자열 | "F2" | 선택된 카메라 중지 |
| prev_group | Qt 키 문자열 | "N" | 이전 카메라 그룹 전환 |
| camera_connect_all | Qt 키 문자열 | "F3" | 모든 카메라 연결 |
| camera_stop_all | Qt 키 문자열 | "F4" | 모든 카메라 중지 |
| next_group | Qt 키 문자열 | "M" | 다음 카메라 그룹 전환 |
| prev_config | Qt 키 문자열 | "F5" | 이전 설정으로 전환 |
| record_start | Qt 키 문자열 | "F7" | 녹화 시작 |
| screen_rotate | Qt 키 문자열 | "F9" | 화면 회전 |
| next_config | Qt 키 문자열 | "F6" | 다음 설정으로 전환 |
| record_stop | Qt 키 문자열 | "F8" | 녹화 중지 |
| screen_flip | Qt 키 문자열 | "F10" | 화면 반전 |
| screen_hide | Qt 키 문자열 | "Esc" | 전체화면 모드 UI 숨김/표시 |
| menu_open | Qt 키 문자열 | "F11" | 설정 메뉴 열기 |
| program_exit | Qt 키 문자열 | "F12" | 프로그램 종료 |

**사용 가능한 키 문자열 예시**
- 기능키: "F1" ~ "F12"
- 일반키: "A" ~ "Z", "0" ~ "9"
- 특수키: "Esc", "Space", "Enter", "Tab"
- 조합키: "Ctrl+S", "Shift+A", "Alt+F4"

### 코드 사용 용도

**읽기** (`core/db_manager.py:616-653`)
```python
def get_menu_keys(self) -> dict:
    # menu_keys 테이블 조회 (menu_keys_idx 제외)
    # 반환: {"camera_connect": "F1", "camera_stop": "F2", ...}
```

**쓰기** (`core/db_manager.py:1200-1269`)
```python
def save_menu_keys(self, data: dict):
    # menu_keys 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `ui/main_window.py:keyPressEvent()`: 키보드 이벤트 처리
  - EventFilter를 QApplication에 설치하여 전역 키 이벤트 캡처
  - menu_keys 딕셔너리에서 키 매핑 조회
  - 해당 기능 실행

**키 이벤트 처리 예시**
```python
# ui/main_window.py
def keyPressEvent(self, event):
    key_text = event.text().upper()
    menu_keys = config.get_menu_keys()

    if key_text == menu_keys["camera_connect"]:  # "F1"
        self.connect_selected_camera()
    elif key_text == menu_keys["record_start"]:  # "F7"
        self.start_recording()
    elif key_text == menu_keys["program_exit"]:  # "F12"
        self.close()
```

**EventFilter 설치** (2025-11-12 수정)
```python
# ui/main_window.py:_setup_fullscreen_ui()
app = QApplication.instance()
app.installEventFilter(self)  # 전역 키 이벤트 캡처

# eventFilter() 메서드에서 키 이벤트 처리
def eventFilter(self, obj, event):
    if event.type() == QEvent.KeyPress:
        self.keyPressEvent(event)
        return True
    return False
```

### 비고
- 단일 레코드만 유지
- 키 중복 체크는 UI에서 수행 (DB 제약조건 없음)
- 2025-11-12 PTZ 키 이벤트 픽스: EventFilter를 QApplication에 설치하여 모든 키 이벤트 캡처

---

## 9. ptz_keys 테이블

### 목적
PTZ 카메라 제어 단축키 매핑 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| ptz_keys_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| pan_left | TEXT | NO | 'Q' | NOT NULL | 팬 왼쪽 |
| up | TEXT | NO | 'W' | NOT NULL | 틸트 위 |
| right_up | TEXT | NO | 'E' | NOT NULL | 팬/틸트 오른쪽 위 |
| left | TEXT | NO | 'A' | NOT NULL | 팬 왼쪽 |
| stop | TEXT | NO | 'S' | NOT NULL | PTZ 정지 |
| right | TEXT | NO | 'D' | NOT NULL | 팬 오른쪽 |
| pan_down | TEXT | NO | 'Z' | NOT NULL | 팬 아래 |
| down | TEXT | NO | 'X' | NOT NULL | 틸트 아래 |
| right_down | TEXT | NO | 'C' | NOT NULL | 팬/틸트 오른쪽 아래 |
| zoom_in | TEXT | NO | 'V' | NOT NULL | 줌 인 |
| zoom_out | TEXT | NO | 'B' | NOT NULL | 줌 아웃 |
| ptz_speed_up | TEXT | NO | 'R' | NOT NULL | PTZ 속도 증가 |
| ptz_speed_down | TEXT | NO | 'T' | NOT NULL | PTZ 속도 감소 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | PTZ 동작 |
|--------|---------|-------------|----------|
| pan_left | Qt 키 문자열 | "Q" | 카메라 좌측으로 회전 |
| up | Qt 키 문자열 | "W" | 카메라 위로 회전 |
| right_up | Qt 키 문자열 | "E" | 카메라 우측 상단으로 회전 |
| left | Qt 키 문자열 | "A" | 카메라 좌측으로 회전 (pan_left와 동일) |
| stop | Qt 키 문자열 | "S" | PTZ 동작 정지 |
| right | Qt 키 문자열 | "D" | 카메라 우측으로 회전 |
| pan_down | Qt 키 문자열 | "Z" | 카메라 아래로 회전 |
| down | Qt 키 문자열 | "X" | 카메라 아래로 회전 (pan_down과 동일) |
| right_down | Qt 키 문자열 | "C" | 카메라 우측 하단으로 회전 |
| zoom_in | Qt 키 문자열 | "V" | 줌 인 (확대) |
| zoom_out | Qt 키 문자열 | "B" | 줌 아웃 (축소) |
| ptz_speed_up | Qt 키 문자열 | "R" | PTZ 이동 속도 증가 |
| ptz_speed_down | Qt 키 문자열 | "T" | PTZ 이동 속도 감소 |

**키 레이아웃 (QWERTY 기준)**
```
Q(좌상)  W(위)  E(우상)    R(속도+)  T(속도-)
A(좌)    S(정지) D(우)
Z(좌하)  X(아래) C(우하)    V(줌+)   B(줌-)
```

### 코드 사용 용도

**읽기** (`core/db_manager.py:655-690`)
```python
def get_ptz_keys(self) -> dict:
    # ptz_keys 테이블 조회 (ptz_keys_idx 제외)
    # 반환: {"pan_left": "Q", "up": "W", ...}
```

**쓰기** (`core/db_manager.py:1271-1332`)
```python
def save_ptz_keys(self, data: dict):
    # ptz_keys 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `ui/main_window.py:keyPressEvent(), keyReleaseEvent()`: PTZ 키 이벤트 처리
  - 카메라 선택 후 PTZ 키 입력 시 PTZController 호출
  - keyPress: PTZ 동작 시작
  - keyRelease: PTZ 동작 정지

**PTZ 제어 흐름**
```python
# ui/main_window.py
def keyPressEvent(self, event):
    if not self.selected_camera:
        return  # 카메라 선택 필요

    if not self.ptz_controller:
        self.ptz_controller = create_ptz_controller(self.selected_camera)

    key_text = event.text().upper()
    ptz_keys = config.get_ptz_keys()

    if key_text == ptz_keys["zoom_in"]:  # "V"
        self.ptz_controller.zoom_in(speed=self.ptz_speed)
    elif key_text == ptz_keys["pan_left"]:  # "Q"
        self.ptz_controller.pan_left(speed=self.ptz_speed)
    ...

def keyReleaseEvent(self, event):
    if key_text == ptz_keys["stop"]:  # "S"
        self.ptz_controller.stop()
```

**PTZ Controller 예시** (`camera/ptz_controller.py`)
```python
class HikPTZController:
    def zoom_in(self, speed=1):
        # HIK 프로토콜로 줌 인 명령 전송

class ONVIFPTZController:
    def pan_left(self, speed=1):
        # ONVIF 프로토콜로 팬 왼쪽 명령 전송
```

### 비고
- 단일 레코드만 유지
- PTZ 제어는 카메라 선택 후에만 동작
- PTZ 타입 (HIK, ONVIF)에 따라 다른 컨트롤러 사용
- 2025-11-12 픽스: EventFilter를 QApplication에 설치하여 키 이벤트가 MainWindow에 도달하도록 수정
- 관련 문서: `_doc/ptz_zoom_keypress_issue_analysis_20251112.md`

---

## 10. logging 테이블

### 목적
로깅 시스템 설정 (콘솔, 파일, 에러 로그, JSON 로그)

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| logging_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| enabled | BOOLEAN | NO | 1 | NOT NULL | 로깅 활성화 |
| log_path | TEXT | NO | './logs' | NOT NULL | 로그 파일 저장 경로 |
| console_enabled | BOOLEAN | NO | 1 | NOT NULL | 콘솔 로그 활성화 |
| console_level | TEXT | NO | 'DEBUG' | NOT NULL | 콘솔 로그 레벨 |
| console_colorize | BOOLEAN | NO | 1 | NOT NULL | 콘솔 로그 색상 활성화 |
| console_format | TEXT | NO | (기본 포맷) | NOT NULL | 콘솔 로그 포맷 |
| file_enabled | BOOLEAN | NO | 1 | NOT NULL | 파일 로그 활성화 |
| file_level | TEXT | NO | 'DEBUG' | NOT NULL | 파일 로그 레벨 |
| file_filename | TEXT | NO | 'pynvr_{time:YYYY-MM-DD}.log' | NOT NULL | 파일 로그 이름 패턴 |
| file_format | TEXT | NO | (기본 포맷) | NOT NULL | 파일 로그 포맷 |
| file_rotation | TEXT | NO | '1 day' | NOT NULL | 파일 로그 로테이션 주기 |
| file_retention | TEXT | NO | '7 days' | NOT NULL | 파일 로그 보관 기간 |
| file_compression | TEXT | NO | 'zip' | NOT NULL | 압축 형식 |
| file_max_size_mb | INTEGER | NO | 100 | NOT NULL | 파일 최대 크기 (MB) |
| file_rotation_count | INTEGER | NO | 10 | NOT NULL | 로테이션 파일 개수 |
| error_log_enabled | BOOLEAN | NO | 1 | NOT NULL | 에러 로그 활성화 |
| error_log_filename | TEXT | NO | 'pynvr_errors_{time:YYYY-MM-DD}.log' | NOT NULL | 에러 로그 이름 패턴 |
| error_log_level | TEXT | NO | 'ERROR' | NOT NULL | 에러 로그 레벨 |
| error_log_rotation | TEXT | NO | '10 MB' | NOT NULL | 에러 로그 로테이션 |
| error_log_retention | TEXT | NO | '30 days' | NOT NULL | 에러 로그 보관 기간 |
| json_log_enabled | BOOLEAN | NO | 0 | NOT NULL | JSON 로그 활성화 |
| json_log_filename | TEXT | NO | 'pynvr_{time:YYYY-MM-DD}.json' | NOT NULL | JSON 로그 이름 패턴 |
| json_log_serialize | BOOLEAN | NO | 1 | NOT NULL | JSON 직렬화 여부 |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| enabled | 0 (False), 1 (True) | 1 | 전체 로깅 활성화 |
| log_path | 절대 경로 또는 상대 경로 | "./logs" | 로그 파일 저장 위치 |
| console_enabled | 0 (False), 1 (True) | 1 | 콘솔 로그 출력 |
| console_level | "TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL" | "DEBUG" | loguru 로그 레벨 |
| console_colorize | 0 (False), 1 (True) | 1 | ANSI 색상 코드 사용 |
| console_format | loguru 포맷 문자열 | (기본 포맷) | loguru 포맷 문법 |
| file_enabled | 0 (False), 1 (True) | 1 | 파일 로그 활성화 |
| file_level | "TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL" | "DEBUG" | loguru 로그 레벨 |
| file_filename | 파일명 패턴 (loguru time 지원) | "pynvr_{time:YYYY-MM-DD}.log" | loguru time 포맷 |
| file_format | loguru 포맷 문자열 | (기본 포맷) | loguru 포맷 문법 |
| file_rotation | "크기" 또는 "시간" | "1 day" | 예: "100 MB", "1 week" |
| file_retention | "시간" | "7 days" | 예: "10 days", "1 month" |
| file_compression | "zip", "gz", "bz2", "xz" | "zip" | 압축 형식 |
| file_max_size_mb | 1 ~ 1000 | 100 | MB 단위 (미사용) |
| file_rotation_count | 1 ~ 100 | 10 | 최대 파일 개수 (미사용) |
| error_log_enabled | 0 (False), 1 (True) | 1 | 에러 전용 로그 |
| error_log_filename | 파일명 패턴 | "pynvr_errors_{time:YYYY-MM-DD}.log" | 에러만 별도 기록 |
| error_log_level | "ERROR", "CRITICAL" | "ERROR" | 에러 레벨 이상만 |
| error_log_rotation | "크기" 또는 "시간" | "10 MB" | loguru rotation 문법 |
| error_log_retention | "시간" | "30 days" | loguru retention 문법 |
| json_log_enabled | 0 (False), 1 (True) | 0 | JSON 형식 로그 |
| json_log_filename | 파일명 패턴 | "pynvr_{time:YYYY-MM-DD}.json" | JSON 로그 파일 |
| json_log_serialize | 0 (False), 1 (True) | 1 | loguru serialize 옵션 |

**기본 포맷**
- console_format: `<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>`
- file_format: `{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}`

### 코드 사용 용도

**읽기** (`core/db_manager.py:692-744`)
```python
def get_logging_config(self) -> dict:
    # logging 테이블 조회 (nested 구조로 변환)
    # 반환: {
    #   "enabled": True,
    #   "log_path": "./logs",
    #   "console": {"enabled": True, "level": "DEBUG", ...},
    #   "file": {"enabled": True, "level": "DEBUG", ...},
    #   "error_log": {...},
    #   "json_log": {...}
    # }
```

**쓰기** (`core/db_manager.py:1334-1426`)
```python
def save_logging_config(self, data: dict):
    # nested dict → flat dict 변환 후 저장
    # console, file, error_log, json_log를 개별 컬럼으로 분해
```

**사용처**
- `main.py:setup_logging()`: 로깅 시스템 초기화
  - loguru logger 설정
  - 콘솔, 파일, 에러, JSON 로그 핸들러 추가
- `ui/log_viewer_dialog.py`: 실시간 로그 뷰어
- `ui/settings/logging_settings_tab.py`: 로깅 설정 UI

**로깅 시스템 초기화 예시**
```python
# main.py
from loguru import logger

def setup_logging():
    logging_config = config.get_logging_config()

    logger.remove()  # 기본 핸들러 제거

    # 콘솔 로그
    if logging_config["console"]["enabled"]:
        logger.add(
            sys.stderr,
            level=logging_config["console"]["level"],
            format=logging_config["console"]["format"],
            colorize=logging_config["console"]["colorize"]
        )

    # 파일 로그
    if logging_config["file"]["enabled"]:
        logger.add(
            f"{logging_config['log_path']}/{logging_config['file']['filename']}",
            level=logging_config["file"]["level"],
            format=logging_config["file"]["format"],
            rotation=logging_config["file"]["rotation"],
            retention=logging_config["file"]["retention"],
            compression=logging_config["file"]["compression"]
        )

    # 에러 로그 (별도 파일)
    if logging_config["error_log"]["enabled"]:
        logger.add(
            f"{logging_config['log_path']}/{logging_config['error_log']['filename']}",
            level=logging_config["error_log"]["level"],
            rotation=logging_config["error_log"]["rotation"],
            retention=logging_config["error_log"]["retention"]
        )
```

### 비고
- 단일 레코드만 유지
- loguru 라이브러리 기반 (Python logging 모듈 아님)
- console, file, error_log, json_log는 nested dict로 관리되지만 DB에는 flat하게 저장
- file_max_size_mb, file_rotation_count는 현재 미사용 (loguru rotation 문법 사용)
- JSON 로그는 기본 비활성화 (성능 영향)

---

## 11. performance 테이블

### 목적
시스템 성능 모니터링 임계값 설정

### 테이블 구조

| 컬럼명 | 데이터 타입 | Nullable | 기본값 | 제약조건 | 설명 |
|--------|-------------|----------|--------|----------|------|
| performance_idx | INTEGER | NO | - | PRIMARY KEY AUTOINCREMENT | 레코드 고유 ID |
| alert_enabled | BOOLEAN | NO | 0 | NOT NULL | 알림 활성화 |
| alert_warning_check_interval_seconds | INTEGER | NO | 30 | NOT NULL | 경고 알림 체크 주기 (초) |
| alert_critical_check_interval_seconds | INTEGER | NO | 15 | NOT NULL | 심각 알림 체크 주기 (초) |
| max_cpu_percent | INTEGER | NO | 80 | NOT NULL | CPU 사용률 임계값 (%) |
| max_memory_mb | INTEGER | NO | 6144 | NOT NULL | 메모리 사용량 임계값 (MB) |
| max_temp | INTEGER | NO | 71 | NOT NULL | 온도 임계값 (℃) |

### 설정 가능한 값

| 컬럼명 | 값 범위 | 현재 기본값 | 비고 |
|--------|---------|-------------|------|
| alert_enabled | 0 (False), 1 (True) | 0 | 알림 기능 활성화 (기본 비활성화) |
| alert_warning_check_interval_seconds | 10 ~ 300 | 30 | 경고 레벨 체크 주기 (초) |
| alert_critical_check_interval_seconds | 5 ~ 60 | 15 | 심각 레벨 체크 주기 (초) |
| max_cpu_percent | 50 ~ 100 | 80 | CPU 사용률 퍼센트 (%) |
| max_memory_mb | 512 ~ 32768 | 6144 | 메모리 사용량 (MB, 6GB) |
| max_temp | 50 ~ 90 | 71 | 온도 (℃, Raspberry Pi 기준) |

### 코드 사용 용도

**읽기** (`core/db_manager.py:746-779`)
```python
def get_performance_config(self) -> dict:
    # performance 테이블 조회
    # 반환: {
    #   "alert_enabled": False,
    #   "max_cpu_percent": 80,
    #   "max_memory_mb": 6144,
    #   ...
    # }
```

**쓰기** (`core/db_manager.py:1428-1475`)
```python
def save_performance_config(self, data: dict):
    # performance 설정 저장 (UPDATE 또는 INSERT)
```

**사용처**
- `core/system_monitor.py:SystemMonitor`: 시스템 리소스 모니터링
  - CPU, 메모리, 온도 체크
  - 임계값 초과 시 알림 (alert_enabled=True인 경우)
- `ui/settings/performance_settings_tab.py`: 성능 설정 UI
- `ui/main_window.py`: 상태바에 시스템 리소스 표시

**모니터링 로직 예시**
```python
# core/system_monitor.py
class SystemMonitor:
    def check_resources(self):
        perf_config = config.get_performance_config()

        if not perf_config["alert_enabled"]:
            return

        # CPU 체크
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > perf_config["max_cpu_percent"]:
            logger.warning(f"CPU usage high: {cpu_percent}%")

        # 메모리 체크
        memory_mb = psutil.virtual_memory().used / 1024 / 1024
        if memory_mb > perf_config["max_memory_mb"]:
            logger.warning(f"Memory usage high: {memory_mb:.0f} MB")

        # 온도 체크 (Raspberry Pi)
        temp = self.get_cpu_temperature()
        if temp and temp > perf_config["max_temp"]:
            logger.critical(f"Temperature high: {temp}℃")
```

**알림 체크 주기**
- 경고 레벨 (warning): 30초마다 체크
- 심각 레벨 (critical): 15초마다 체크
- 임계값 초과 시 로그 기록

### 비고
- 단일 레코드만 유지
- alert_enabled는 기본 비활성화 (성능 영향 최소화)
- Raspberry Pi에서 온도 모니터링 중요 (과열 방지)
- max_memory_mb 기본값 6144MB (6GB)는 Raspberry Pi 4 (8GB 모델) 기준

---

## 인덱스 정보

### cameras 테이블 인덱스
- `idx_cameras_camera_id` ON `camera_id`
  - **용도**: 카메라 ID로 빠른 검색
  - **쿼리**: `SELECT * FROM cameras WHERE camera_id = ?`

- `idx_cameras_enabled` ON `enabled`
  - **용도**: 활성화된 카메라만 필터링
  - **쿼리**: `SELECT * FROM cameras WHERE enabled = 1`

- `idx_cameras_display_order` ON `display_order`
  - **용도**: 화면 표시 순서 정렬
  - **쿼리**: `SELECT * FROM cameras ORDER BY display_order`

---

## 데이터베이스 설계 특징

### 1. 단일 레코드 패턴
대부분의 설정 테이블은 단일 레코드만 유지:
- app, ui, streaming, recording, backup, storage, menu_keys, ptz_keys, logging, performance
- UPDATE/INSERT 로직에서 `LIMIT 1` 사용
- cameras 테이블만 다중 레코드 허용

### 2. Nested → Flat 변환
코드에서는 nested dict로 관리하지만 DB에는 flat하게 저장:
- `ui.window_state` → `window_state_x`, `window_state_y`, `window_state_width`, `window_state_height`
- `ui.dock_state` → `dock_state_camera_visible`, `dock_state_recording_visible`, `dock_state_playback_visible`
- `cameras.video_transform` → `video_transform_enabled`, `video_transform_flip`, `video_transform_rotation`
- `logging` → `console_*`, `file_*`, `error_log_*`, `json_log_*`

### 3. CSV 필드
배열 데이터는 CSV 문자열로 저장:
- `streaming.osd_font_color`: `"255,255,255"` (코드에서 `[255, 255, 255]`)
- `streaming.decoder_preference`: `"avdec_h264,omxh264dec,v4l2h264dec"` (코드에서 리스트)

### 4. BOOLEAN 타입
SQLite는 BOOLEAN을 INTEGER (0/1)로 저장:
- 0 = False
- 1 = True
- Python 코드에서 `bool()` 변환 필요

### 5. WAL 모드
데이터베이스 성능 최적화:
- `PRAGMA journal_mode=WAL`: 읽기/쓰기 동시 처리
- `PRAGMA synchronous=NORMAL`: WAL 모드에서 성능 최적화
- 멀티스레드 안전성: `RLock` 사용

---

## JSON 마이그레이션 정보

### 마이그레이션 경로
- **이전**: `IT_RNVR.json` (JSON 파일)
- **현재**: `IT_RNVR.db` (SQLite 데이터베이스)
- **마이그레이션 일자**: 2025-11

### 마이그레이션 메서드
`core/db_manager.py:migrate_from_json(json_path)`
- JSON 파일 읽기
- 트랜잭션으로 전체 데이터 저장
- JSON 파일 백업 (`.json.backup`)

### 백업 정책
- 마이그레이션 시 기존 JSON 파일 자동 백업
- 백업 파일명: `IT_RNVR.json.backup` (또는 타임스탬프 추가)

---

## 관련 문서

- `_doc/db_migration_complete.md` - JSON to SQLite 마이그레이션 완료 보고서
- `core/db_schema.sql` - 데이터베이스 스키마 정의
- `core/db_manager.py` - 데이터베이스 접근 계층
- `core/config.py` - 설정 관리 계층 (Singleton)
- `CLAUDE.md` - 프로젝트 전체 가이드 (Configuration System 섹션)

---

**문서 생성일**: 2025-01-13
**데이터베이스 버전**: 1.0 (schema_version: 1)
**작성자**: Claude Code
