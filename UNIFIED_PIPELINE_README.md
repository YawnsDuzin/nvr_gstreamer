# 통합 파이프라인 사용 가이드

## 개요
라즈베리파이에서 효율적으로 실행하기 위해 스트리밍과 녹화를 하나의 파이프라인으로 처리하는 통합 파이프라인을 구현했습니다.

## 주요 특징
- **단일 파이프라인**: 스트리밍과 녹화를 하나의 GStreamer 파이프라인에서 처리
- **리소스 효율성**: 중복 디코딩 없이 tee 엘리먼트로 스트림 분기
- **유연한 모드 전환**: 스트리밍만, 녹화만, 또는 동시 처리 가능
- **라즈베리파이 최적화**: 하드웨어 가속 지원 및 메모리 효율적 설계

## 사용 방법

### 1. 기본 사용 (스트리밍 + 녹화)

```python
from streaming.unified_pipeline import UnifiedPipeline, PipelineMode

# 파이프라인 생성
pipeline = UnifiedPipeline(
    rtsp_url="rtsp://admin:password@192.168.1.100:554/stream1",
    camera_id="cam01",
    camera_name="Front Camera",
    mode=PipelineMode.BOTH  # 스트리밍과 녹화 동시
)

# 파이프라인 시작
if pipeline.create_pipeline():
    if pipeline.start():
        print("Pipeline started")

        # 녹화 시작
        if pipeline.start_recording():
            print("Recording started")

            # 일정 시간 후 녹화 정지
            time.sleep(60)
            pipeline.stop_recording()

        # 파이프라인 정지
        pipeline.stop()
```

### 2. Pipeline Manager를 통한 사용

```python
from streaming.pipeline_manager import PipelineManager
from streaming.unified_pipeline import PipelineMode

# 통합 파이프라인 모드로 매니저 생성
manager = PipelineManager(
    rtsp_url="rtsp://admin:password@192.168.1.100:554/stream1",
    use_unified_pipeline=True,
    camera_id="cam01",
    camera_name="Front Camera"
)

# 통합 파이프라인 생성 및 시작
if manager.create_unified_pipeline(mode=PipelineMode.BOTH):
    if manager.start_unified():
        print("Unified pipeline started")

        # 녹화 시작
        manager.start_recording()

        # 상태 확인
        status = manager.get_unified_status()
        print(f"Status: {status}")

        # 녹화 정지
        manager.stop_recording()

        # 파이프라인 정지
        manager.stop_unified()
```

### 3. 모드별 사용

#### 스트리밍만
```python
pipeline = UnifiedPipeline(
    rtsp_url=rtsp_url,
    camera_id="cam01",
    camera_name="Camera",
    mode=PipelineMode.STREAMING_ONLY
)
```

#### 녹화만
```python
pipeline = UnifiedPipeline(
    rtsp_url=rtsp_url,
    camera_id="cam01",
    camera_name="Camera",
    mode=PipelineMode.RECORDING_ONLY
)
```

## 파이프라인 구조

```
rtspsrc → rtph264depay → h264parse → tee ─┬─→ [Streaming Branch]
                                           │    queue → decoder → videoconvert → videoscale → videosink
                                           │
                                           └─→ [Recording Branch]
                                                queue → valve → mp4mux → filesink
```

### 주요 컴포넌트
- **tee**: 스트림을 두 개의 브랜치로 분기
- **valve**: 녹화 on/off 제어 (drop 속성 사용)
- **queue**: 각 브랜치의 버퍼링으로 안정성 향상

## 설정 옵션

### 녹화 설정
```python
pipeline.file_duration = 600  # 파일 분할 시간 (초)
pipeline.recording_dir = Path("recordings") / camera_id  # 녹화 디렉토리
```

### 성능 최적화
- 라즈베리파이에서는 `glimagesink` 사용 (하드웨어 가속)
- 적절한 큐 크기 설정으로 버퍼링 최적화
- sync=false로 레이턴시 감소

## 테스트

테스트 스크립트 실행:
```bash
# 스트리밍만 테스트
python test_unified_pipeline.py --mode streaming

# 녹화만 테스트
python test_unified_pipeline.py --mode recording

# 스트리밍 + 녹화 테스트
python test_unified_pipeline.py --mode both

# 파일 회전 테스트
python test_unified_pipeline.py --mode rotation
```

## 주의사항

1. **라즈베리파이 설정**
   - GPU 메모리 할당 확인: `gpu_mem=128` (최소)
   - V4L2 드라이버 활성화 확인

2. **메모리 관리**
   - 긴 시간 녹화 시 디스크 공간 확인
   - 파일 회전으로 메모리 누수 방지

3. **네트워크**
   - 안정적인 네트워크 연결 필요
   - TCP 프로토콜 사용 권장

## 문제 해결

### 스트리밍이 보이지 않을 때
- window_handle 설정 확인
- 적절한 비디오 싱크 사용 (glimagesink, xvimagesink)

### 녹화가 시작되지 않을 때
- 녹화 디렉토리 권한 확인
- 디스크 공간 확인
- 파이프라인 모드 확인 (RECORDING_ONLY 또는 BOTH)

### 성능 문제
- 해상도 조정 (720p 권장)
- 하드웨어 디코더 사용 확인
- 큐 크기 조정