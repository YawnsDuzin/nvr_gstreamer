# 카메라 재연결 시 녹화 파일 분할 문제 분석

## 문제 설명
카메라가 네트워크 끊김 후 재연결될 때, 파일이 설정된 시간(예: 10분)마다 분할되지 않고 하나의 파일로 계속 녹화되는 문제가 발생합니다.

## 현상
1. **정상 동작 시**: 녹화 파일이 설정된 `rotation_minutes`(예: 10분)마다 자동으로 분할됨
2. **재연결 후 문제**: 파일 분할이 작동하지 않고 하나의 파일로 계속 녹화됨
3. **영향**: 파일 크기가 과도하게 커짐, 파일 관리 어려움

## 원인 분석

### 1. **Splitmuxsink 상태 초기화 문제**

#### 문제 코드 위치: `gst_pipeline.py` line 630-647
```python
# 7. splitmuxsink 상태 확인 및 재시작 (EOS 상태에서 복구)
# 단, 전체 파이프라인이 새로 생성된 경우(재연결 후)는 건너뛰기
if self.splitmuxsink and not skip_splitmux_restart:
    current_state = self.splitmuxsink.get_state(0)[1]
    logger.debug(f"[RECORDING DEBUG] splitmuxsink current state: {current_state.value_nick}")

    # splitmuxsink를 READY로 전환 후 다시 PLAYING으로 전환 (EOS 상태 초기화)
    self.splitmuxsink.set_state(Gst.State.READY)
    time.sleep(0.1)

    # ⭐ 중요: READY 상태에서 설정이 초기화되므로 max-size-time 다시 설정
    self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
    logger.debug(f"[RECORDING DEBUG] Re-applied max-size-time: {self.file_duration_ns / Gst.SECOND}s")

    self.splitmuxsink.set_state(Gst.State.PLAYING)
    logger.debug("[RECORDING DEBUG] splitmuxsink restarted (READY -> PLAYING)")
elif skip_splitmux_restart:
    logger.info("[RECORDING DEBUG] Skipping splitmuxsink restart (fresh pipeline after reconnection)")
```

#### 문제점
- **네트워크 재연결 후** 새 파이프라인이 생성되면 `skip_splitmux_restart=True`로 설정됨
- 이 경우 `splitmuxsink`의 `max-size-time` 속성이 재설정되지 않을 수 있음
- 파이프라인 생성 시점(line 591)에만 설정되고, 재연결 후 재설정되지 않음

### 2. **Fragment ID 초기화 문제**

#### 문제 코드: `gst_pipeline.py` line 612, 765
```python
# start_recording() 메서드
self._recording_fragment_id = 0  # 프래그먼트 ID 초기화

# _on_format_location() 콜백
self._recording_fragment_id = fragment_id
```

#### 문제점
- 재연결 후 fragment ID가 제대로 관리되지 않을 가능성
- Splitmuxsink의 내부 fragment 카운터와 동기화 문제

### 3. **파이프라인 재생성 시 속성 유실**

#### 네트워크 재연결 프로세스
1. **RTSP 에러 발생** → `_handle_rtsp_error()` 호출
2. **비동기 정지 및 재연결** → `_async_stop_and_reconnect()` 실행
3. **파이프라인 정지** → `stop()` 호출로 기존 파이프라인 파괴
4. **재연결 시도** → `_reconnect()` → `start()` → 새 파이프라인 생성
5. **녹화 재시작** → `start_recording(skip_splitmux_restart=True)`

#### 핵심 문제
- 새 파이프라인 생성 시 `create_pipeline()` → `_create_recording_branch()` 실행
- Line 591에서 `max-size-time` 설정은 되지만, 파이프라인이 PLAYING 상태로 전환된 후 속성이 제대로 적용되지 않을 수 있음

### 4. **Splitmuxsink 내부 타이머 리셋 문제**

