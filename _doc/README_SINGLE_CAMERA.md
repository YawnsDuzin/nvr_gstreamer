# 단일 카메라 NVR 시스템

Python 기반의 단일 카메라 네트워크 비디오 녹화(NVR) 시스템입니다.
GStreamer를 사용하여 RTSP 스트림을 실시간으로 표시하고 녹화합니다.

## 주요 변경사항

4채널 그리드 뷰에서 단일 카메라 전용 시스템으로 변경되었습니다:

- ✅ config.yaml - 단일 카메라만 설정
- ✅ UI - 1x1 단일 뷰로 고정
- ✅ 불필요한 그리드 레이아웃 옵션 제거
- ✅ 녹화 시스템 최적화

## 설정 파일 (config.yaml)

```yaml
# PyNVR Configuration File - Single Camera Setup

app:
  app_name: PyNVR
  version: 0.1.0
  default_layout: 1x1  # 단일 카메라용 레이아웃
  recording_path: recordings
  log_level: INFO
  use_hardware_acceleration: true
  max_reconnect_attempts: 3
  reconnect_delay: 5

cameras:
  # 단일 카메라 설정
  - camera_id: cam_01
    name: Main Camera
    rtsp_url: rtsp://admin:password@192.168.0.131:554/Streaming/Channels/102
    enabled: true
    recording_enabled: true  # 녹화 활성화
    motion_detection: false
```

## 실행 방법

### 1. 기본 실행 (GUI 모드)

```bash
python main.py
```

### 2. 간편 실행 스크립트

```bash
# GUI 모드
python run_single_camera.py

# 디버그 모드
python run_single_camera.py --debug

# 자동 녹화 시작
python run_single_camera.py --recording

# GUI 없이 녹화만 (헤드리스 모드)
python run_single_camera.py --headless
```

### 3. 테스트 스크립트

```bash
# 단일 카메라 전체 테스트
python test_single_camera.py
```

## 기능

### 실시간 스트리밍
- RTSP 스트림 실시간 디스플레이
- 자동 재연결 기능
- 전체화면 지원 (F11)

### 연속 녹화
- MP4/MKV/AVI 형식 지원
- 자동 파일 분할 (기본 10분 단위)
- 날짜별 디렉토리 구조
- 디스크 공간 관리

### 녹화 파일 구조
```
recordings/
├── cam_01/
│   ├── 20241020/
│   │   ├── cam_01_20241020_090000.mp4
│   │   ├── cam_01_20241020_091000.mp4
│   │   └── ...
│   └── 20241021/
│       ├── cam_01_20241021_090000.mp4
│       └── ...
```

## 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| F11 | 전체화면 전환 |
| Ctrl+Q | 프로그램 종료 |
| Ctrl+Shift+C | 카메라 연결 |
| Ctrl+Shift+D | 카메라 연결 해제 |
| Alt+1 | 단일 뷰 (이미 활성) |
| ESC | 전체화면 종료 |

## 시스템 요구사항

### Windows
- Python 3.8+
- GStreamer 1.20+ (https://gstreamer.freedesktop.org/download/)
- PyQt5

### Linux/Raspberry Pi
```bash
# GStreamer 설치
sudo apt-get update
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Python 패키지
pip install -r requirements.txt
```

## 문제 해결

### 카메라 연결 실패
1. RTSP URL이 올바른지 확인
2. 카메라 네트워크 연결 확인
3. 방화벽 설정 확인
4. 직접 테스트:
   ```bash
   gst-launch-1.0 rtspsrc location=rtsp://... ! decodebin ! autovideosink
   ```

### 녹화 파일이 생성되지 않음
1. recordings 디렉토리 권한 확인
2. 디스크 공간 확인
3. config.yaml에서 recording_enabled: true 확인

### 높은 CPU 사용률
1. 하드웨어 가속 활성화 확인
2. 비디오 해상도 낮추기
3. 파일 분할 간격 늘리기 (file_duration 설정)

## 성능 최적화

### 통합 파이프라인
단일 디코딩으로 스트리밍과 녹화를 동시에 처리하여 CPU 사용률을 약 50% 감소시킵니다:

```
RTSP Source → Decode → Tee ─┬─→ Display (streaming_valve)
                            └─→ File (recording_valve)
```

### Valve 기반 제어
파이프라인을 재생성하지 않고 실시간으로 스트리밍/녹화 모드를 전환할 수 있습니다.

## 헤드리스 모드 (서버용)

GUI 없이 녹화만 실행하려면:

```bash
python run_single_camera.py --headless
```

이 모드는 서버나 임베디드 시스템에서 유용합니다.

## 로그 파일

로그는 `logs/` 디렉토리에 일별로 저장됩니다:
- single_camera_YYYY-MM-DD.log
- 7일 간 보관
- 자동 로테이션

## 라이센스

MIT License