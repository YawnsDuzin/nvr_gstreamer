# 프로그램 시작 시 자동 스트리밍 및 녹화 처리 로직

## 설정값 (IT_RNVR.json)

```json
{
  "cameras": [{
    "streaming_enabled_start": true,   // 프로그램 시작 시 자동 스트리밍 연결
    "recording_enabled_start": true    // 프로그램 시작 시 자동 녹화 시작
  }]
}
```

## 전체 처리 흐름 (순서도)

### Phase 1: 프로그램 초기화 (main_window.py)

```
[프로그램 시작]
    ↓
[MainWindow.__init__()]
    ↓
├─ ConfigManager.get_instance() - 싱글톤 설정 로더
├─ _setup_ui() - UI 컴포넌트 생성
│   ├─ GridView 생성 (1x1 레이아웃)
│   ├─ CameraListWidget 생성
│   ├─ RecordingControlWidget 생성
│   └─ PlaybackWidget 생성
├─ _setup_menus() - 메뉴바 구성
├─ _setup_status_bar() - 상태바 구성
├─ _load_dock_state() - Dock 상태 복원
└─ _setup_connections() ← **여기서 자동 연결 시작**
    ↓
    [_setup_connections() 세부 절차]
    ├─ 1. _auto_assign_cameras() - 카메라를 채널에 할당
    ├─ 2. _assign_window_handles_to_streams() - 윈도우 핸들 사전 할당
    ├─ 3. _populate_recording_control() - 녹화 컨트롤 위젯 초기화
    └─ 4. _auto_connect_cameras() ← **자동 연결 진입점**
```

---

### Phase 2: 자동 연결 시작 (_auto_connect_cameras)

**위치**: `ui/main_window.py:1036-1071`

```
[_auto_connect_cameras()]
    ↓
[설정에서 enabled 카메라 조회]
cameras = config_manager.get_enabled_cameras()
    ↓
[각 카메라에 대해 반복]
for camera in cameras:
    ↓
    [streaming_enabled_start 확인]
    if camera.streaming_enabled_start == True:
        ↓
        [CameraListWidget에서 카메라 아이템 찾기]
        camera_item = camera_list.camera_items[camera.camera_id]
        ↓
        [아이템 선택 (UI 상태)]
        camera_list.list_widget.setCurrentItem(camera_item)
        ↓
        [카메라 연결 실행]
        camera_list._connect_camera() ← **CameraListWidget로 진입**
```

**핵심 로그**:
```
[INFO] Auto-connecting camera: Main Camera (cam_01)
```

---

### Phase 3: 카메라 연결 (_connect_camera)

**위치**: `ui/camera_list_widget.py:307-333`

```
[CameraListWidget._connect_camera()]
    ↓
[현재 선택된 카메라 아이템 확인]
camera_item = self.list_widget.currentItem()
    ↓
[스트림이 존재하고 연결되지 않은 경우]
if camera_item.camera_stream and not is_connected():
    ↓
    [윈도우 핸들 찾기]
    window_handle = None
    for channel in main_window.grid_view.channels:
        if channel.camera_id == camera_id:
            window_handle = channel.get_window_handle()
            break
    ↓
    [recording_enabled_start 확인]
    enable_recording = camera_item.camera_config.recording_enabled_start  # True
    ↓
    [CameraStream.connect() 호출]
    camera_item.camera_stream.connect(
        window_handle=window_handle,
        enable_recording=enable_recording  # True가 전달됨
    ) ← **CameraStream으로 진입**
    ↓
    [성공 시 시그널 발생]
    self.camera_connected.emit(camera_id)
```

**핵심 로그**:
```
[DEBUG] Found window handle for cam_01: 1234567
[INFO] Connecting to camera: Main Camera (ID: cam_01)
```

---

### Phase 4: 스트림 연결 및 파이프라인 생성 (camera_stream.connect)

**위치**: `camera/streaming.py:67-124`