GStreamer의 splitmuxsink는 내부적으로 타이머를 사용하여 파일 분할을 관리합니다:
- **정상 동작**: 내부 타이머가 `max-size-time`에 도달하면 새 파일 생성
- **재연결 후 문제**: 파이프라인 재생성으로 인해 타이머가 초기화되지 않거나 잘못된 상태일 수 있음

## 해결 방법

### 방법 1: **강제 파일 분할 (권장)**

재연결 후 녹화 시작 시 즉시 새 파일로 분할:

```python
def start_recording(self, skip_splitmux_restart: bool = False) -> bool:
    # ... 기존 코드 ...

    # 재연결 후인 경우 (skip_splitmux_restart=True)
    if skip_splitmux_restart and self.splitmuxsink:
        # splitmuxsink의 max-size-time 재확인 및 설정
        current_max_time = self.splitmuxsink.get_property("max-size-time")
        if current_max_time != self.file_duration_ns:
            logger.warning(f"[RECORDING] max-size-time mismatch: {current_max_time} != {self.file_duration_ns}")
            self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
            logger.info(f"[RECORDING] Corrected max-size-time to {self.file_duration_ns / Gst.SECOND}s")

        # 강제로 새 파일 시작
        try:
            self.splitmuxsink.emit("split-now")
            logger.info("[RECORDING] Forced file split after reconnection")
        except Exception as e:
            logger.warning(f"[RECORDING] Failed to force split: {e}")

    # ... 나머지 코드 ...
```

### 방법 2: **Splitmuxsink 재초기화**

재연결 후에도 splitmuxsink를 재초기화:

```python
def start_recording(self, skip_splitmux_restart: bool = False) -> bool:
    # ... 기존 코드 ...

    # skip_splitmux_restart를 무시하고 항상 재초기화
    if self.splitmuxsink:
        # 현재 상태 저장
        current_state = self.splitmuxsink.get_state(0)[1]

        # READY 상태로 전환 (초기화)
        self.splitmuxsink.set_state(Gst.State.READY)
        time.sleep(0.1)

        # 모든 속성 재설정
        self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
        self.splitmuxsink.set_property("send-keyframe-requests", True)
        self.splitmuxsink.set_property("async-handling", True)

        # fragment ID 초기화
        self._recording_fragment_id = 0

        # PLAYING 상태로 복원
        self.splitmuxsink.set_state(Gst.State.PLAYING)
        logger.info("[RECORDING] Splitmuxsink fully reinitialized after reconnection")

    # ... 나머지 코드 ...
```

### 방법 3: **파이프라인 생성 시점 수정**

`_create_recording_branch()` 메서드에서 속성 설정 강화:

```python
def _create_recording_branch(self):
    # ... 기존 코드 ...

    # splitmuxsink 생성 및 설정
    self.splitmuxsink = Gst.ElementFactory.make("splitmuxsink", "splitmuxsink")

    # 파일 분할 시간 설정 (나노초 단위)
    self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)

    # ⭐ 추가: 최대 파일 크기 제한 (백업)
    # 시간 기반 분할이 실패할 경우를 대비
    max_file_size = 1024 * 1024 * 1024  # 1GB
    self.splitmuxsink.set_property("max-size-bytes", max_file_size)

    # ⭐ 추가: fragment-duration 설정 (MP4의 경우)
    if self.file_format == 'mp4':
        # muxer 직접 생성 및 설정
        mp4mux = Gst.ElementFactory.make("mp4mux", None)
        mp4mux.set_property("fragment-duration", 1000)  # 1초
        mp4mux.set_property("streamable", True)
        self.splitmuxsink.set_property("muxer", mp4mux)

    # ... 나머지 코드 ...
```

### 방법 4: **주기적 강제 분할 (Workaround)**

타이머를 사용하여 주기적으로 파일 분할 강제:

