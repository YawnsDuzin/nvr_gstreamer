# IT_RNVR.json 설정 파일 문서

## 개요
IT_RNVR 시스템의 전체 설정을 관리하는 JSON 형식 설정 파일입니다.

---

## 📋 설정 항목

### 1. app (애플리케이션 기본 정보)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `app_name` | string | "IT_RNVR" | 애플리케이션 이름 |
| `version` | string | "1.0.0" | 애플리케이션 버전 |

**사용 위치**: `config_manager.py`

---

### 2. ui (사용자 인터페이스 설정)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `theme` | string | "dark" | UI 테마 (dark/light) |
| `show_status_bar` | boolean | true | 상태바 표시 여부 |
| `fullscreen_on_start` | boolean | false | 시작 시 전체화면 모드 |
| `window_state.x` | number | 0 | 창 X 좌표 (자동 저장) |
| `window_state.y` | number | 0 | 창 Y 좌표 (자동 저장) |
| `window_state.width` | number | 1920 | 창 너비 (자동 저장) |
| `window_state.height` | number | 1080 | 창 높이 (자동 저장) |
| `dock_state.camera_visible` | boolean | true | 카메라 도크 표시 (자동 저장) |
| `dock_state.recording_visible` | boolean | true | 녹화 도크 표시 (자동 저장) |
| `dock_state.playback_visible` | boolean | false | 재생 도크 표시 (자동 저장) |

**사용 위치**: `main_window.py`, `config_manager.py`
**주의**: 프로그램 종료 시 자동으로 현재 창 상태가 저장됩니다.

---

### 3. streaming (스트리밍 설정)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `default_layout` | string | "1x1" | 그리드 레이아웃 (1x1~4x4) |
| `show_timestamp` | boolean | true | 타임스탬프 오버레이 표시 |
| `show_camera_name` | boolean | true | 카메라 이름 오버레이 표시 |
| `osd_font_size` | number | 14 | OSD 폰트 크기 |
| `osd_font_color` | array | [255,255,255] | OSD 폰트 색상 (RGB) |
| `osd_valignment` | string | "top" | OSD 수직 정렬 (top/bottom) |
| `osd_halignment` | string | "left" | OSD 수평 정렬 (left/right) |
| `osd_xpad` | number | 20 | OSD 좌우 여백 (픽셀) |
| `osd_ypad` | number | 15 | OSD 상하 여백 (픽셀) |
| `use_hardware_acceleration` | boolean | true | 하드웨어 가속 사용 여부 |
| `decoder_preference` | array | [...] | 디코더 우선순위 목록 |
| `buffer_size` | number | 10485760 | 스트림 버퍼 크기 (바이트) |
| `latency_ms` | number | 200 | RTSP 지연시간 (밀리초) |
| `tcp_timeout` | number | 10000 | TCP 타임아웃 (밀리초) |
| `auto_reconnect` | boolean | true | 자동 재연결 활성화 |
| `max_reconnect_attempts` | number | 5 | 최대 재연결 시도 횟수 |
| `reconnect_delay_seconds` | number | 5 | 재연결 대기 시간 (초) |
| `connection_timeout` | number | 10 | 연결 타임아웃 (초) |

**사용 위치**: `gst_pipeline.py`, `camera_stream.py`

---

### 4. cameras (카메라 설정)

각 카메라별 설정 배열입니다.

| 항목 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `camera_id` | string | ✓ | 카메라 고유 ID |
| `name` | string | ✓ | 카메라 표시 이름 |
| `rtsp_url` | string | ✓ | RTSP 스트림 URL |
| `enabled` | boolean |  | 카메라 활성화 여부 |
| `username` | string |  | RTSP 인증 사용자명 |
| `password` | string |  | RTSP 인증 비밀번호 |
| `streaming_enabled_start` | boolean |  | 시작 시 스트리밍 자동 연결 |
| `recording_enabled_start` | boolean |  | 연결 시 녹화 자동 시작 |

**사용 위치**: `config_manager.py`, `camera_service.py`, `main_window.py`

**예시**:
```json
{
  "camera_id": "cam_01",
  "name": "Main Camera",
  "rtsp_url": "rtsp://admin:password@192.168.0.131:554/stream",
  "enabled": true,
  "streaming_enabled_start": true,
  "recording_enabled_start": true
}
```

---

### 5. recording (녹화 설정)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `base_path` | string | "./recordings" | 녹화 파일 저장 경로 |
| `file_format` | string | "mp4" | 컨테이너 포맷 (mp4/mkv/avi) |
| `rotation_minutes` | number | 10 | 파일 분할 주기 (분) |
| `retention_days` | number | 30 | 파일 보관 기간 (일) |
| `codec` | string | "h264" | 비디오 코덱 (h264/h265) |
| `fragment_duration_ms` | number | 1000 | MP4 fragment 크기 (ms) |

**사용 위치**:
- `gst_pipeline.py`: 녹화 파이프라인 생성
- `recording_manager.py`: 녹화 파일 관리
- `playback_manager.py`: 재생 파일 스캔
- `storage_service.py`: 스토리지 관리

**파일 포맷별 특징**:
- **mp4**: 범용성 최고, 웹 스트리밍 최적화
- **mkv**: 오픈소스, 메타데이터 풍부
- **avi**: 레거시 호환성