```
[CameraStream.connect(enable_recording=True)]
    ↓
[파라미터 정리]
- frame_callback: None (GstPipeline에서 미지원)
- window_handle: 1234567
- enable_recording: True ← **여기 주목!**
    ↓
[모드 결정]
mode = PipelineMode.BOTH if enable_recording else PipelineMode.STREAMING_ONLY
# enable_recording=True이므로 mode=PipelineMode.BOTH
    ↓
[GstPipeline 객체 생성]
self.gst_pipeline = GstPipeline(
    rtsp_url=self.rtsp_url,
    camera_id=self.config.camera_id,
    camera_name=self.config.name,
    window_handle=window_handle,
    mode=PipelineMode.BOTH  ← **BOTH 모드**
)
    ↓
[파이프라인 생성]
if not self.gst_pipeline.create_pipeline():
    raise Exception("Failed to create pipeline")
    ↓
    [GstPipeline.create_pipeline() 세부]
    ├─ RTSP 소스 생성 (rtspsrc)
    ├─ Depay + Parse 엘리먼트 생성
    ├─ Tee 엘리먼트 생성 (스트림 분기)
    ├─ _create_streaming_branch() - 스트리밍 브랜치 생성
    │   ├─ stream_queue
    │   ├─ streaming_valve (초기: drop=False, 열림)
    │   ├─ decoder → convert → textoverlay → scale → video_sink
    │   └─ Tee → stream_queue 연결
    ├─ _create_recording_branch() - 녹화 브랜치 생성
    │   ├─ record_queue
    │   ├─ recording_valve (초기: drop=True, 닫힘)
    │   ├─ record_parse → splitmuxsink
    │   └─ Tee → record_queue 연결
    └─ _apply_mode_settings() - 모드별 Valve 설정
        ↓
        [mode=PipelineMode.BOTH인 경우]
        - streaming_valve.drop = False (열림)
        - recording_valve.drop = False (열림) ← **녹화 준비**
    ↓
[파이프라인 시작]
if not self.gst_pipeline.start():
    raise Exception("Failed to start pipeline") ← **GstPipeline.start()로 진입**
```

**핵심 로그**:
```
[DEBUG] Creating unified pipeline for Main Camera (mode: BOTH)
[DEBUG] Streaming branch created successfully
[DEBUG] Recording branch created successfully with splitmuxsink
[INFO] [VALVE DEBUG] Mode: BOTH - Setting Streaming valve drop=False (open), Recording valve drop=False (open)
```

---

### Phase 5: 파이프라인 시작 및 자동 녹화 트리거 (gst_pipeline.start)

**위치**: `camera/gst_pipeline.py:650-803`

```
[GstPipeline.start()]
    ↓
[파이프라인 상태 전환]
├─ pipeline.set_state(Gst.State.READY)
├─ pipeline.set_state(Gst.State.PAUSED)
└─ pipeline.set_state(Gst.State.PLAYING)
    ↓
[모드별 녹화 파일 설정]
if self.mode in [PipelineMode.RECORDING_ONLY, PipelineMode.BOTH]:
    valve_drop = self.recording_valve.get_property("drop")
    if not valve_drop:  # drop=False이면 녹화 예정
        ↓
        [녹화 파일 경로 생성]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_dir = recordings/cam_01/20251029/
        location_pattern = "recordings/cam_01/20251029/cam_01_20251029_143000_%05d.mp4"
        ↓
        [splitmuxsink에 location 설정]
        self.splitmuxsink.set_property("location", location_pattern)
        ↓
        [녹화 상태 업데이트]
        self._is_recording = True
        self.recording_start_time = time.time()
        ↓
        [**녹화 시작 콜백 호출**] ← **UI 동기화 시작점**
        self._notify_recording_state_change(True)
            ↓
            [등록된 모든 콜백 실행]
            for callback in self._recording_state_callbacks:
                callback(self.camera_id, True)
```

**핵심 로그**:
```
[INFO] [RECORDING DEBUG] Auto-recording started with splitmuxsink: recordings/cam_01/20251029/cam_01_20251029_143000.mp4
[DEBUG] [RECORDING SYNC] Notifying recording state change: cam_01 -> True
```

**⚠️ 중요 타이밍 이슈**:
- 이 시점에서 `_notify_recording_state_change(True)`가 호출되지만
- 콜백은 아직 **등록되지 않음** (콜백 등록은 `_on_camera_connected()`에서 수행)
- 따라서 **UI가 업데이트되지 않음** ← 현재 문제의 원인!

---

### Phase 6: 연결 완료 시그널 처리 (_on_camera_connected)

**위치**: `ui/main_window.py:1181-1245`

