# Unified Pipeline Branch Control Guide

## 목차
1. [개요](#1-개요)
2. [브랜치 아키텍처](#2-브랜치-아키텍처)
3. [Valve 기반 브랜치 제어](#3-valve-기반-브랜치-제어)
4. [브랜치별 상태 관리](#4-브랜치별-상태-관리)
5. [예외 상황별 브랜치 제어](#5-예외-상황별-브랜치-제어)
6. [부분 파이프라인 재시작](#6-부분-파이프라인-재시작)
7. [실전 구현 패턴](#7-실전-구현-패턴)

---

## 1. 개요

### 1.1 Unified Pipeline이란?

**Unified Pipeline**은 하나의 GStreamer 파이프라인에서 스트리밍과 녹화를 동시에 처리하는 아키텍처입니다.

**핵심 장점:**
- ✅ **CPU 사용량 50% 절감** (디코딩 1회만 수행)
- ✅ **메모리 효율** (버퍼 공유)
- ✅ **독립적 제어** (스트리밍/녹화 개별 제어)
- ✅ **무중단 전환** (한 브랜치 에러 시 다른 브랜치는 유지)

**전통적 방식 vs Unified Pipeline:**

```
[전통적 방식 - 2개의 독립 파이프라인]
Pipeline 1: RTSP → Decode → Display    (스트리밍)
Pipeline 2: RTSP → Decode → File       (녹화)
문제: 디코딩 2번, 메모리 2배, CPU 2배

[Unified Pipeline - 1개의 통합 파이프라인]
RTSP → Decode → Tee ─┬─→ Display Branch
                     └─→ Recording Branch
장점: 디코딩 1번, 메모리 절약, CPU 절약
```

### 1.2 언제 사용하는가?

| 시나리오 | 전통적 방식 | Unified Pipeline |
|---------|-----------|------------------|
| 임베디드 장치 (라즈베리파이) | CPU 부족 | ✅ 권장 |
| 다채널 NVR (8ch 이상) | 메모리 부족 | ✅ 권장 |
| 스트리밍/녹화 독립 제어 | 복잡함 | ✅ 간단함 |
| 스트리밍만 또는 녹화만 | 적합 | 불필요 |

---

## 2. 브랜치 아키텍처

### 2.1 전체 구조

```
┌────────────────────────────────────────────────────────────────────┐
│                         Unified Pipeline                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [RTSP Source]                                                      │
│       ↓                                                             │
│  [rtph264depay]                                                     │
│       ↓                                                             │
│  [h264parse]                                                        │
│       ↓                                                             │
│  ┌─────────┐                                                        │
│  │   Tee   │ ← 스트림 분기점                                          │
│  └────┬────┘                                                        │
│       │                                                             │
│       ├──────────────────┬─────────────────────┐                   │
│       │                  │                     │                    │
│  [Streaming Branch]  [Recording Branch]   [Other Branch?]          │
│       │                  │                                          │
│   ┌───▼────┐        ┌───▼────┐                                     │
│   │ Queue  │        │ Queue  │                                     │
│   └───┬────┘        └───┬────┘                                     │
│       │                  │                                          │
│   ┌───▼────┐        ┌───▼────┐                                     │
│   │ Valve  │ ◄──┐   │ Valve  │ ◄──┐ Valve로 브랜치 제어              │
│   └───┬────┘    │   └───┬────┘    │                               │
│       │         │       │         │                                │
│   [Decoder]     │   [h264parse]   │                                │
│       │         │       │         │                                │
│   [Convert]     │   [splitmuxsink]│                                │
│       │         │       │         │                                │
│   [Display]     │   [File]        │                                │
│       │         │       │         │                                │
│   (화면 출력)    │   (파일 저장)    │                                │
│                 │                 │                                │
│         제어: drop=False/True (열림/닫힘)                            │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 브랜치별 엘리먼트 구성

#### Streaming Branch (화면 출력)
```
stream_queue → streaming_valve → decoder → convert →
textoverlay → scale → capsfilter → final_queue → videosink
```

**주요 엘리먼트:**
- `stream_queue`: 버퍼링 (max-size-time=2s, leaky=downstream)
- `streaming_valve`: 스트리밍 on/off 제어 (drop 속성)
- `decoder`: H.264 디코딩 (avdec_h264, omxh264dec, v4l2h264dec)
- `textoverlay`: OSD (카메라명, 타임스탬프)
- `videosink`: 플랫폼별 비디오 출력 (d3d11videosink, ximagesink 등)

#### Recording Branch (파일 저장)
```
record_queue → recording_valve → h264parse → splitmuxsink
```

**주요 엘리먼트:**
- `record_queue`: 버퍼링 (max-size-time=5s, max-size-bytes=50MB)
- `recording_valve`: 녹화 on/off 제어 (drop 속성)
- `h264parse`: 키프레임 파싱 (config-interval=1)
- `splitmuxsink`: 자동 파일 분할 (max-size-time 기준)

### 2.3 Tee 엘리먼트 이해하기

**Tee란?**
- GStreamer의 분기 엘리먼트
- 하나의 입력 스트림을 여러 출력으로 복제
- 각 출력은 독립적으로 제어 가능

**Tee 속성:**
```python
tee = Gst.ElementFactory.make("tee", "tee")
tee.set_property("allow-not-linked", True)  # 중요!
```

**allow-not-linked=True의 의미:**
- 일부 브랜치가 PLAYING 상태가 아니어도 파이프라인이 동작
- 예: 녹화는 중지되고 스트리밍만 실행 가능

**Tee 패드 연결:**
```python
# 동적으로 출력 패드 요청
tee_pad = tee.request_pad_simple("src_%u")  # src_0, src_1, ...
queue_pad = stream_queue.get_static_pad("sink")
tee_pad.link(queue_pad)
```

---

## 3. Valve 기반 브랜치 제어

### 3.1 Valve 엘리먼트란?

**Valve**는 GStreamer의 **데이터 흐름 제어 밸브**입니다.

**핵심 속성: `drop`**
- `drop=False`: 밸브 열림 (데이터 통과) ✅
- `drop=True`: 밸브 닫힘 (데이터 차단) ❌

**장점:**
- ✅ 런타임 중 동적 제어
- ✅ 파이프라인 재시작 불필요
- ✅ 빠른 응답 속도 (즉시 적용)
- ✅ 상태 전환 부드러움

### 3.2 Valve 생성 및 초기화

```python
# Streaming Valve 생성
self.streaming_valve = Gst.ElementFactory.make("valve", "streaming_valve")
self.streaming_valve.set_property("drop", False)  # 초기: 열림
logger.debug("[VALVE] streaming_valve initial state: drop=False (open)")

# Recording Valve 생성
self.recording_valve = Gst.ElementFactory.make("valve", "recording_valve")
self.recording_valve.set_property("drop", True)   # 초기: 닫힘
logger.debug("[VALVE] recording_valve initial state: drop=True (closed)")
```

**초기 상태 설정 이유:**
- **스트리밍 밸브**: 파이프라인이 PLAYING 상태로 전환되려면 최소 1개의 sink가 데이터를 받아야 함
- **녹화 밸브**: 명시적으로 `start_recording()` 호출 전까지는 닫힘

### 3.3 Valve 제어 방법

#### 방법 1: 직접 제어 (간단)
```python
# 스트리밍 시작
self.streaming_valve.set_property("drop", False)

# 스트리밍 중지
self.streaming_valve.set_property("drop", True)

# 녹화 시작
self.recording_valve.set_property("drop", False)

# 녹화 중지
self.recording_valve.set_property("drop", True)
```

#### 방법 2: 모드 기반 제어 (권장)
```python
def _apply_mode_settings(self):
    """현재 모드에 따라 Valve 설정 적용"""

    if self.mode == PipelineMode.STREAMING_ONLY:
        # 스트리밍만
        self.streaming_valve.set_property("drop", False)
        self.recording_valve.set_property("drop", True)
        logger.info("[VALVE] Mode: STREAMING_ONLY")

    elif self.mode == PipelineMode.RECORDING_ONLY:
        # 녹화만 (headless)
        self.streaming_valve.set_property("drop", True)
        self.recording_valve.set_property("drop", False)
        logger.info("[VALVE] Mode: RECORDING_ONLY")

    elif self.mode == PipelineMode.BOTH:
        # 스트리밍 + 녹화
        self.streaming_valve.set_property("drop", False)
        self.recording_valve.set_property("drop", False)
        logger.info("[VALVE] Mode: BOTH")
```

#### 방법 3: 런타임 모드 전환
```python
def set_mode(self, mode: PipelineMode):
    """파이프라인 모드 변경 (런타임 중 변경 가능)"""
    old_mode = self.mode
    self.mode = mode

    # 파이프라인이 실행 중이면 즉시 적용
    if self._is_playing:
        self._apply_mode_settings()
        logger.info(f"Pipeline mode changed from {old_mode.value} to {mode.value}")
    else:
        logger.info(f"Pipeline mode set to {mode.value} (will apply on start)")

    return True

# 사용 예시
pipeline.set_mode(PipelineMode.STREAMING_ONLY)  # 녹화 중지, 스트리밍만
pipeline.set_mode(PipelineMode.BOTH)            # 녹화 재개
```

### 3.4 Valve 상태 확인

```python
def get_valve_states(self):
    """현재 밸브 상태 조회"""
    streaming_drop = self.streaming_valve.get_property("drop")
    recording_drop = self.recording_valve.get_property("drop")

    return {
        "streaming": "closed" if streaming_drop else "open",
        "recording": "closed" if recording_drop else "open"
    }

# 사용 예시
states = pipeline.get_valve_states()
print(f"Streaming: {states['streaming']}, Recording: {states['recording']}")
# 출력: Streaming: open, Recording: closed
```

### 3.5 Valve 제어 시 주의사항

#### ⚠️ 주의 1: 파이프라인 상태 전환 시 밸브 리셋 가능
```python
# 문제: PLAYING 상태 전환 후 valve 상태가 리셋될 수 있음
self.pipeline.set_state(Gst.State.PLAYING)

# 해결: 상태 전환 후 밸브 재적용
self.pipeline.set_state(Gst.State.PLAYING)
time.sleep(0.1)  # 짧은 대기
self._apply_mode_settings()  # 밸브 재설정
```

#### ⚠️ 주의 2: 두 밸브 모두 닫으면 파이프라인 블록 가능
```python
# 위험: 모든 밸브 닫힘 → 데이터 흐름 없음 → 파이프라인 블록
self.streaming_valve.set_property("drop", True)
self.recording_valve.set_property("drop", True)

# 해결: tee의 allow-not-linked=True 설정으로 방지
tee.set_property("allow-not-linked", True)
```

#### ⚠️ 주의 3: 키프레임 대기
```python
# 문제: 녹화 시작 시 첫 프레임이 I-frame이 아니면 깨진 영상
self.recording_valve.set_property("drop", False)  # 즉시 열기 → 문제 발생 가능

# 해결: splitmuxsink의 send-keyframe-requests 사용
self.splitmuxsink.set_property("send-keyframe-requests", True)
# splitmuxsink가 자동으로 키프레임을 요청하여 해결
```

---

## 4. 브랜치별 상태 관리

### 4.1 파이프라인 상태 vs 브랜치 상태

**GStreamer 파이프라인 상태:**
```
NULL → READY → PAUSED → PLAYING
```

**Unified Pipeline의 브랜치 상태:**
- 파이프라인 전체는 `PLAYING` 상태 유지
- 각 브랜치는 **Valve**로 독립적으로 제어

```python
# 파이프라인 상태 (전역)
pipeline.set_state(Gst.State.PLAYING)  # 전체 파이프라인 시작

# 브랜치 상태 (개별)
streaming_valve.set_property("drop", False)  # 스트리밍 활성화
recording_valve.set_property("drop", True)   # 녹화 비활성화
```

### 4.2 상태 추적 패턴

```python
class GstPipeline:
    def __init__(self, ...):
        # 파이프라인 전역 상태
        self._is_playing = False       # 파이프라인 실행 여부

        # 브랜치별 상태
        self._is_streaming = False     # 스트리밍 활성 여부
        self._is_recording = False     # 녹화 활성 여부

    def start(self):
        """파이프라인 시작"""
        self.pipeline.set_state(Gst.State.PLAYING)
        self._is_playing = True

        # 초기 모드에 따라 브랜치 상태 설정
        if self.mode == PipelineMode.STREAMING_ONLY:
            self._is_streaming = True
            self._is_recording = False
        elif self.mode == PipelineMode.RECORDING_ONLY:
            self._is_streaming = False
            self._is_recording = False  # 명시적 호출 필요
        elif self.mode == PipelineMode.BOTH:
            self._is_streaming = True
            self._is_recording = False  # 명시적 호출 필요

    def start_recording(self):
        """녹화 시작"""
        if not self._is_playing:
            return False

        self.recording_valve.set_property("drop", False)
        self._is_recording = True
        return True

    def stop_recording(self):
        """녹화 중지"""
        self.recording_valve.set_property("drop", True)
        self._is_recording = False
        return True

    def get_status(self):
        """현재 상태 조회"""
        return {
            "pipeline_playing": self._is_playing,
            "streaming_active": self._is_streaming,
            "recording_active": self._is_recording,
            "mode": self.mode.value
        }
```

### 4.3 상태 동기화 (UI ↔ Pipeline)

#### 문제: UI와 파이프라인 상태 불일치
```python
# 사용자가 녹화 시작 버튼 클릭
# → 파이프라인에서 녹화 시작
# → UI는 즉시 "녹화 중" 표시
# → 하지만 실제 파일은 아직 생성되지 않음 (비동기)
```

#### 해결: 콜백 패턴
```python
class GstPipeline:
    def __init__(self, ...):
        # 녹화 상태 변경 콜백 리스트
        self._recording_state_callbacks = []

    def register_recording_callback(self, callback):
        """녹화 상태 변경 콜백 등록"""
        if callback not in self._recording_state_callbacks:
            self._recording_state_callbacks.append(callback)

    def _notify_recording_state_change(self, is_recording: bool):
        """녹화 상태 변경 알림"""
        logger.debug(f"[CALLBACK] Notifying recording state: {is_recording}")
        for callback in self._recording_state_callbacks:
            try:
                callback(self.camera_id, is_recording)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def start_recording(self):
        """녹화 시작"""
        # ... valve 열기
        self._is_recording = True

        # 콜백 호출 (UI 동기화)
        self._notify_recording_state_change(True)
        return True

    def stop_recording(self):
        """녹화 중지"""
        # ... valve 닫기
        self._is_recording = False

        # 콜백 호출 (UI 동기화)
        self._notify_recording_state_change(False)
        return True

# UI에서 사용
def on_recording_state_changed(camera_id, is_recording):
    """녹화 상태 변경 콜백 (UI 스레드에서 호출)"""
    if is_recording:
        ui.update_recording_button(camera_id, "녹화 중지", "red")
    else:
        ui.update_recording_button(camera_id, "녹화 시작", "green")

# 콜백 등록
pipeline.register_recording_callback(on_recording_state_changed)
```

---

## 5. 예외 상황별 브랜치 제어

### 5.1 네트워크 끊김 (RTSP 소스 에러)

**상황:**
- 카메라 전원 꺼짐
- 네트워크 케이블 분리
- 카메라 재부팅

**에러 시그니처:**
```python
# error code: 9 (GST_RESOURCE_ERROR_READ)
# error message: "Could not read from resource"
# element: "source" (rtspsrc)
```

**처리 방법: 전체 파이프라인 재시작**

```python
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()
        error_code = err.code

        # RTSP 소스 에러 감지
        if (src_name == "source" and
            "Could not read from resource" in str(err) and
            error_code == 9):

            logger.critical(f"[RTSP ERROR] Network disconnected: {self.camera_name}")

            # 1. 전체 파이프라인 중지
            self.stop()

            # 2. 재연결 스케줄링 (지수 백오프)
            self._schedule_reconnect()
            return

def _schedule_reconnect(self):
    """재연결 스케줄링"""
    # 지수 백오프: 5, 10, 20, 40, 60초
    delay = min(5 * (2 ** self.retry_count), 60)
    self.retry_count += 1

    logger.info(f"Reconnecting in {delay}s (attempt {self.retry_count})...")

    self.reconnect_timer = threading.Timer(delay, self._reconnect)
    self.reconnect_timer.daemon = True
    self.reconnect_timer.start()

def _reconnect(self):
    """재연결 수행"""
    logger.info("Attempting to reconnect...")

    # 파이프라인 재시작
    success = self.start()

    if success:
        logger.success("Reconnected successfully")
        self.retry_count = 0  # 성공 시 리셋
    else:
        logger.error("Reconnect failed - retrying...")
        self._schedule_reconnect()
```

**왜 전체 재시작?**
- RTSP 소스는 파이프라인의 **최상위 엘리먼트**
- 소스가 끊기면 모든 브랜치에 영향
- 부분 재시작으로는 복구 불가

### 5.2 USB/저장소 끊김 (Recording Branch 에러)

**상황:**
- USB 드라이브 분리
- 외장 HDD 전원 끊김
- 네트워크 드라이브 연결 끊김

**에러 시그니처:**
```python
# error code: 10 (GST_RESOURCE_ERROR_WRITE)
# error message: "Could not write to resource"
# element: "splitmuxsink" or "sink"
# debug: "Permission denied" or "Error while writing to file descriptor"
```

**처리 방법: Recording Branch만 중지 (Streaming 유지)**

```python
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()
        error_code = err.code

        # USB 분리 감지
        if (src_name in ["splitmuxsink", "sink"] and
            "Could not write to resource" in str(err) and
            error_code == 10 and
            ("Permission denied" in str(debug) or
             "Error while writing to file descriptor" in str(debug))):

            logger.critical(f"[STORAGE ERROR] USB disconnected: {self.camera_name}")
            logger.critical(f"Current file: {self.current_recording_file}")

            # 1. 녹화만 중지 (스트리밍은 유지!) ✅
            self.stop_recording()

            # 2. 에러 플래그 설정
            self._recording_branch_error = True
            self._recording_error_time = time.time()

            # 3. UI 알림
            self._notify_recording_state_change(False)

            logger.info("[STREAMING] Streaming continues - only recording stopped")
            return
```

**왜 부분 중지?**
- ✅ **사용자 경험**: 화면은 계속 보임
- ✅ **시스템 효율**: 디코더 재시작 불필요
- ✅ **Unified Pipeline의 장점**: 브랜치 독립성

**복구 방법:**
```python
def start_recording(self):
    """녹화 시작"""
    if not self._is_playing:
        return False

    # 에러 상태 체크 및 복구
    if self._recording_branch_error:
        logger.warning("[RECOVERY] Recording branch error detected - recovering...")

        if not self._recover_recording_branch():
            logger.error("[RECOVERY] Failed to recover recording branch")
            return False

        logger.success("[RECOVERY] Recording branch recovered")

    # ... 정상 녹화 시작
    self.recording_valve.set_property("drop", False)
    self._is_recording = True
    self._notify_recording_state_change(True)
    return True

def _recover_recording_branch(self):
    """녹화 브랜치만 재구성"""
    try:
        # 1. splitmuxsink를 NULL 상태로
        self.splitmuxsink.set_state(Gst.State.NULL)
        ret, current, pending = self.splitmuxsink.get_state(2 * Gst.SECOND)

        if ret == Gst.StateChangeReturn.FAILURE:
            return False

        # 2. 짧은 대기
        time.sleep(0.5)

        # 3. PLAYING 상태로 복구
        self.splitmuxsink.set_state(Gst.State.PLAYING)
        ret, current, pending = self.splitmuxsink.get_state(3 * Gst.SECOND)

        if ret in [Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.ASYNC]:
            # 4. 에러 플래그 초기화
            self._recording_branch_error = False
            self._recording_error_time = None
            return True

        return False

    except Exception as e:
        logger.error(f"Recovery error: {e}")
        return False
```

### 5.3 디스크 Full (Recording Branch 에러)

**상황:**
- 저장 공간 부족
- 파일 시스템 쿼터 초과

**에러 시그니처:**
```python
# error code: 9 or 10
# error message: "No space left on device" or "space"
```

**처리 방법: 자동 정리 후 재시작**

```python
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # 디스크 Full 감지
        if src_name in ["splitmuxsink", "sink"]:
            if "space" in str(err).lower() or "No space" in str(err):
                logger.critical("[DISK FULL] Storage full - attempting cleanup")
                self._handle_disk_full()
                return

def _handle_disk_full(self):
    """디스크 Full 처리"""
    # 1. 녹화 중지
    if self._is_recording:
        self.stop_recording()

    # 2. 공간 확보 시도
    try:
        storage_service = StorageService()
        storage_service.auto_cleanup(max_age_days=7)  # 7일 이상 파일 삭제

        time.sleep(2)

        # 3. 공간 확보 확인
        free_gb = storage_service.get_free_space_gb()

        if free_gb > 2:
            logger.success(f"[DISK CLEANUP] Freed space: {free_gb:.2f}GB")

            # 4. 녹화 재시작
            if not self._recording_branch_error:
                self.start_recording()
            else:
                # 브랜치 복구 필요
                logger.warning("[DISK CLEANUP] Recording branch needs recovery")
        else:
            logger.error("[DISK CLEANUP] Still not enough space")
            # UI 알림
            self._notify_disk_full_error()

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
```

### 5.4 디코더 에러 (Streaming Branch 에러)

**상황:**
- 손상된 비디오 프레임
- 지원되지 않는 코덱 프로파일
- 일시적 스트림 손상

**에러 시그니처:**
```python
# element: "decoder" (avdec_h264, omxh264dec, etc.)
# error: "Failed to decode", "stream error"
```

**처리 방법: 버퍼 플러시**

```python
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # 디코더 에러 감지
        if "dec" in src_name or "decode" in src_name:
            logger.warning(f"[DECODER ERROR] {err}")

            # 손상된 프레임으로 인한 일시적 에러인 경우
            if "failed to decode" in str(err).lower():
                logger.info("[DECODER] Flushing pipeline buffers...")

                # 버퍼 플러시
                self.pipeline.send_event(Gst.Event.new_flush_start())
                time.sleep(0.1)
                self.pipeline.send_event(Gst.Event.new_flush_stop(True))

                logger.info("[DECODER] Pipeline flushed - continuing")
                return  # 에러 무시하고 계속

            # 심각한 디코더 에러 - 재시작 필요
            logger.error("[DECODER] Critical decoder error - restarting")
            self.stop()
            self._schedule_reconnect()
```

### 5.5 Video Sink 에러 (Streaming Branch)

**상황:**
- 윈도우 핸들 없음 (headless 모드)
- 디스플레이 드라이버 문제

**처리 방법: 에러 무시 (Recording 계속)**

```python
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # Video sink 에러
        if "videosink" in src_name or "Output window" in str(err):
            logger.warning(f"[VIDEOSINK] {err}")

            # Headless 모드인 경우 무시
            if not self.window_handle:
                logger.debug("[VIDEOSINK] No window handle - error ignored")
                return  # 녹화는 계속

            # 윈도우 있는데 에러 발생 - 스트리밍 브랜치만 중지
            logger.error("[VIDEOSINK] Display error - closing streaming branch")
            self.streaming_valve.set_property("drop", True)
            self._is_streaming = False

            # 녹화는 계속
            logger.info("[RECORDING] Recording continues")
            return
```

---

## 6. 부분 파이프라인 재시작

### 6.1 전체 재시작 vs 부분 재시작

| 방법 | 장점 | 단점 | 사용 시기 |
|------|------|------|----------|
| **전체 재시작** | 간단, 안전 | 느림 (5-10초), 모든 브랜치 중단 | RTSP 에러, 네트워크 끊김 |
| **부분 재시작** | 빠름 (1-2초), 다른 브랜치 유지 | 복잡, 실패 가능성 | USB 끊김, 디스크 Full |

### 6.2 Recording Branch만 재시작

#### 방법 1: Element 상태 전환 (권장)
```python
def _recover_recording_branch(self):
    """녹화 브랜치만 재시작"""
    try:
        logger.info("[RECOVERY] Restarting recording branch...")

        # 1. Valve 닫기 (데이터 흐름 차단)
        if self.recording_valve:
            self.recording_valve.set_property("drop", True)
            time.sleep(0.2)

        # 2. splitmuxsink를 NULL 상태로
        if self.splitmuxsink:
            ret = self.splitmuxsink.set_state(Gst.State.NULL)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("[RECOVERY] Failed to set NULL")
                return False

            # 상태 전환 대기
            ret, current, pending = self.splitmuxsink.get_state(2 * Gst.SECOND)
            logger.debug(f"[RECOVERY] splitmuxsink state: {current.value_nick}")

        # 3. 짧은 대기 (리소스 정리)
        time.sleep(0.5)

        # 4. PLAYING 상태로 복구
        ret = self.splitmuxsink.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("[RECOVERY] Failed to set PLAYING")
            return False

        # 상태 전환 대기
        ret, current, pending = self.splitmuxsink.get_state(3 * Gst.SECOND)

        if ret in [Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.ASYNC]:
            logger.success(f"[RECOVERY] splitmuxsink recovered: {current.value_nick}")

            # 5. 에러 플래그 초기화
            self._recording_branch_error = False
            self._recording_error_time = None

            return True
        else:
            logger.error(f"[RECOVERY] State change failed: ret={ret}")
            return False

    except Exception as e:
        logger.error(f"[RECOVERY] Exception: {e}")
        return False
```

#### 방법 2: Pad Probe (고급)
```python
def _recover_recording_branch_with_probe(self):
    """Pad Probe를 사용한 녹화 브랜치 재시작"""
    try:
        # 1. splitmuxsink의 sink 패드에 Probe 추가
        sink_pad = self.splitmuxsink.get_static_pad("video")
        if not sink_pad:
            sink_pad = self.splitmuxsink.get_static_pad("sink")

        if not sink_pad:
            logger.error("[RECOVERY] Failed to get sink pad")
            return False

        # 2. 블로킹 프로브 추가 (데이터 흐름 차단)
        self.probe_id = sink_pad.add_probe(
            Gst.PadProbeType.BLOCK_DOWNSTREAM,
            self._block_probe_callback
        )

        logger.info("[RECOVERY] Probe added - data flow blocked")
        return True

    except Exception as e:
        logger.error(f"[RECOVERY] Probe error: {e}")
        return False

def _block_probe_callback(self, pad, info):
    """Pad Probe 콜백"""
    logger.debug("[RECOVERY] Probe callback - performing restart")

    # 별도 스레드에서 재시작 수행
    threading.Thread(target=self._do_recovery_in_probe).start()

    # 프로브 유지 (OK 반환)
    return Gst.PadProbeReturn.OK

def _do_recovery_in_probe(self):
    """Probe 내에서 실제 재시작"""
    try:
        # 1. splitmuxsink를 NULL로
        self.splitmuxsink.set_state(Gst.State.NULL)
        time.sleep(0.5)

        # 2. 새 location 설정
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
        location = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")
        self.splitmuxsink.set_property("location", location)

        # 3. PLAYING으로 복구
        self.splitmuxsink.set_state(Gst.State.PLAYING)

        # 4. Probe 제거 (데이터 흐름 재개)
        if self.probe_id:
            sink_pad = self.splitmuxsink.get_static_pad("video")
            if not sink_pad:
                sink_pad = self.splitmuxsink.get_static_pad("sink")

            if sink_pad:
                sink_pad.remove_probe(self.probe_id)
                self.probe_id = None
                logger.success("[RECOVERY] Probe removed - data flow resumed")

        # 5. 에러 플래그 초기화
        self._recording_branch_error = False

    except Exception as e:
        logger.error(f"[RECOVERY] Probe recovery error: {e}")
```

**Pad Probe의 장점:**
- ✅ 더 안전한 데이터 흐름 제어
- ✅ 프레임 손실 최소화
- ✅ 타이밍 이슈 해결

**Pad Probe의 단점:**
- ❌ 복잡한 구현
- ❌ 디버깅 어려움
- ❌ 스레드 안전성 고려 필요

### 6.3 Streaming Branch만 재시작

**사용 사례:**
- 디코더 교체 (HW → SW)
- OSD 설정 변경
- 해상도 변경

```python
def _restart_streaming_branch(self):
    """스트리밍 브랜치만 재시작"""
    try:
        logger.info("[RESTART] Restarting streaming branch...")

        # 1. Valve 닫기
        self.streaming_valve.set_property("drop", True)
        time.sleep(0.2)

        # 2. 디코더와 이후 엘리먼트를 NULL로
        elements_to_restart = [
            self.pipeline.get_by_name("decoder"),
            self.pipeline.get_by_name("convert"),
            self.pipeline.get_by_name("scale"),
            self.video_sink
        ]

        for elem in elements_to_restart:
            if elem:
                elem.set_state(Gst.State.NULL)

        time.sleep(0.5)

        # 3. PLAYING으로 복구
        for elem in elements_to_restart:
            if elem:
                elem.set_state(Gst.State.PLAYING)

        # 4. Valve 열기
        time.sleep(0.5)
        self.streaming_valve.set_property("drop", False)

        logger.success("[RESTART] Streaming branch restarted")
        return True

    except Exception as e:
        logger.error(f"[RESTART] Error: {e}")
        return False
```

### 6.4 재시작 실패 시 Fallback

```python
def safe_restart_recording_branch(self):
    """안전한 녹화 브랜치 재시작 (실패 시 전체 재시작)"""

    # 1차 시도: 부분 재시작
    logger.info("[RECOVERY] Attempting partial restart...")
    success = self._recover_recording_branch()

    if success:
        logger.success("[RECOVERY] Partial restart succeeded")
        return True

    # 2차 시도: 전체 재시작
    logger.warning("[RECOVERY] Partial restart failed - falling back to full restart")

    try:
        # 전체 파이프라인 재시작
        self.stop()
        time.sleep(1)
        success = self.start()

        if success:
            logger.success("[RECOVERY] Full restart succeeded")
            # 녹화 재시작
            if self.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
                self.start_recording()
            return True
        else:
            logger.error("[RECOVERY] Full restart failed")
            return False

    except Exception as e:
        logger.error(f"[RECOVERY] Full restart error: {e}")
        return False
```

---

## 7. 실전 구현 패턴

### 7.1 종합 예외처리 클래스

```python
class RobustUnifiedPipeline(GstPipeline):
    """예외처리가 강화된 통합 파이프라인"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 에러 상태 추적
        self._streaming_branch_error = False
        self._recording_branch_error = False
        self._last_error_time = {}

        # 재연결 관리
        self.retry_count = 0
        self.max_retries = 10
        self.reconnect_timer = None

    def _on_bus_message(self, bus, message):
        """통합 에러 처리"""
        if message.type != Gst.MessageType.ERROR:
            return super()._on_bus_message(bus, message)

        err, debug = message.parse_error()
        src_name = message.src.get_name() if message.src else "unknown"
        error_code = err.code

        # 에러 분류
        error_type = self._classify_error(src_name, err, debug, error_code)

        # 에러 타입별 처리
        if error_type == ErrorType.RTSP_NETWORK:
            self._handle_rtsp_error(err)

        elif error_type == ErrorType.STORAGE_DISCONNECTED:
            self._handle_storage_error(err)

        elif error_type == ErrorType.DISK_FULL:
            self._handle_disk_full_error(err)

        elif error_type == ErrorType.DECODER:
            self._handle_decoder_error(err)

        elif error_type == ErrorType.VIDEO_SINK:
            self._handle_videosink_error(err)

        else:
            # 알 수 없는 에러
            self._handle_unknown_error(src_name, err)

    def _classify_error(self, src_name, err, debug, error_code):
        """에러 타입 분류"""
        error_str = str(err).lower()
        debug_str = str(debug).lower() if debug else ""

        # RTSP 네트워크 에러
        if (src_name == "source" and
            error_code == 9 and
            "could not read" in error_str):
            return ErrorType.RTSP_NETWORK

        # 저장소 분리
        if (src_name in ["splitmuxsink", "sink"] and
            error_code == 10 and
            "could not write" in error_str and
            ("permission denied" in debug_str or
             "file descriptor" in debug_str)):
            return ErrorType.STORAGE_DISCONNECTED

        # 디스크 Full
        if ("space" in error_str or
            "no space" in error_str):
            return ErrorType.DISK_FULL

        # 디코더 에러
        if "dec" in src_name and "decode" in error_str:
            return ErrorType.DECODER

        # Video sink 에러
        if "videosink" in src_name or "output window" in error_str:
            return ErrorType.VIDEO_SINK

        return ErrorType.UNKNOWN

    def _handle_rtsp_error(self, err):
        """RTSP 에러 처리 - 전체 재시작"""
        logger.critical(f"[RTSP] Network error: {err}")
        self.stop()
        self._schedule_reconnect()

    def _handle_storage_error(self, err):
        """저장소 에러 처리 - Recording Branch만 중지"""
        logger.critical(f"[STORAGE] USB disconnected: {err}")

        # 1. 녹화 중지
        self.stop_recording()

        # 2. 에러 플래그 설정
        self._recording_branch_error = True
        self._last_error_time["recording"] = time.time()

        # 3. UI 알림
        self._notify_recording_error("저장 장치가 분리되었습니다")

        logger.info("[STREAMING] Streaming continues")

    def _handle_disk_full_error(self, err):
        """디스크 Full 처리 - 자동 정리"""
        logger.critical(f"[DISK] Disk full: {err}")
        self._handle_disk_full()

    def _handle_decoder_error(self, err):
        """디코더 에러 처리 - 버퍼 플러시"""
        logger.warning(f"[DECODER] Decode error: {err}")

        # 버퍼 플러시
        self.pipeline.send_event(Gst.Event.new_flush_start())
        time.sleep(0.1)
        self.pipeline.send_event(Gst.Event.new_flush_stop(True))

        logger.info("[DECODER] Pipeline flushed")

    def _handle_videosink_error(self, err):
        """Video Sink 에러 처리 - 무시 또는 Streaming Branch 중지"""
        logger.warning(f"[VIDEOSINK] Display error: {err}")

        if not self.window_handle:
            # Headless 모드 - 무시
            logger.debug("[VIDEOSINK] Headless mode - error ignored")
            return

        # Streaming Branch만 중지
        self.streaming_valve.set_property("drop", True)
        self._is_streaming = False
        self._streaming_branch_error = True

        logger.info("[RECORDING] Recording continues")

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프)"""
        if self.retry_count >= self.max_retries:
            logger.error(f"Max retries ({self.max_retries}) reached")
            return

        # 지수 백오프
        delay = min(5 * (2 ** self.retry_count), 60)
        self.retry_count += 1

        logger.info(f"Reconnecting in {delay}s (attempt {self.retry_count}/{self.max_retries})")

        if self.reconnect_timer:
            self.reconnect_timer.cancel()

        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

    def _reconnect(self):
        """재연결 수행"""
        logger.info("Attempting to reconnect...")

        success = self.start()

        if success:
            logger.success("Reconnected successfully")
            self.retry_count = 0
        else:
            logger.error("Reconnect failed")
            self._schedule_reconnect()

    def start_recording(self):
        """녹화 시작 (에러 복구 포함)"""
        # 에러 상태 체크 및 복구
        if self._recording_branch_error:
            logger.warning("[RECOVERY] Attempting to recover recording branch...")

            if not self.safe_restart_recording_branch():
                logger.error("[RECOVERY] Failed to recover")
                return False

            logger.success("[RECOVERY] Recording branch recovered")

        # 정상 녹화 시작
        return super().start_recording()

# 사용 예시
pipeline = RobustUnifiedPipeline(
    rtsp_url="rtsp://admin:password@192.168.0.131:554/stream",
    camera_id="cam_01",
    camera_name="Front Door",
    mode=PipelineMode.BOTH
)

pipeline.create_pipeline()
pipeline.start()
```

### 7.2 에러 타입 Enum

```python
from enum import Enum, auto

class ErrorType(Enum):
    """에러 타입 분류"""
    RTSP_NETWORK = auto()          # RTSP 네트워크 끊김
    STORAGE_DISCONNECTED = auto()  # USB/HDD 분리
    DISK_FULL = auto()             # 디스크 공간 부족
    DECODER = auto()               # 디코더 에러
    VIDEO_SINK = auto()            # Video sink 에러
    RECORDING_BRANCH = auto()      # 녹화 브랜치 일반 에러
    STREAMING_BRANCH = auto()      # 스트리밍 브랜치 일반 에러
    UNKNOWN = auto()               # 알 수 없는 에러
```

### 7.3 상태 모니터링

```python
class PipelineHealthMonitor:
    """파이프라인 상태 모니터링"""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.monitoring = False
        self.last_buffer_time = {}

    def start(self):
        """모니터링 시작"""
        self.monitoring = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("Health monitoring started")

    def _monitor_loop(self):
        """모니터링 루프"""
        while self.monitoring:
            try:
                # 1. 브랜치별 상태 체크
                self._check_branch_health()

                # 2. 디스크 공간 체크
                self._check_disk_space()

                # 3. 메모리 사용량 체크
                self._check_memory_usage()

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            time.sleep(10)  # 10초마다

    def _check_branch_health(self):
        """브랜치 상태 체크"""
        status = self.pipeline.get_status()

        # 스트리밍 브랜치 체크
        if status["streaming_active"]:
            # 버퍼 수신 확인 (TODO: appsink로 버퍼 모니터링)
            pass

        # 녹화 브랜치 체크
        if status["recording_active"]:
            # 파일 생성 확인
            if self.pipeline.current_recording_file:
                file_path = Path(self.pipeline.current_recording_file)
                if file_path.exists():
                    # 파일 크기 증가 확인
                    size = file_path.stat().st_size
                    logger.debug(f"[HEALTH] Recording file size: {size} bytes")

    def _check_disk_space(self):
        """디스크 공간 체크"""
        storage_service = StorageService()
        free_gb = storage_service.get_free_space_gb()

        if free_gb < 5:
            logger.warning(f"[HEALTH] Low disk space: {free_gb:.2f}GB")

            # 사전 정리
            storage_service.auto_cleanup()

    def _check_memory_usage(self):
        """메모리 사용량 체크"""
        import psutil

        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)

        logger.debug(f"[HEALTH] Memory usage: {memory_mb:.2f}MB")

        if memory_mb > 500:  # 500MB 초과
            logger.warning(f"[HEALTH] High memory usage: {memory_mb:.2f}MB")
```

### 7.4 사용 예시

```python
# main.py
def main():
    Gst.init(None)

    # 파이프라인 생성
    pipeline = RobustUnifiedPipeline(
        rtsp_url="rtsp://admin:password@192.168.0.131:554/stream",
        camera_id="cam_01",
        camera_name="Front Door",
        mode=PipelineMode.BOTH
    )

    # 콜백 등록
    pipeline.register_recording_callback(on_recording_state_changed)

    # 파이프라인 시작
    pipeline.create_pipeline()
    pipeline.start()

    # 자동 녹화 시작 (설정에 따라)
    config = ConfigManager.get_instance()
    if config.is_auto_recording_enabled():
        pipeline.start_recording()

    # 헬스 모니터링 시작
    health_monitor = PipelineHealthMonitor(pipeline)
    health_monitor.start()

    # 메인 루프
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("Interrupted by user")
        pipeline.stop()

if __name__ == '__main__':
    main()
```

---

## 요약

### 핵심 개념
1. **Unified Pipeline** = 1개 파이프라인 + Tee + 여러 브랜치
2. **Valve** = 브랜치별 독립 제어 (drop 속성)
3. **에러 격리** = 한 브랜치 에러가 다른 브랜치에 영향 없음

### 브랜치 제어 원칙
- ✅ **Streaming Branch**: 실시간성 우선 (낮은 지연시간)
- ✅ **Recording Branch**: 안정성 우선 (데이터 손실 방지)
- ✅ **독립성**: 각 브랜치는 독립적으로 제어

### 예외 처리 전략
| 에러 타입 | 영향 범위 | 처리 방법 |
|----------|----------|----------|
| RTSP 네트워크 | 전체 | 전체 재시작 + 재연결 |
| USB 분리 | Recording | Recording Branch만 중지 |
| 디스크 Full | Recording | 자동 정리 + 재시작 |
| 디코더 에러 | Streaming | 버퍼 플러시 또는 재시작 |
| Video Sink | Streaming | 무시 또는 Streaming Branch 중지 |

### 구현 우선순위
1. **Valve 제어** - 기본 브랜치 on/off
2. **에러 분류** - 에러 타입별 처리
3. **Recording Branch 복구** - 부분 재시작
4. **RTSP 재연결** - 지수 백오프
5. **헬스 모니터링** - 사전 예방

---

**문서 버전:** 1.0
**작성일:** 2025-10-30
**대상 프로젝트:** nvr_gstreamer
**참고:** GStreamer 1.0, Python 3.8+
