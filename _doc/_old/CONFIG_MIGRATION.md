# Configuration Migration Guide

## 변경 사항 (2025-10-22)

기본 설정 파일이 `config.yaml`에서 `IT_RNVR.yaml`로 변경되었습니다.

## 주요 변경 사항

### 1. 기본 설정 파일 변경
- **이전**: `config.yaml` (단순 설정)
- **이후**: `IT_RNVR.yaml` (확장 설정)

### 2. IT_RNVR.yaml의 장점

#### 📁 더 많은 설정 항목
```yaml
# IT_RNVR.yaml 구조
- app: 기본 애플리케이션 설정
- ui: UI 테마, 레이아웃, OSD 설정
- streaming: 스트리밍 버퍼, 디코더 설정
- recording: 녹화 형식, 로테이션, 보관 기간
- camera_settings: 카메라 글로벌 설정
- cameras: 카메라 개별 설정
- logging: 상세한 로깅 설정 (콘솔/파일/에러/JSON)
- performance: CPU/메모리 제한 설정
- security: 인증 및 SSL 설정
```

#### 🎯 로깅 기능 강화
```yaml
logging:
  console:
    level: INFO
    colorize: true
  file:
    level: DEBUG
    rotation: "1 day"
    retention: "7 days"
    compression: "zip"
  error_log:
    enabled: true
    level: ERROR
  levels:
    application: INFO
    streaming: INFO
    gstreamer: WARNING
```

## 마이그레이션 방법

### Option 1: IT_RNVR.yaml 사용 (권장)

1. **IT_RNVR.yaml 편집**
   ```bash
   # 기본 설정 파일이 자동으로 IT_RNVR.yaml 사용
   python main.py
   ```

2. **카메라 설정 복사**
   - `config.yaml`의 cameras 섹션을 `IT_RNVR.yaml`의 cameras 섹션으로 복사
   - 이미 Main Camera가 추가되어 있으므로 필요시 수정

### Option 2: 기존 config.yaml 계속 사용

```bash
# 명령줄 옵션으로 기존 파일 지정
python main.py --config config.yaml
```

**주의**: config.yaml은 향후 제거될 예정이므로 IT_RNVR.yaml로 마이그레이션 권장

## 설정 파일 비교

### config.yaml (간단)
```yaml
app:
  app_name: PyNVR
  version: 0.1.0
  log_level: INFO

cameras:
  - camera_id: cam_01
    name: Main Camera
    rtsp_url: rtsp://...
```

### IT_RNVR.yaml (상세)
```yaml
app:
  app_name: IT_RNVR
  version: 1.0.0
  default_layout: 1x1
  recording_path: recordings

ui:
  theme: dark
  show_timestamp: true
  window_state:
    width: 1920
    height: 1080

streaming:
  use_hardware_acceleration: true
  decoder_preference:
    - v4l2h264dec
    - omxh264dec
    - avdec_h264

recording:
  enabled: true
  base_path: ./recordings
  file_format: mp4
  rotation_minutes: 10
  retention_days: 30

logging:
  enabled: true
  console:
    level: INFO
  file:
    level: DEBUG
    rotation: "1 day"

cameras:
  - camera_id: cam_01
    name: Main Camera
    rtsp_url: rtsp://...
```

## 코드 변경 사항

### ConfigManager 기본값 변경
```python
# 이전
self.config_file = Path(config_file) if config_file else Path("config.yaml")

# 이후
self.config_file = Path(config_file) if config_file else Path("IT_RNVR.yaml")
```

### main.py에서 로깅 설정 사용
```python
# IT_RNVR.yaml의 logging 섹션 자동 로드
setup_logging(debug=args.debug, config_file=args.config)
```

## 테스트

### IT_RNVR.yaml 로드 확인
```bash
cd d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer
python -c "from config.config_manager import ConfigManager; c = ConfigManager(); print(f'Config file: {c.config_file}'); print(f'Cameras: {len(c.cameras)}')"
```

**예상 출력:**
```
Config file: IT_RNVR.yaml
Cameras: 1
```

### 로깅 설정 확인
```bash
python tests/test_logging_config.py
```

## 문제 해결

### Q: IT_RNVR.yaml이 없다고 나옵니다
**A**: 파일이 프로젝트 루트에 있는지 확인하세요.
```bash
ls IT_RNVR.yaml
```

### Q: 기존 config.yaml 설정을 유지하고 싶습니다
**A**: 두 가지 방법이 있습니다:
1. config.yaml 내용을 IT_RNVR.yaml로 복사
2. `--config config.yaml` 옵션 사용

### Q: 로깅이 작동하지 않습니다
**A**: IT_RNVR.yaml의 logging 섹션을 확인하세요:
```yaml
logging:
  enabled: true  # 이 값이 false면 로깅 비활성화
```

## 추가 정보

### 백업 파일
- `config.yaml.backup`: 원본 config.yaml 백업
- 필요시 복구 가능

### 관련 파일
- `IT_RNVR.yaml`: 메인 설정 파일
- `config/config_manager.py`: 설정 로더
- `main.py`: 로깅 초기화
- `utils/logging_utils.py`: 로깅 유틸리티

### 참고 문서
- `CLAUDE.md`: 프로젝트 전체 가이드
- `tests/test_logging_config.py`: 로깅 테스트