```
[시그널 발생]
camera_list.camera_connected.emit(camera_id)
    ↓
[MainWindow._on_camera_connected(camera_id)]
    ↓
[카메라 스트림 조회]
stream = self.camera_list.get_camera_stream(camera_id)
    ↓
[채널 업데이트 - 윈도우 핸들 설정]
for channel in self.grid_view.channels:
    if channel.camera_id == camera_id:
        channel.set_connected(True)
        if window_handle and stream.gst_pipeline:
            stream.gst_pipeline.video_sink.set_window_handle(window_handle)
        break
    ↓
[**녹화 상태 콜백 등록**] ← **여기서 비로소 콜백 등록!**
if stream and stream.gst_pipeline:
    def on_recording_state_change(cam_id: str, is_recording: bool):
        # Grid View 업데이트
        for channel in self.grid_view.channels:
            if channel.camera_id == cam_id:
                channel.set_recording(is_recording)
                break
        # Recording Control Widget 업데이트
        self.recording_control.update_recording_status(cam_id, is_recording)
        # 시그널 발생
        if is_recording:
            self.recording_control.recording_started.emit(cam_id)
    ↓
    stream.gst_pipeline.register_recording_callback(on_recording_state_change)
    ↓
[자동 녹화 체크]
camera_config = self.config_manager.get_camera(camera_id)
if camera_config.recording_enabled_start:
    ↓
    [500ms 지연 후 녹화 시작 시도]
    QTimer.singleShot(500, lambda: self._auto_start_recording(camera_id))
        ↓
        [_auto_start_recording(camera_id)]
        ├─ [이미 녹화 중인지 확인]
        │   if self.recording_control.is_recording(camera_id):
        │       return  # 이미 녹화 중이면 종료
        ├─ [녹화 시작]
        │   self.recording_control.start_recording(camera_id)
        └─ [UI 상태 업데이트]
            self.recording_control.update_recording_status(camera_id, True)
```

**핵심 로그**:
```
[INFO] Camera connected: cam_01
[DEBUG] [UI SYNC] Registered recording callback for cam_01
[INFO] Auto-recording enabled for Main Camera (cam_01)
[INFO] ✓ Auto-started recording for camera: cam_01
```

**⚠️ 타이밍 문제**:
1. `GstPipeline.start()` → `_notify_recording_state_change(True)` 호출 (콜백 없음)
2. `camera_connected` 시그널 발생
3. `_on_camera_connected()` → 콜백 등록 (이미 늦음)
4. 500ms 후 `_auto_start_recording()` 호출 → 이미 녹화 중이므로 중복 시작 방지됨

---

## 타임라인 분석 (시간순)

```
T=0ms    : MainWindow 초기화 시작
T=50ms   : CameraListWidget 생성, 카메라 설정 로드
T=100ms  : _auto_connect_cameras() 진입
T=150ms  : CameraStream.connect(enable_recording=True) 호출
T=200ms  : GstPipeline 생성 (mode=BOTH)
T=250ms  : create_pipeline() - Valve 상태 설정
           - streaming_valve: drop=False (열림)
           - recording_valve: drop=False (열림)
T=300ms  : GstPipeline.start() 진입
T=500ms  : RTSP 연결 성공, PLAYING 상태 전환
T=550ms  : ⚠️ _notify_recording_state_change(True) 호출
           → 콜백 없음 (아직 등록 안 됨) ← **UI 업데이트 실패**
T=600ms  : camera_connected 시그널 발생
T=650ms  : _on_camera_connected() 진입
T=700ms  : ✅ register_recording_callback() 호출 (콜백 등록 완료)
T=750ms  : QTimer.singleShot(500, ...) 등록 (자동 녹화 예약)
T=1250ms : _auto_start_recording() 호출
           → is_recording() 체크 → 이미 True (녹화 중)
           → 중복 시작 방지로 return

결과: 녹화는 정상 동작하지만, UI는 "녹화 중지" 상태로 표시됨!
```

---

## 문제 원인 정리

### 1. 콜백 등록 타이밍 문제

- **콜백 호출 시점**: `GstPipeline.start()` 내부 (T=550ms)
- **콜백 등록 시점**: `_on_camera_connected()` 내부 (T=700ms)
- **시간 차**: 약 150ms (콜백 등록보다 호출이 먼저 발생)

### 2. 이벤트 순서

```
[올바른 순서 (이상적)]
1. GstPipeline 생성
2. 콜백 등록 ← **먼저 등록해야 함**
3. pipeline.start()
4. 자동 녹화 시작
5. _notify_recording_state_change() ← **UI 업데이트 성공**

[현재 순서 (문제)]
1. GstPipeline 생성
2. pipeline.start()
3. 자동 녹화 시작
4. _notify_recording_state_change() ← **콜백 없음, UI 업데이트 실패**
5. camera_connected 시그널
6. 콜백 등록 ← **너무 늦음**
```