```python
def start_recording(self, skip_splitmux_restart: bool = False) -> bool:
    # ... 기존 코드 ...

    # 파일 분할 타이머 시작
    self._start_split_timer()

    # ... 나머지 코드 ...

def _start_split_timer(self):
    """파일 분할 타이머 시작"""
    if hasattr(self, '_split_timer') and self._split_timer:
        self._split_timer.cancel()

    def check_and_split():
        if self._is_recording and self.recording_start_time:
            # 현재 녹화 시간 계산
            recording_duration = time.time() - self.recording_start_time
            split_interval_sec = self.file_duration_ns / Gst.SECOND

            # 분할 시간 초과 확인
            if recording_duration >= split_interval_sec:
                try:
                    self.splitmuxsink.emit("split-now")
                    logger.info(f"[RECORDING] Forced file split after {recording_duration:.1f}s")
                    self.recording_start_time = time.time()  # 타이머 리셋
                except:
                    pass

            # 다음 체크 스케줄
            if self._is_recording:
                self._split_timer = threading.Timer(10.0, check_and_split)  # 10초마다 체크
                self._split_timer.daemon = True
                self._split_timer.start()

    # 첫 체크 스케줄
    self._split_timer = threading.Timer(10.0, check_and_split)
    self._split_timer.daemon = True
    self._split_timer.start()
```

## 권장 해결책

### 즉각적인 해결 (최소 수정)

**방법 1**을 적용하여 재연결 후 녹화 시작 시 강제로 새 파일을 생성하도록 합니다:

```python
# gst_pipeline.py의 start_recording() 메서드 수정
# Line 646 근처에 추가

if skip_splitmux_restart and self.splitmuxsink:
    # 재연결 후 max-size-time 재설정
    self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
    logger.info(f"[RECORDING] Re-applied max-size-time after reconnection: {self.file_duration_ns / Gst.SECOND}s")

    # 즉시 새 파일로 분할 (선택적)
    try:
        self.splitmuxsink.emit("split-now")
        logger.info("[RECORDING] Starting with new file after reconnection")
    except:
        pass  # split-now가 지원되지 않으면 무시
```

### 근본적인 해결 (안정성 향상)

**방법 2 + 방법 3**을 조합하여 적용:
1. 재연결 여부와 관계없이 항상 splitmuxsink 재초기화
2. 파이프라인 생성 시 백업 분할 조건 추가 (max-size-bytes)
3. 파일 분할 모니터링 로그 강화

## 테스트 방법

1. **재연결 시나리오 테스트**
   ```bash
   # 1. 녹화 시작
   # 2. 네트워크 케이블 분리 (또는 카메라 전원 차단)
   # 3. 30초 후 네트워크 복구
   # 4. 자동 재연결 및 녹화 재개 확인
   # 5. 설정된 시간(예: 10분) 후 파일 분할 확인
   ```

2. **로그 확인**
   ```
   [RECORDING DEBUG] max-size-time: 600s
   [RECORDING DEBUG] Creating recording file: xxx_20251105_140000.mp4 (fragment #0)
   [RECORDING DEBUG] Creating recording file: xxx_20251105_141000.mp4 (fragment #1)
   ```

3. **파일 시스템 확인**
   - 녹화 디렉토리에서 파일 크기와 생성 시간 확인
   - 파일이 정해진 시간마다 새로 생성되는지 확인

## 추가 고려사항

1. **GStreamer 버전 호환성**
   - GStreamer 1.18.4에서는 `split-now` 시그널이 다르게 동작할 수 있음
   - `split-after` 또는 `split-next` 시그널 사용 고려

2. **키프레임 정렬**
   - 파일 분할은 키프레임에서만 가능
   - `send-keyframe-requests=True` 설정 확인

3. **Fragment Duration**
   - MP4 format 사용 시 fragment-duration 설정 중요
   - 너무 큰 값은 파일 분할을 방해할 수 있음

4. **모니터링 강화**
   - 파일 크기 모니터링 추가
   - 분할 실패 시 알림 기능
   - 통계 정보 수집 (평균 파일 크기, 분할 주기 등)