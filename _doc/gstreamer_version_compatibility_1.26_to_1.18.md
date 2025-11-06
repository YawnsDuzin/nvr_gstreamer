# GStreamer 버전 호환성 가이드: 1.26.7 → 1.18.4

## 개요
현재 코드베이스는 GStreamer 1.26.7에서 개발되었으며, GStreamer 1.18.4 환경에서 실행 시 호환성 문제가 발생할 수 있습니다. 이 문서는 버전 다운그레이드 시 필요한 변경사항을 정리합니다.

## 버전 간 주요 차이점

### GStreamer 1.18.4 (2021년 3월 릴리스)
- Long Term Support (LTS) 버전
- 라즈베리파이 OS (Bullseye)의 기본 버전
- Ubuntu 20.04 LTS의 기본 버전

### GStreamer 1.26.7 (2024년 릴리스)
- 최신 안정 버전
- 새로운 엘리먼트와 개선된 API 포함
- 성능 개선 및 버그 수정

## 코드 수정이 필요한 부분

### 1. splitmuxsink 관련 변경사항

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 586-621
self.splitmuxsink = Gst.ElementFactory.make("splitmuxsink", "splitmuxsink")
self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
self.splitmuxsink.set_property("muxer-factory", muxer_factory)

# 1.26에서 추가된 속성들
self.splitmuxsink.set_property("muxer-properties", "fragment-duration=1000,streamable=true")
self.splitmuxsink.set_property("async-handling", True)
self.splitmuxsink.set_property("send-keyframe-requests", True)
```

#### 수정 필요 (1.18.4)
```python
self.splitmuxsink = Gst.ElementFactory.make("splitmuxsink", "splitmuxsink")
self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)

# muxer-factory 대신 muxer 속성 사용 (1.18.4)
if self.file_format == 'mp4':
    muxer = Gst.ElementFactory.make("mp4mux", None)
    if muxer:
        # 1.18에서는 fragment-duration을 직접 설정
        muxer.set_property("fragment-duration", 1000)
        try:
            muxer.set_property("streamable", True)
        except:
            pass  # streamable 속성이 없을 수 있음
        self.splitmuxsink.set_property("muxer", muxer)
elif self.file_format == 'mkv':
    muxer = Gst.ElementFactory.make("matroskamux", None)
    if muxer:
        self.splitmuxsink.set_property("muxer", muxer)

# 1.18.4에 없는 속성들 제거 또는 조건부 설정
try:
    self.splitmuxsink.set_property("async-handling", True)
except:
    pass  # 1.18.4에서는 이 속성이 없음

# send-keyframe-requests는 1.18.4에도 존재
self.splitmuxsink.set_property("send-keyframe-requests", True)
```

### 2. Valve 엘리먼트 초기화

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 289-293
self.streaming_valve = Gst.ElementFactory.make("valve", "streaming_valve")
self.streaming_valve.set_property("drop", False)  # 즉시 설정
```

#### 수정 필요 (1.18.4)
```python
self.streaming_valve = Gst.ElementFactory.make("valve", "streaming_valve")
# 1.18.4에서는 파이프라인이 READY 상태가 된 후 설정하는 것이 안전
# 초기값은 생성자에서 설정하지 않고 start() 메서드에서 설정
```

### 3. Tee 엘리먼트 패드 요청

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 528, 645
tee_pad = self.tee.request_pad_simple("src_%u")
```

#### 수정 필요 (1.18.4)
```python
# request_pad_simple은 1.20에서 추가됨
# 1.18.4에서는 get_request_pad 사용
tee_pad_template = self.tee.get_pad_template("src_%u")
tee_pad = self.tee.request_pad(tee_pad_template, None, None)
```

### 4. 파이프라인 상태 변경 처리

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 1044-1073
elif ret == Gst.StateChangeReturn.NO_PREROLL:
    logger.debug("Live source confirmed (NO_PREROLL)")
```

#### 수정 필요 (1.18.4)
```python
# 1.18.4에서는 NO_PREROLL 처리가 다를 수 있음
elif ret == Gst.StateChangeReturn.NO_PREROLL:
    # 1.18.4에서는 라이브 소스 처리가 덜 최적화되어 있음
    logger.debug("Live source detected (NO_PREROLL)")
    # 추가 대기 시간이 필요할 수 있음
    time.sleep(0.5)
```

### 5. Video Transform 엘리먼트 (videoflip)

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 339-358
videoflip = Gst.ElementFactory.make("videoflip", "videoflip")
videoflip.set_property("method", method)
```

#### 수정 필요 (1.18.4)
```python
# videoflip method 열거형 값이 다를 수 있음
# 1.18.4에서는 숫자 대신 문자열 사용을 권장
videoflip = Gst.ElementFactory.make("videoflip", "videoflip")