### 3. 영향받는 UI 컴포넌트

1. **StreamVideoWidget (Grid View)**
   - `channel.set_recording(True)` 호출 안 됨
   - 녹화 인디케이터(빨간 점) 표시 안 됨

2. **RecordingControlWidget**
   - `update_recording_status(camera_id, True)` 호출 안 됨
   - 녹화 상태 아이콘 업데이트 안 됨
   - "Start Recording" 버튼 비활성화 안 됨

---

## 해결 방안

### 방안 1: 콜백 조기 등록 (추천)

**개념**: `CameraStream.connect()` 호출 전에 콜백을 미리 등록

```python
# ui/camera_list_widget.py:_add_camera_item()
stream = CameraStream(stream_config)

# 파이프라인 생성 전에 콜백 등록
if self.main_window and hasattr(self.main_window, '_create_recording_callback'):
    callback = self.main_window._create_recording_callback(camera_id)
    stream.register_recording_callback(callback)

self.camera_streams[camera_id] = stream
```

**장점**:
- 모든 녹화 상태 변경을 UI에 반영 가능
- 자동 녹화뿐 아니라 수동 녹화도 커버
- 근본적인 해결책

**단점**:
- 코드 구조 변경 필요

---

### 방안 2: UI 상태 강제 동기화

**개념**: `_on_camera_connected()`에서 파이프라인 상태를 확인하여 UI 강제 업데이트

```python
# ui/main_window.py:_on_camera_connected()
def _on_camera_connected(self, camera_id: str):
    stream = self.camera_list.get_camera_stream(camera_id)

    # 콜백 등록
    stream.gst_pipeline.register_recording_callback(on_recording_state_change)

    # 이미 녹화 중인지 확인하고 UI 동기화
    status = stream.gst_pipeline.get_status()
    if status['is_recording']:
        # 녹화 중이면 UI 강제 업데이트
        for channel in self.grid_view.channels:
            if channel.camera_id == camera_id:
                channel.set_recording(True)
                break
        self.recording_control.update_recording_status(camera_id, True)
```

**장점**:
- 간단한 수정으로 해결 가능
- 기존 구조 유지

**단점**:
- 임시방편 (근본 원인 미해결)
- 다른 녹화 상태 변경도 놓칠 수 있음

---

### 방안 3: 자동 녹화 지연 시작

**개념**: `GstPipeline.start()`에서 자동 녹화를 즉시 시작하지 않고, `_on_camera_connected()`에서 시작

```python
# camera/gst_pipeline.py:start()
def start(self):
    # ... 파이프라인 시작 ...

    # 자동 녹화 시작 제거 (콜백 등록 전이므로)
    # if self.mode in [RECORDING_ONLY, BOTH]:
    #     self._notify_recording_state_change(True)  # 제거

    return True

# ui/main_window.py:_on_camera_connected()
def _on_camera_connected(self, camera_id):
    # 콜백 등록
    stream.gst_pipeline.register_recording_callback(on_recording_state_change)

    # 여기서 녹화 시작 (콜백 등록 후)
    if camera_config.recording_enabled_start:
        stream.gst_pipeline.start_recording()  # 명시적 호출
```

**장점**:
- 타이밍 문제 완전 해결
- 명확한 제어 흐름

**단점**:
- 녹화 시작 시점 변경 (약간의 지연 발생)
- 파이프라인 로직 수정 필요

---

## 권장 해결책: 방안 1 (콜백 조기 등록)

**이유**:
1. 근본적인 타이밍 문제 해결
2. 모든 녹화 상태 변경 이벤트를 UI에 반영 가능
3. 확장성 우수 (향후 추가 콜백도 동일한 패턴으로 처리 가능)

**구현 단계**:
1. `MainWindow._create_recording_callback(camera_id)` 메서드 생성
2. `CameraStream.register_recording_callback()` 메서드 추가 (pending queue 지원)
3. `CameraListWidget._add_camera_item()`에서 콜백 조기 등록
4. `CameraStream.connect()` 내부에서 pending 콜백을 파이프라인에 등록

이 방식으로 타이밍 문제를 근본적으로 해결할 수 있습니다.
