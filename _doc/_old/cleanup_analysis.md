# 프로젝트 정리 분석 보고서

## 📊 현재 프로젝트 구조 분석

### 중복 기능 발견

#### 1. **Camera 관련 클래스 중복**
- `streaming/camera_stream.py::CameraConfig`
- `core/models.py::Camera`
- 두 클래스가 동일한 역할 수행

#### 2. **Status Enum 중복**
- `streaming/camera_stream.py::StreamStatus`
- `core/enums.py::CameraStatus`
- 이미 import 변경했지만 아직 StreamStatus 정의 남아있음

#### 3. **Camera Manager 중복**
- `reference/enhanced_camera_manager.py::EnhancedCameraManager`
- `core/services/camera_service.py::CameraService`
- `ui/camera_list_widget.py`의 카메라 관리 기능
- 동일한 기능이 3곳에서 구현됨

#### 4. **Pipeline 관련 중복**
- `reference/simple_pipeline.py`
- `reference/optimized_pipeline.py`
- `streaming/gst_pipeline.py::UnifiedPipeline`
- 모두 동일한 파이프라인 구현의 다른 버전들

### 불필요한 파일들

#### reference/ 폴더 (구버전/테스트 파일)
- `enhanced_camera_manager.py` - CameraService로 대체됨
- `main_window_old.py` - 구버전 백업
- `main_with_playback.py` - 테스트용, 현재 main_window.py에 통합됨
- `simple_pipeline.py` - 구버전 파이프라인
- `optimized_pipeline.py` - 구버전 파이프라인
- `simple_test.py` - 개발 중 테스트 파일
- `run_nvr.py` - main.py와 중복
- `run_with_recording.py` - tests/run_single_camera.py와 중복

#### 백업 파일들
- `config.yaml.backup` - 구 설정 백업
- `IT_RNVR.yaml.bak` - YAML에서 JSON으로 마이그레이션 후 백업

## 🛠️ 정리 계획

### Phase 1: 중복 코드 제거
1. ✅ `streaming/camera_stream.py`에서 StreamStatus 클래스 정의 제거
2. ✅ `streaming/camera_stream.py`의 CameraConfig을 core.models.Camera로 통합
3. ✅ EnhancedCameraManager 제거 (CameraService 사용)

### Phase 2: reference/ 폴더 정리
1. ✅ 유용한 테스트 코드만 tests/로 이동
2. ✅ 나머지 파일들 삭제

### Phase 3: 백업 파일 제거
1. ✅ `config.yaml.backup` 삭제
2. ✅ `IT_RNVR.yaml.bak` 삭제
3. ⚠️ `IT_RNVR.db` 유지 (향후 사용 가능)
4. ⚠️ `IT_RNVR.env` 유지 (환경변수 설정용)

### Phase 4: 코드 리팩토링
1. ✅ camera_stream.py를 core.models 사용하도록 수정
2. ✅ UI 파일들이 CameraService를 사용하도록 통일

## 📈 예상 효과

- **코드 중복 제거**: 약 30% 코드량 감소
- **유지보수성 향상**: 단일 책임 원칙 준수
- **명확한 구조**: core 모듈 중심의 깔끔한 아키텍처
- **테스트 용이성**: 비즈니스 로직 분리로 테스트 작성 용이

## 🚀 정리 후 프로젝트 구조

```
nvr_gstreamer/
├── core/               # 핵심 비즈니스 로직
│   ├── models.py       # 도메인 모델
│   ├── enums.py        # 상태 열거형
│   ├── exceptions.py   # 커스텀 예외
│   └── services/       # 비즈니스 서비스
├── streaming/          # GStreamer 파이프라인
│   ├── gst_pipeline.py # 통합 파이프라인
│   └── camera_stream.py # 카메라 스트림 핸들러
├── recording/          # 녹화 관리
├── playback/           # 재생 관리
├── ui/                 # PyQt5 UI
├── config/             # 설정 관리
├── utils/              # 유틸리티
├── tests/              # 테스트 코드
├── IT_RNVR.db         # 데이터베이스 (유지)
├── IT_RNVR.env        # 환경변수 (유지)
├── IT_RNVR.json       # 설정 파일
└── main.py             # 엔트리 포인트
```