# method 값 매핑 (1.18.4 호환)
method_map = {
    0: "none",
    1: "clockwise",
    2: "rotate-180",
    3: "counterclockwise",
    4: "horizontal-flip",
    5: "vertical-flip",
    6: "upper-left-diagonal",
    7: "upper-right-diagonal"
}

# 숫자를 문자열로 변환 (1.18.4 호환성)
if isinstance(method, int) and method in method_map:
    try:
        videoflip.set_property("method", method_map[method])
    except:
        # 문자열이 안 되면 숫자로 시도
        videoflip.set_property("method", method)
```

### 6. GStreamer 초기화 및 버전 체크

#### 추가 권장 코드
```python
# main.py 또는 gst_utils.py에 추가
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

def check_gstreamer_version():
    """GStreamer 버전 확인 및 호환성 경고"""
    Gst.init(None)
    version = Gst.version()
    major, minor, micro, nano = version

    version_str = f"{major}.{minor}.{micro}"
    logger.info(f"GStreamer version: {version_str}")

    # 1.18.x 버전 체크
    if major == 1 and minor < 20:
        logger.warning(f"GStreamer {version_str} detected. Some features may be limited.")
        logger.warning("Recommended version: 1.20 or higher")

        # 전역 플래그 설정
        global GST_VERSION_LEGACY
        GST_VERSION_LEGACY = True
    else:
        GST_VERSION_LEGACY = False

    return version_str, GST_VERSION_LEGACY
```

### 7. 텍스트 오버레이 색상 설정

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 374-376
r, g, b = osd_font_color[0], osd_font_color[1], osd_font_color[2]
color_argb = 0xFF000000 | (r << 16) | (g << 8) | b
self.text_overlay.set_property("color", color_argb)
```

#### 수정 필요 (1.18.4)
```python
# 1.18.4에서는 color 속성 형식이 다를 수 있음
r, g, b = osd_font_color[0], osd_font_color[1], osd_font_color[2]
color_argb = 0xFF000000 | (r << 16) | (g << 8) | b

try:
    # 1.20+ 방식
    self.text_overlay.set_property("color", color_argb)
except:
    try:
        # 1.18.4 방식 - RGBA 문자열
        color_str = f"0x{color_argb:08X}"
        self.text_overlay.set_property("color", color_str)
    except:
        # 더 오래된 방식
        pass
```

### 8. 하드웨어 디코더 호환성

#### 현재 코드 (1.26.7)
```python
# camera/gst_utils.py - Line 104-115
decoders = [
    "v4l2h264dec",     # V4L2 hardware decoder (newer Raspberry Pi)
    "omxh264dec",      # OpenMAX hardware decoder (older Raspberry Pi)
    "avdec_h264",      # Software decoder (libav)
]
```

#### 수정 필요 (1.18.4)
```python
# 1.18.4에서는 v4l2h264dec가 덜 안정적일 수 있음
decoders = [
    "omxh264dec",      # 1.18.4에서 더 안정적 (라즈베리파이)
    "v4l2h264dec",     # 두 번째 옵션으로
    "avdec_h264",      # Software decoder fallback
]

# 라즈베리파이 모델별 분기
if is_raspberry_pi_3_or_older():  # 별도 검출 함수 필요
    decoders = ["omxh264dec", "avdec_h264"]
elif is_raspberry_pi_4():
    decoders = ["v4l2h264dec", "omxh264dec", "avdec_h264"]
```

### 9. format-location 시그널 핸들러

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 617-618
self.splitmuxsink.connect("format-location", self._on_format_location)
```

#### 수정 필요 (1.18.4)
```python
# 1.18.4에서는 format-location 시그널 시그니처가 다를 수 있음
def _on_format_location_legacy(self, splitmux, fragment_id, first_sample):
    """1.18.4 호환 format-location 핸들러"""
    # 1.18.4에서는 추가 파라미터가 있을 수 있음
    return self._generate_recording_filename(fragment_id)

# 버전에 따라 다른 핸들러 연결
if GST_VERSION_LEGACY:
    self.splitmuxsink.connect("format-location", self._on_format_location_legacy)
else:
    self.splitmuxsink.connect("format-location", self._on_format_location)
```

### 10. 버스 메시지 처리

#### 현재 코드 (1.26.7)
```python
# camera/gst_pipeline.py - Line 689-741
def _on_bus_message(self, bus, message):
    t = message.type
    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