**코덱별 특징**:
- **h264**: 최대 호환성, 낮은 CPU 사용량
- **h265**: 50% 저장공간 절감, 높은 CPU 사용량

---

### 6. logging (로깅 설정)

#### 6.1 기본 설정

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | true | 로깅 시스템 활성화 |
| `log_path` | string | "./logs" | 로그 파일 저장 경로 |

#### 6.2 콘솔 로그 (console)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | true | 콘솔 로그 출력 활성화 |
| `level` | string | "INFO" | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |
| `colorize` | boolean | true | 컬러 출력 사용 |
| `format` | string | ... | 로그 출력 포맷 |

#### 6.3 파일 로그 (file)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | true | 파일 로그 활성화 |
| `level` | string | "DEBUG" | 파일 로그 레벨 |
| `filename` | string | "pynvr_{time}.log" | 로그 파일명 패턴 |
| `format` | string | ... | 파일 로그 포맷 |
| `rotation` | string | "1 day" | 로그 파일 회전 주기 |
| `retention` | string | "7 days" | 로그 파일 보관 기간 |
| `compression` | string | "zip" | 로그 파일 압축 방식 |
| `max_size_mb` | number | 100 | 로그 파일 최대 크기 (MB) |
| `rotation_count` | number | 10 | 최대 로그 파일 개수 |

#### 6.4 에러 로그 (error_log)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | true | 에러 전용 로그 활성화 |
| `filename` | string | "pynvr_errors_{time}.log" | 에러 로그 파일명 |
| `level` | string | "ERROR" | 에러 로그 레벨 |
| `rotation` | string | "10 MB" | 파일 크기 기반 회전 |
| `retention` | string | "30 days" | 에러 로그 보관 기간 |

#### 6.5 JSON 로그 (json_log)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | false | JSON 형식 로그 활성화 |
| `filename` | string | "pynvr_{time}.json" | JSON 로그 파일명 |
| `serialize` | boolean | true | 객체 직렬화 사용 |

**사용 위치**: `main.py` (loguru 설정)

---

### 7. performance (성능 설정)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `max_cpu_percent` | number | 80 | 최대 CPU 사용률 (%) |
| `max_memory_mb` | number | 2048 | 최대 메모리 사용량 (MB) |
| `pipeline_queue_size` | number | 200 | 파이프라인 큐 크기 |
| `max_dropped_frames` | number | 10 | 최대 프레임 드롭 허용치 |
| `enable_gpu` | boolean | true | GPU 사용 활성화 |
| `gpu_device` | string | "/dev/dri/renderD128" | GPU 디바이스 경로 (Linux) |

**사용 위치**: `system_monitor.py`
**참고**: 현재 모니터링 용도로 사용, 제한 기능은 미구현

---

### 8. security (보안 설정)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `require_authentication` | boolean | false | 인증 요구 활성화 |
| `session_timeout_minutes` | number | 60 | 세션 타임아웃 (분) |
| `max_login_attempts` | number | 3 | 최대 로그인 시도 횟수 |
| `password_min_length` | number | 8 | 최소 비밀번호 길이 |
| `enable_ssl` | boolean | false | SSL/TLS 활성화 |
| `ssl_cert_path` | string | "" | SSL 인증서 경로 |
| `ssl_key_path` | string | "" | SSL 키 파일 경로 |

**사용 위치**: 미구현 (향후 웹 인터페이스용)
**참고**: 현재 버전에서는 사용되지 않음

---

## 🔧 설정 변경 방법

### 1. 파일 직접 수정
```bash
# 텍스트 에디터로 열기
notepad IT_RNVR.json  # Windows
nano IT_RNVR.json     # Linux
```

### 2. 프로그램 재시작
설정 변경 후 프로그램을 재시작해야 적용됩니다.

### 3. 주의사항
- JSON 형식을 정확히 지켜야 합니다 (쉼표, 따옴표 등)
- UI 설정은 프로그램 종료 시 자동 저장되므로 수동 수정하지 마세요
- 잘못된 설정 시 기본값으로 대체됩니다

---

## 📂 파일 구조 예시

### 녹화 파일 저장 구조
```
./recordings/
├── cam_01/
│   ├── 20251027/
│   │   ├── cam_01_20251027_140000.mp4
│   │   ├── cam_01_20251027_141000.mp4
│   │   └── ...
│   └── 20251028/
│       └── ...
└── cam_02/
    └── ...
```

### 로그 파일 구조
```
./logs/
├── pynvr_2025-10-27.log
├── pynvr_2025-10-27.log.zip
├── pynvr_errors_2025-10-27.log
└── ...
```

---

## 🛠️ 문제 해결

### 설정 파일이 손상된 경우
프로그램 실행 시 기본 설정으로 자동 생성됩니다.

### 경로 변경 후 파일을 찾을 수 없는 경우
- `base_path` 변경 시 기존 녹화 파일을 새 경로로 이동하세요
- 또는 `base_path`를 원래대로 복원하세요

### 성능 문제 발생 시
1. `use_hardware_acceleration: false` (소프트웨어 디코딩)
2. `latency_ms` 값 증가 (400~800)
3. `buffer_size` 감소

---

## 📌 버전 정보

- **문서 버전**: 1.0.0
- **작성일**: 2025-10-27
- **대상 프로그램**: IT_RNVR v1.0.0

---

## 📞 지원

설정 관련 문제가 발생하면 로그 파일(`./logs/`)을 확인하세요.
