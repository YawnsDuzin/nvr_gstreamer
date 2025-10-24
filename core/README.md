# NVR Core Module

NVR 시스템의 핵심 비즈니스 로직과 도메인 모델을 담당하는 코어 모듈입니다.

## 📁 폴더 구조

```
core/
├── __init__.py          # 코어 모듈 초기화 및 주요 클래스 export
├── models.py            # 도메인 엔티티 (Camera, Recording, StreamStatus 등)
├── enums.py             # 시스템 전체 열거형 (CameraStatus, RecordingStatus 등)
├── exceptions.py        # 커스텀 예외 클래스
└── services/
    ├── __init__.py
    ├── camera_service.py    # 카메라 비즈니스 로직 (자동 녹화 등)
    └── storage_service.py   # 스토리지 관리 로직 (파일 정리, 디스크 관리)
```

## 🎯 주요 기능

### Models (도메인 엔티티)
- **Camera**: 카메라 정보 및 설정
- **Recording**: 녹화 세션 정보
- **StreamStatus**: 스트림 상태 정보
- **StorageInfo**: 스토리지 상태 정보
- **SystemStatus**: 시스템 전체 상태

### Enums (열거형)
- **CameraStatus**: 카메라 연결 상태
- **RecordingStatus**: 녹화 상태
- **PipelineMode**: 파이프라인 동작 모드
- **PlaybackState**: 재생 상태
- **StreamQuality**: 스트림 품질 설정
- **FileFormat**: 녹화 파일 형식

### Services (비즈니스 로직)

#### CameraService
- 카메라 연결 관리
- **자동 녹화 기능** (recording_enabled 설정 기반)
- 녹화 시작/중지
- 카메라 상태 모니터링
- 이벤트 콜백 관리

#### StorageService
- 디스크 공간 모니터링
- **자동 파일 정리** (기간/공간 기반)
- 녹화 파일 관리
- 보관 정책 계산
- 빈 디렉토리 정리

## 💡 사용 예시

### CameraService 사용
```python
from core.services import CameraService
from config.config_manager import ConfigManager

# 서비스 초기화
config_manager = ConfigManager.get_instance()
camera_service = CameraService(config_manager)

# 카메라 연결 (자동 녹화 처리 포함)
camera_service.connect_camera(camera_id="cam_01", stream_object=stream)

# 콜백 등록
def on_recording_started(camera_id, recording):
    print(f"Recording started: {camera_id}")

camera_service.register_callback('recording_started', on_recording_started)

# 녹화 수동 시작/중지
camera_service.start_recording("cam_01")
camera_service.stop_recording("cam_01")

# 상태 조회
status = camera_service.get_camera_status("cam_01")
```

### StorageService 사용
```python
from core.services import StorageService

# 서비스 초기화
storage_service = StorageService()

# 스토리지 정보 조회
info = storage_service.get_storage_info()
print(f"Free space: {info.free_space / (1024**3):.1f}GB")
print(f"Usage: {info.usage_percent:.1f}%")

# 자동 정리 실행
deleted_count = storage_service.auto_cleanup()

# 수동 정리
# 30일 이상 오래된 파일 삭제
deleted_count = storage_service.cleanup_old_recordings(days=30)

# 공간 확보를 위한 정리 (20GB 확보)
deleted_count = storage_service.cleanup_by_space(target_free_gb=20)

# 녹화 파일 조회
recordings = storage_service.get_recordings_for_camera("cam_01")
for rec in recordings:
    print(f"{rec['file_name']}: {rec['size_mb']:.1f}MB")
```

## 🔄 마이그레이션 가이드

기존 코드를 core 모듈 사용하도록 변경하는 방법:

### 1. StreamStatus 마이그레이션
```python
# Before
from streaming.camera_stream import StreamStatus

# After
from core.enums import CameraStatus as StreamStatus
```

### 2. 자동 녹화 로직 마이그레이션
```python
# Before (main_window.py)
if camera_config.recording_enabled:
    if stream.gst_pipeline.start_recording():
        # UI 업데이트 코드...

# After
camera_service.connect_camera(camera_id, stream)
camera_service.register_callback('recording_started', on_recording_started)
```

### 3. 파일 정리 로직 추가
```python
# 시스템 시작 시 또는 주기적으로 실행
storage_service.auto_cleanup()
```

## 🏗️ 확장 가능성

### 향후 추가 가능한 기능
1. **알림 서비스** (`core/services/notification_service.py`)
   - 디스크 공간 부족 알림
   - 카메라 연결 끊김 알림
   - 녹화 오류 알림

2. **분석 서비스** (`core/services/analytics_service.py`)
   - 모션 감지
   - 객체 인식
   - 이벤트 트리거

3. **백업 서비스** (`core/services/backup_service.py`)
   - 클라우드 백업
   - 외부 스토리지 백업
   - 증분 백업

4. **스케줄링 서비스** (`core/services/schedule_service.py`)
   - 예약 녹화
   - 자동 정리 스케줄
   - 시스템 유지보수

## 📝 설계 원칙

1. **도메인 중심**: 비즈니스 로직을 UI나 기술 구현으로부터 분리
2. **단일 책임**: 각 서비스는 하나의 명확한 책임을 가짐
3. **확장 가능**: 새로운 기능 추가 시 기존 코드 수정 최소화
4. **테스트 가능**: 의존성 주입을 통한 단위 테스트 용이
5. **재사용 가능**: 다른 UI나 인터페이스에서도 사용 가능