```

#### 수정 필요 (1.18.4)
```python
def _on_bus_message(self, bus, message):
    t = message.type

    # 1.18.4에서는 일부 메시지 타입이 다르게 처리될 수 있음
    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()

        # 1.18.4에서는 에러 코드가 다를 수 있음
        if hasattr(err, 'code'):
            error_code = err.code
        else:
            # 1.18.4 호환성
            error_code = None
```

## 테스트 권장사항

### 1. 기본 기능 테스트
```bash
# GStreamer 버전 확인
gst-inspect-1.0 --version

# 필수 엘리먼트 확인
gst-inspect-1.0 splitmuxsink
gst-inspect-1.0 valve
gst-inspect-1.0 tee
gst-inspect-1.0 videoflip

# 디코더 확인 (라즈베리파이)
gst-inspect-1.0 omxh264dec
gst-inspect-1.0 v4l2h264dec
```

### 2. 파이프라인 테스트
```bash
# 간단한 RTSP 스트리밍 테스트
gst-launch-1.0 rtspsrc location=rtsp://camera_ip ! \
    rtph264depay ! h264parse ! avdec_h264 ! \
    videoconvert ! autovideosink

# splitmuxsink 테스트
gst-launch-1.0 videotestsrc ! x264enc ! h264parse ! \
    splitmuxsink location=test_%05d.mp4 max-size-time=10000000000
```

### 3. 단위 테스트 실행
```bash
# 개별 컴포넌트 테스트
python _tests/test_valve_mode_switch.py
python _tests/run_single_camera.py --debug
```

## 환경별 설정 권장사항

### 라즈베리파이 3 (GStreamer 1.18.4)
```json
{
  "streaming": {
    "use_hardware_acceleration": true,
    "decoder_preference": ["omxh264dec", "avdec_h264"]
  }
}
```

### 라즈베리파이 4 (GStreamer 1.18.4)
```json
{
  "streaming": {
    "use_hardware_acceleration": true,
    "decoder_preference": ["v4l2h264dec", "avdec_h264"]
  }
}
```

### Ubuntu 20.04 (GStreamer 1.18.4)
```json
{
  "streaming": {
    "use_hardware_acceleration": false,
    "decoder_preference": ["avdec_h264"]
  }
}
```

## 알려진 이슈 및 해결방법

### 1. splitmuxsink 파일 분할 실패
- **증상**: 파일이 지정된 시간에 분할되지 않음
- **원인**: 1.18.4의 splitmuxsink 버그
- **해결**: max-size-bytes도 함께 설정
```python
self.splitmuxsink.set_property("max-size-time", self.file_duration_ns)
self.splitmuxsink.set_property("max-size-bytes", 500 * 1024 * 1024)  # 500MB
```

### 2. Valve 상태 변경 무시
- **증상**: valve drop 속성 변경이 적용되지 않음
- **원인**: 1.18.4에서 파이프라인 상태에 따른 제약
- **해결**: PLAYING 상태에서만 변경
```python
if self.pipeline.get_state(0)[1] == Gst.State.PLAYING:
    self.recording_valve.set_property("drop", False)
```

### 3. 라이브 소스 연결 지연
- **증상**: RTSP 연결이 느림
- **원인**: 1.18.4의 라이브 소스 처리 방식
- **해결**: 타임아웃 증가
```python
rtspsrc.set_property("timeout", 20 * 1000000)  # 20초로 증가
```

## 마이그레이션 체크리스트

- [ ] GStreamer 버전 감지 코드 추가
- [ ] splitmuxsink 속성 설정 수정
- [ ] Tee 패드 요청 방식 변경
- [ ] Valve 초기화 타이밍 조정
- [ ] videoflip method 설정 호환성 처리
- [ ] 하드웨어 디코더 우선순위 조정
- [ ] format-location 핸들러 호환성 처리
- [ ] 텍스트 오버레이 색상 설정 호환성
- [ ] 에러 메시지 처리 호환성
- [ ] 설정 파일에 decoder_preference 추가

## 참고 문서
- [GStreamer 1.18 Release Notes](https://gstreamer.freedesktop.org/releases/1.18/)
- [GStreamer 1.20 Release Notes](https://gstreamer.freedesktop.org/releases/1.20/)
- [GStreamer API Migration Guide](https://gstreamer.freedesktop.org/documentation/application-development/appendix/migration.html)
- [Raspberry Pi GStreamer Hardware Acceleration](https://www.raspberrypi.org/documentation/usage/camera/raspicam/gstreamer.md)