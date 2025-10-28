# GStreamer 파이프라인 구조 및 시스템 연관 분석

## 목차
1. [개요](#개요)
2. [핵심 파이프라인 구조](#핵심-파이프라인-구조)
3. [클래스 계층 구조](#클래스-계층-구조)
4. [설정 시스템 연동](#설정-시스템-연동)
5. [UI 연동 메커니즘](#ui-연동-메커니즘)
6. [데이터 흐름](#데이터-흐름)
7. [제어 흐름](#제어-흐름)

---

## 개요

IT_RNVR 시스템은 **Unified Pipeline Pattern**을 사용하여 라즈베리파이에서 CPU 사용률을 ~50% 감소시키는 효율적인 NVR 시스템입니다.

### 핵심 혁신

**단일 디코더 + Tee 분기 방식**으로 스트리밍과 녹화를 동시 처리합니다.

```
기존 방식 (비효율):
├─ 스트리밍 파이프라인: RTSP → Decode → Display  (CPU 50%)
└─ 녹화 파이프라인: RTSP → Decode → MP4 File      (CPU 50%)
   총 CPU 사용: 100%

개선된 통합 방식:
RTSP → Decode → Tee ─┬─→ Display    (CPU 50% 감소!)
                     └─→ MP4 File
   총 CPU 사용: 50%
```

---

## 핵심 파이프라인 구조

### 1. UnifiedPipeline 아키텍처

#### 파이프라인 구성 요소

```
┌─────────────────────────────────────────────────────────────────┐
│                     RTSP Source (rtspsrc)                       │
│  - location: RTSP URL                                           │
│  - latency: 200ms (기본값, IT_RNVR.json에서 설정 가능)          │
│  - protocols: TCP                                               │
│  - tcp-timeout: 10000ms                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RTP H264 Depayloader                          │
│  rtph264depay: RTP 패킷에서 H.264 스트림 추출                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      H264 Parser                                │
│  h264parse: H.264 스트림 파싱 및 프레임 분리                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Tee (분기점)                            │
│  - allow-not-linked: True                                       │
│  - pull-mode: 1 (GST_TEE_PULL_MODE_SINGLE)                      │
│                                                                 │
│  ┌───────────────────┬─────────────────────┐                   │
│  │ src_0 (스트리밍)  │  src_1 (녹화)        │                   │
│  └────────┬──────────┴──────────┬──────────┘                   │
└───────────┼─────────────────────┼───────────────────────────────┘
            │                     │
            ▼                     ▼
    [스트리밍 브랜치]         [녹화 브랜치]
```

### 2. 스트리밍 브랜치 (Streaming Branch)

```
Tee (src_0)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stream Queue (stream_queue)                                    │
│  - max-size-buffers: 5                                          │
│  - max-size-time: 1초                                           │
│  - leaky: 2 (downstream leaky - 오래된 프레임 버림)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Streaming Valve (streaming_valve)                              │
│  - drop: False (스트리밍 ON) / True (스트리밍 OFF)              │
│  → 런타임 중 스트리밍 제어 가능                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  H264 Decoder (decoder)                                         │
│  자동 선택 우선순위:                                            │
│  1. v4l2h264dec (RPi 4+, 하드웨어 가속)                         │
│  2. omxh264dec (RPi 3 이하, 하드웨어 가속)                      │
│  3. avdec_h264 (소프트웨어 디코더, 폴백)                        │
│  → use_hardware_acceleration 설정에 따라 제어                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Video Convert (convert)                                        │
│  videoconvert: 픽셀 포맷 변환 (decoder → raw video)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Text Overlay (text_overlay) - OSD                              │
│  textoverlay: 카메라 이름 및 타임스탬프 표시                     │
│  - font-desc: "Sans Bold 14" (기본값)                           │
│  - color: 0xFFFFFFFF (흰색, RGB)                                │
│  - shaded-background: True                                      │
│  - valignment: top/bottom (IT_RNVR.json)                        │
│  - halignment: left/right (IT_RNVR.json)                        │
│  - text: "{카메라명} | {타임스탬프}"                            │
│  → 1초마다 타임스탬프 자동 업데이트                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Video Scale (scale)                                            │
│  videoscale: 비디오 크기 조정                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Caps Filter (caps_filter)                                      │
│  capsfilter: 해상도 강제 설정                                    │
│  - caps: "video/x-raw,width=1280,height=720"                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Final Queue (final_queue)                                      │
│  - max-size-buffers: 2 (최소 버퍼)                              │
│  - leaky: 2 (downstream leaky)                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Video Sink (videosink)                                         │
│  플랫폼별 자동 선택:                                            │
│  - Windows: d3d11videosink → d3dvideosink → autovideosink      │
│  - macOS: osxvideosink → autovideosink → glimagesink           │
│  - Linux/RPi: glimagesink → xvimagesink → ximagesink           │
│                                                                 │
│  속성:                                                          │
│  - sync: False (비동기 렌더링, 지연 최소화)                     │
│  - qos: True (QoS 활성화)                                       │
│  - max-lateness: 20ms                                           │
│  - force-aspect-ratio: True                                     │
│  - window_handle: PyQt5 위젯 핸들 (UI 연동)                     │
└─────────────────────────────────────────────────────────────────┘
```

### 3. 녹화 브랜치 (Recording Branch)

```
Tee (src_1)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Record Queue (record_queue)                                    │
│  - max-size-buffers: 0 (무제한)                                 │
│  - max-size-time: 5초                                           │
│  - max-size-bytes: 50MB                                         │
│  - leaky: 0 (no leaky - 모든 데이터 보존)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Recording Valve (recording_valve)                              │
│  - drop: True (녹화 OFF, 초기값) / False (녹화 ON)              │
│  → start_recording() / stop_recording()로 제어                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  H264 Parse (record_parse)                                      │
│  h264parse: 녹화용 H.264 스트림 파싱                            │
│  → 디코딩 없이 원본 H.264 스트림 사용 (CPU 절약)                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  MP4 Muxer (muxer)                                              │
│  mp4mux: H.264 스트림을 MP4 컨테이너로 감싸기                   │
│  - fragment-duration: 1000ms (IT_RNVR.json)                     │
│  - streamable: True                                             │
│  - faststart: True                                              │
│  - movie-timescale: 90000                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  File Sink (filesink)                                           │
│  filesink: MP4 파일로 저장                                       │
│  - location: recordings/{camera_id}/{date}/{timestamp}.mp4      │
│  → start_recording() 호출 시 파일 경로 설정                     │
│  → 파일 회전: 10분마다 새 파일 생성 (rotation_minutes 설정)     │
└─────────────────────────────────────────────────────────────────┘
```

### 4. 파이프라인 모드 (PipelineMode)

```python
class PipelineMode(Enum):
    STREAMING_ONLY = "streaming"   # 스트리밍만 (recording_valve=drop)
    RECORDING_ONLY = "recording"   # 녹화만 (streaming_valve=drop)
    BOTH = "both"                  # 스트리밍 + 녹화 (둘 다 활성화)
```

**Valve 기반 모드 제어:**

| 모드              | streaming_valve | recording_valve | 설명                    |
|-------------------|-----------------|-----------------|-------------------------|
| STREAMING_ONLY    | drop=False      | drop=True       | 화면 표시만             |
| RECORDING_ONLY    | drop=True       | drop=True       | 녹화만 (별도 시작 필요) |
| BOTH              | drop=False      | drop=True       | 둘 다 (녹화 별도 시작)  |

---

## 클래스 계층 구조

### 1. 파이프라인 관리 계층

```
┌────────────────────────────────────────────────────────────────┐
│                      CameraStream                              │
│  - 개별 카메라 스트림 핸들러                                   │
│  - 연결 상태 관리 (DISCONNECTED/CONNECTING/CONNECTED/ERROR)    │
│  - 자동 재연결 로직 (max_reconnect_attempts)                   │
│                                                                │
│  주요 메서드:                                                  │
│  - connect(enable_recording=False) → PipelineManager 생성      │
│  - disconnect()                                                │
│  - reconnect()                                                 │
│  - is_connected() → bool                                       │
└────────────────────────┬───────────────────────────────────────┘
                         │ 소유 (1:1)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                   PipelineManager                              │
│  - UnifiedPipeline 래퍼 클래스                                 │
│  - 파이프라인 생명주기 관리                                    │
│                                                                │
│  주요 메서드:                                                  │
│  - create_unified_pipeline(mode: PipelineMode) → bool         │
│  - start() → bool                                              │
│  - stop()                                                      │
│  - start_recording() → bool                                    │
│  - stop_recording() → bool                                     │
│  - set_window_handle(handle)                                   │
└────────────────────────┬───────────────────────────────────────┘
                         │ 소유 (1:1)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                   UnifiedPipeline                              │
│  - 실제 GStreamer 파이프라인 구현                              │
│  - Tee 기반 스트리밍/녹화 통합 처리                            │
│                                                                │
│  핵심 속성:                                                    │
│  - pipeline: Gst.Pipeline                                      │
│  - tee: Gst.Element                                            │
│  - streaming_valve: Gst.Element                                │
│  - recording_valve: Gst.Element                                │
│  - video_sink: Gst.Element                                     │
│  - file_sink: Gst.Element                                      │
│  - text_overlay: Gst.Element (OSD)                             │
│  - mode: PipelineMode                                          │
│  - _is_playing: bool                                           │
│  - _is_recording: bool                                         │
│                                                                │
│  핵심 메서드:                                                  │
│  - create_pipeline() → bool                                    │
│  - _create_streaming_branch()                                  │
│  - _create_recording_branch()                                  │
│  - start() → bool                                              │
│  - stop()                                                      │
│  - start_recording() → bool                                    │
│  - stop_recording() → bool                                     │
│  - _rotate_recording_file()                                    │
│  - _schedule_file_rotation()                                   │
│  - _stop_rotation_timer()                                      │
│  - set_mode(mode: PipelineMode)                                │
│  - get_status() → Dict                                         │
└────────────────────────────────────────────────────────────────┘
```

### 2. UI 계층 구조

```
┌────────────────────────────────────────────────────────────────┐
│                      MainWindow                                │
│  - QMainWindow 메인 창                                         │
│  - Dock 위젯 관리 (Camera List, Recording Control, Playback)   │
│  - 시그널/슬롯 연결                                            │
│                                                                │
│  주요 컴포넌트:                                                │
│  - grid_view: GridViewWidget                                   │
│  - camera_list: CameraListWidget                               │
│  - recording_control: RecordingControlWidget                   │
│  - playback_widget: PlaybackWidget                             │
│                                                                │
│  시그널 핸들러:                                                │
│  - _on_camera_connected(camera_id)                             │
│    → 자동 녹화 시작 (recording_enabled=true)                   │
│    → Recording Control UI 동기화                               │
│  - _on_recording_started(camera_id)                            │
│  - _on_recording_stopped(camera_id)                            │
└────────────────┬───────────────┬───────────────┬───────────────┘
                 │               │               │
        ┌────────▼───────┐  ┌───▼────────┐  ┌──▼──────────────┐
        │  GridViewWidget│  │CameraList  │  │RecordingControl │
        │                │  │Widget      │  │Widget           │
        │ 1~16 channels  │  │            │  │                 │
        │ VideoWidget[]  │  │Camera List │  │Start/Stop       │
        │                │  │+Stream 관리 │  │녹화 제어         │
        └────────────────┘  └─────┬──────┘  └──┬──────────────┘
                                  │            │
                         ┌────────▼────────────▼─────────┐
                         │   CameraStream (각 카메라)    │
                         │    ↓                          │
                         │   PipelineManager             │
                         │    ↓                          │
                         │   UnifiedPipeline             │
                         └───────────────────────────────┘
```

### 3. 설정 관리 계층

```
┌────────────────────────────────────────────────────────────────┐
│                   ConfigManager (Singleton)                    │
│  - JSON 기반 설정 관리 (IT_RNVR.json)                          │
│  - 단일 인스턴스 패턴 (get_instance())                         │
│                                                                │
│  주요 설정 데이터:                                             │
│  - app_config: AppConfig                                       │
│  - ui_config: UIConfig                                         │
│  - cameras: List[CameraConfigData]                             │
│  - streaming_config: Dict (streaming 섹션)                     │
│  - logging_config: Dict (logging 섹션)                         │
│                                                                │
│  주요 메서드:                                                  │
│  - get_instance() → ConfigManager (싱글톤)                     │
│  - get_camera(camera_id) → CameraConfigData                    │
│  - get_all_cameras() → List[CameraConfigData]                  │
│  - get_enabled_cameras() → List[CameraConfigData]              │
│  - get_streaming_config() → Dict                               │
│  - save_ui_config()                                            │
│  - update_ui_window_state(x, y, width, height)                 │
│  - update_ui_dock_state(...)                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 설정 시스템 연동

### 1. IT_RNVR.json 구조

```json
{
  "app": {
    "app_name": "IT_RNVR",
    "version": "1.0.0"
  },
  "ui": {
    "theme": "dark",
    "show_status_bar": true,
    "fullscreen_on_start": false,
    "window_state": {
      "x": 1920,
      "y": 0,
      "width": 1931,
      "height": 1061
    },
    "dock_state": {
      "camera_visible": true,
      "recording_visible": true,
      "playback_visible": false
    }
  },
  "streaming": {
    "default_layout": [1, 1],
    "latency_ms": 200,
    "tcp_timeout": 10000,
    "connection_timeout": 10,
    "use_hardware_acceleration": true,
    "show_timestamp": true,
    "show_camera_name": true,
    "osd_font_size": 14,
    "osd_font_color": [255, 255, 255],
    "osd_valignment": "top",
    "osd_halignment": "left",
    "osd_xpad": 10,
    "osd_ypad": 10
  },
  "cameras": [
    {
      "camera_id": "cam_01",
      "name": "Main Camera",
      "rtsp_url": "rtsp://admin:password@192.168.0.131:554/stream",
      "enabled": true,
      "recording_enabled": true
    }
  ],
  "recording": {
    "enabled": true,
    "base_path": "./recordings",
    "file_format": "mp4",
    "rotation_minutes": 10,
    "retention_days": 30,
    "fragment_duration_ms": 1000
  }
}
```

### 2. 설정 → 파이프라인 매핑

#### RTSP 소스 설정

```python
# UnifiedPipeline.create_pipeline()
rtspsrc.set_property("latency", streaming_config.get("latency_ms", 200))
rtspsrc.set_property("tcp-timeout", streaming_config.get("tcp_timeout", 10000) * 1000)
rtspsrc.set_property("timeout", streaming_config.get("connection_timeout", 10) * 1000000)
```

**IT_RNVR.json → GStreamer 속성:**
- `streaming.latency_ms` → `rtspsrc.latency`
- `streaming.tcp_timeout` → `rtspsrc.tcp-timeout`
- `streaming.connection_timeout` → `rtspsrc.timeout`

#### 디코더 선택

```python
# UnifiedPipeline._create_streaming_branch()
use_hw_accel = streaming_config.get("use_hardware_acceleration", True)
decoder_name = get_available_h264_decoder(prefer_hardware=use_hw_accel)
decoder = Gst.ElementFactory.make(decoder_name, "decoder")
```

**IT_RNVR.json → 디코더:**
- `streaming.use_hardware_acceleration: true` → v4l2h264dec / omxh264dec
- `streaming.use_hardware_acceleration: false` → avdec_h264

#### OSD 설정

```python
# UnifiedPipeline._create_streaming_branch()
show_timestamp = streaming_config.get("show_timestamp", True)
show_camera_name = streaming_config.get("show_camera_name", True)
osd_font_size = streaming_config.get("osd_font_size", 14)
osd_valignment = streaming_config.get("osd_valignment", "top")
osd_halignment = streaming_config.get("osd_halignment", "left")

self.text_overlay.set_property("font-desc", f"Sans Bold {osd_font_size}")
self.text_overlay.set_property("valignment", osd_valignment)
self.text_overlay.set_property("halignment", osd_halignment)
```

**IT_RNVR.json → OSD:**
- `streaming.show_timestamp` → textoverlay 활성화 여부
- `streaming.show_camera_name` → 카메라명 표시 여부
- `streaming.osd_font_size` → 폰트 크기
- `streaming.osd_valignment` → 수직 정렬 (top/bottom)
- `streaming.osd_halignment` → 수평 정렬 (left/right)

#### 녹화 설정

```python
# UnifiedPipeline._create_recording_branch()
fragment_duration = recording_config.get('fragment_duration_ms', 1000)
muxer.set_property("fragment-duration", fragment_duration)

# UnifiedPipeline.__init__()
self.file_duration = 600  # 10분 = recording.rotation_minutes * 60
```

**IT_RNVR.json → 녹화:**
- `recording.fragment_duration_ms` → `mp4mux.fragment-duration`
- `recording.rotation_minutes` → 파일 회전 간격
- `recording.base_path` → 녹화 파일 저장 경로
- `cameras[].recording_enabled` → 자동 녹화 시작 여부

---

## UI 연동 메커니즘

### 1. Window Handle 전달 흐름

```
1. GridViewWidget 생성
   ├─ 1~16개 VideoChannel 위젯 생성
   └─ 각 VideoChannel에 window_handle 할당

2. MainWindow._auto_assign_cameras()
   ├─ ConfigManager에서 카메라 목록 로드
   └─ 각 카메라를 GridViewWidget 채널에 할당

3. MainWindow._assign_window_handles_to_streams()
   ├─ GridViewWidget에서 window_handle 가져오기
   │   channel.get_window_handle() → int (PyQt5 winId)
   └─ CameraStream에 window_handle 할당
       stream.window_handle = handle

4. CameraListWidget._connect_camera()
   ├─ stream.connect(window_handle=handle, enable_recording=True)
   ├─ PipelineManager.create_unified_pipeline()
   └─ UnifiedPipeline 생성 시 window_handle 전달

5. UnifiedPipeline._on_sync_message()
   └─ GstVideo.VideoOverlay.set_window_handle(video_sink, window_handle)
       → 비디오가 PyQt5 위젯에 렌더링됨
```

**핵심 코드:**

```python
# ui/grid_view.py - VideoChannel
def get_window_handle(self):
    return int(self.winId())  # PyQt5 위젯 핸들

# streaming/unified_pipeline.py - UnifiedPipeline
def _on_sync_message(self, bus, message):
    if message.get_structure().get_name() == 'prepare-window-handle':
        GstVideo.VideoOverlay.set_window_handle(self.video_sink, self.window_handle)
```

### 2. 녹화 제어 흐름

#### 자동 녹화 시작

```
1. CameraListWidget._connect_camera()
   ├─ enable_recording = camera_config.recording_enabled  # IT_RNVR.json
   └─ stream.connect(enable_recording=enable_recording)

2. CameraStream.connect()
   ├─ mode = PipelineMode.BOTH if enable_recording else PipelineMode.STREAMING_ONLY
   └─ pipeline_manager.create_unified_pipeline(mode=mode)

3. UnifiedPipeline.create_pipeline()
   ├─ _create_streaming_branch()  # 항상 생성
   ├─ _create_recording_branch()  # BOTH 모드일 때만 생성
   └─ recording_valve.set_property("drop", True)  # 초기에는 OFF

4. MainWindow._on_camera_connected()
   ├─ if camera_config.recording_enabled:
   ├─   pipeline_manager.start_recording()
   │    └─ UnifiedPipeline.start_recording()
   │        ├─ 파일명 생성: recordings/{camera_id}/{date}/{timestamp}.mp4
   │        ├─ file_sink.set_property("location", filename)
   │        ├─ recording_valve.set_property("drop", False)  # Valve 열기
   │        └─ _schedule_file_rotation()  # 10분마다 파일 회전
   ├─ channel.set_recording(True)  # 채널 UI 업데이트
   └─ recording_control.camera_items[camera_id].set_recording(True)  # 위젯 UI 업데이트
```

#### 수동 녹화 제어

```
1. RecordingControlWidget - 사용자 Start 버튼 클릭
   └─ start_recording(camera_id)

2. RecordingControlWidget.start_recording()
   ├─ CameraListWidget.get_camera_stream(camera_id)
   ├─ camera_stream.pipeline_manager.start_recording()
   │   └─ UnifiedPipeline.start_recording()
   │       └─ recording_valve.set_property("drop", False)
   ├─ camera_items[camera_id].set_recording(True)  # UI 업데이트
   └─ recording_started.emit(camera_id)  # 시그널 발생

3. MainWindow._on_recording_started(camera_id)
   ├─ channel.set_recording(True)  # 채널 UI 동기화
   └─ recording_control.camera_items[camera_id].set_recording(True)  # 위젯 동기화
```

### 3. 시그널/슬롯 연결

```python
# MainWindow._setup_connections()

# Camera List 시그널
camera_list.camera_connected.connect(_on_camera_connected)
camera_list.camera_disconnected.connect(_on_camera_disconnected)

# Recording Control 시그널
recording_control.recording_started.connect(_on_recording_started)
recording_control.recording_stopped.connect(_on_recording_stopped)

# 흐름:
# User Action → Widget → Signal → MainWindow → 다른 Widget 동기화
```

---

## 데이터 흐름

### 1. 비디오 스트림 흐름

```
[RTSP 카메라]
    │ H.264 over RTP/TCP
    ▼
[rtspsrc] ─────────────────────┐
    │                          │
    │ RTP 패킷                 │ (동적 패드 연결)
    ▼                          │
[rtph264depay] ◄───────────────┘
    │
    │ H.264 NAL 유닛
    ▼
[h264parse]
    │
    │ 파싱된 H.264 프레임
    ▼
[tee] ─────────────────┬─────────────────┐
    │                  │                 │
    │ src_0 (복사)     │ src_1 (복사)    │
    ▼                  ▼                 │
[스트리밍 브랜치]    [녹화 브랜치]       │
    │                  │                 │
    │ H.264            │ H.264           │
    ▼                  ▼                 │
[stream_queue]     [record_queue]       │
    │                  │                 │
[streaming_valve]  [recording_valve]    │
    │                  │                 │
    │ (drop=False)     │ (drop=True/False)
    ▼                  ▼                 │
[decoder]          [record_parse]       │
    │                  │                 │
    │ Raw Video        │ H.264           │
    ▼                  ▼                 │
[videoconvert]     [mp4mux]             │
    │                  │                 │
[textoverlay]      [filesink]           │
    │                  │                 │
[videoscale]           ▼                │
    │              recordings/           │
[capsfilter]       cam_01/20251024/     │
    │              cam_01_153045.mp4    │
[final_queue]                           │
    │                                    │
[videosink]                             │
    │                                    │
    ▼                                    │
[PyQt5 Widget]                          │
(화면 표시)                              │
```

### 2. 제어 메시지 흐름

```
[GStreamer Bus Messages]
    │
    ├─ ERROR → UnifiedPipeline._on_bus_message()
    │          └─ pipeline.stop()
    │
    ├─ EOS → UnifiedPipeline._on_bus_message()
    │        └─ (녹화 파일 완료 시 발생)
    │
    └─ STATE_CHANGED → UnifiedPipeline._on_bus_message()
                      └─ logger.debug(state transition)

[Window Handle Messages]
    │
    └─ "prepare-window-handle" → UnifiedPipeline._on_sync_message()
                                 └─ VideoOverlay.set_window_handle()
```

---

## 제어 흐름

### 1. 파이프라인 생명주기

```
[생성 (Creation)]
    │
    ├─ CameraStream.connect()
    ├─ PipelineManager.create_unified_pipeline(mode)
    └─ UnifiedPipeline.create_pipeline()
        ├─ Gst.Pipeline.new()
        ├─ _create_streaming_branch()
        ├─ _create_recording_branch()
        └─ _apply_mode_settings()

[시작 (Start)]
    │
    ├─ PipelineManager.start()
    └─ UnifiedPipeline.start()
        ├─ pipeline.set_state(READY)
        ├─ pipeline.set_state(PAUSED)
        ├─ pipeline.set_state(PLAYING)
        ├─ GLib.MainLoop().run() (별도 스레드)
        └─ _start_timestamp_update() (OSD 업데이트)

[녹화 시작 (Start Recording)]
    │
    ├─ PipelineManager.start_recording()
    └─ UnifiedPipeline.start_recording()
        ├─ 파일명 생성 및 경로 설정
        ├─ file_sink.set_property("location", path)
        ├─ recording_valve.set_property("drop", False)
        ├─ _is_recording = True
        └─ _schedule_file_rotation()

[파일 회전 (File Rotation)]
    │
    ├─ Timer (10초마다 체크)
    └─ UnifiedPipeline._rotate_recording_file()
        ├─ 경과 시간 >= file_duration?
        ├─ 새 파일명 생성
        ├─ file_sink.set_property("location", new_path)
        └─ recording_start_time 업데이트

[녹화 정지 (Stop Recording)]
    │
    ├─ PipelineManager.stop_recording()
    └─ UnifiedPipeline.stop_recording()
        ├─ _is_recording = False
        ├─ _stop_rotation_timer()
        ├─ recording_valve.set_property("drop", True)
        └─ file_sink EOS 이벤트 전송

[정지 (Stop)]
    │
    ├─ PipelineManager.stop()
    └─ UnifiedPipeline.stop()
        ├─ _stop_timestamp_update()
        ├─ stop_recording() (녹화 중이면)
        ├─ pipeline.set_state(NULL)
        ├─ main_loop.quit()
        └─ thread.join()

[파괴 (Destruction)]
    │
    ├─ CameraStream.disconnect()
    └─ pipeline_manager = None
```

### 2. 에러 처리 및 재연결

```
[연결 실패 (Connection Failure)]
    │
    ├─ CameraStream.connect() 실패
    └─ _handle_connection_error()
        ├─ reconnect_count++
        ├─ reconnect_count < max_attempts?
        │   ├─ Yes → StreamStatus.RECONNECTING
        │   │        time.sleep(reconnect_delay)
        │   │        reconnect()
        │   └─ No  → StreamStatus.ERROR
        │            logger.error("Max attempts reached")
        └─ (재연결 중단)

[GStreamer 에러 (Pipeline Error)]
    │
    ├─ Gst.MessageType.ERROR
    └─ UnifiedPipeline._on_bus_message()
        ├─ videosink 에러? (윈도우 핸들 없음)
        │   └─ logger.warning("Ignoring video sink error")
        └─ 기타 에러
            └─ pipeline.stop()
```

---

## 성능 최적화 포인트

### 1. CPU 사용률 감소 (~50%)

**핵심 전략: 단일 디코더 사용**

```
기존:
├─ 스트리밍: RTSP → Decode (CPU 25%) → Display
└─ 녹화: RTSP → Decode (CPU 25%) → MP4
   총 디코딩 비용: 50%

개선:
RTSP → Decode (CPU 25%) → Tee ─┬─→ Display
                               └─→ MP4 (원본 H.264, 디코딩 불필요)
   총 디코딩 비용: 25%
```

### 2. 메모리 최적화

**큐 크기 조정:**

```python
# 스트리밍 큐: 낮은 지연시간 우선
stream_queue.set_property("max-size-buffers", 5)
stream_queue.set_property("leaky", 2)  # downstream leaky

# 녹화 큐: 안정성 우선
record_queue.set_property("max-size-time", 5 * Gst.SECOND)
record_queue.set_property("max-size-bytes", 50 * 1024 * 1024)
record_queue.set_property("leaky", 0)  # no leaky
```

### 3. 하드웨어 가속

**플랫폼별 최적화:**

```python
# RPi 4+: V4L2 하드웨어 디코더
v4l2h264dec

# RPi 3 이하: OpenMAX 하드웨어 디코더
omxh264dec

# 소프트웨어 폴백
avdec_h264
```

### 4. 지연시간 최소화

```python
# RTSP 지연시간 설정
rtspsrc.set_property("latency", 200)  # 200ms

# 비동기 렌더링
video_sink.set_property("sync", False)
video_sink.set_property("max-lateness", 20 * Gst.MSECOND)

# Leaky 큐 사용
stream_queue.set_property("leaky", 2)  # 오래된 프레임 버림
```

---

## 문제 해결 가이드

### 1. 스트리밍은 되지만 녹화 파일이 0MB

**원인:** 녹화 브랜치에 h264parse 누락

**해결:**
```python
# _create_recording_branch()에 추가
record_parse = Gst.ElementFactory.make("h264parse", "record_parse")
record_queue.link(recording_valve)
recording_valve.link(record_parse)  # ← 필수!
record_parse.link(muxer)
```

### 2. Recording Controls와 실제 녹화 상태 불일치

**원인:** UI 동기화 누락

**해결:**
```python
# main_window.py
def _on_camera_connected(self, camera_id):
    if camera_config.recording_enabled:
        pipeline_manager.start_recording()
        # UI 동기화 추가
        recording_control.camera_items[camera_id].set_recording(True)
        recording_control.recording_started.emit(camera_id)
```

### 3. 비디오 화면이 표시되지 않음

**원인:** Window handle 전달 실패

**해결:**
```python
# 1. GridView 채널에서 handle 가져오기
window_handle = channel.get_window_handle()

# 2. CameraStream에 할당
stream.window_handle = window_handle

# 3. connect 시 전달
stream.connect(window_handle=window_handle)

# 4. GStreamer 동기 메시지에서 설정
GstVideo.VideoOverlay.set_window_handle(video_sink, window_handle)
```

### 4. 자동 녹화가 시작되지 않음

**원인:** IT_RNVR.json 설정 확인

**해결:**
```json
{
  "cameras": [
    {
      "camera_id": "cam_01",
      "recording_enabled": true  // ← 이 설정 확인
    }
  ]
}
```

---

## 결론

IT_RNVR 시스템의 GStreamer 파이프라인은 다음과 같은 특징을 가집니다:

1. **Unified Pipeline Pattern**: Tee 기반 단일 디코더로 CPU 사용률 ~50% 감소
2. **Valve 기반 제어**: 런타임 중 스트리밍/녹화 동적 제어
3. **Singleton ConfigManager**: JSON 기반 중앙 집중식 설정 관리
4. **Signal/Slot UI 연동**: PyQt5 시그널로 UI와 파이프라인 동기화
5. **하드웨어 가속 지원**: 플랫폼별 최적 디코더 자동 선택
6. **자동 파일 회전**: 설정 가능한 시간 간격으로 녹화 파일 분할

이 구조를 이해하면 시스템 확장, 디버깅, 최적화가 훨씬 수월해집니다.
