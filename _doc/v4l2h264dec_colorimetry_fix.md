# v4l2h264dec colorimetry 협상 문제 해결

## 문제 개요

GStreamer 1.18.4 환경(라즈베리파이 4)에서 `v4l2h264dec`를 사용하여 RTSP 스트림을 디코딩할 때 "not-negotiated" 오류가 발생하는 문제

### 오류 메시지
```
ERROR: from element source: gst-stream-error-quark: Internal data stream error. (1)
streaming stopped, reason not-negotiated (-4)
```

### 오류 로그 상세
```
WARN GST_CAPS gstpad.c:5701:pre_eventfunc_check:<v4l2h264dec0:sink>
caps video/x-h264, stream-format=(string)byte-stream, alignment=(string)au,
width=(int)640, height=(int)480, framerate=(fraction)10/1,
chroma-format=(string)4:2:0, bit-depth-luma=(uint)8, bit-depth-chroma=(uint)8,
colorimetry=(string)1:3:5:1, parsed=(boolean)true,
profile=(string)baseline, level=(string)3 not accepted
```

## 원인 분석

### 1. Caps 협상 실패

`h264parse`가 생성하는 caps에 포함된 `colorimetry=(string)1:3:5:1` 값을 `v4l2h264dec`가 거부함

### 2. v4l2h264dec가 지원하는 colorimetry

```bash
$ gst-inspect-1.0 v4l2h264dec | grep -A 15 'SINK template'
SINK template: 'sink'
  Availability: Always
  Capabilities:
    video/x-h264
        stream-format: byte-stream
            alignment: au
                level: { (string)1, (string)1b, (string)1.1, (string)1.2,
                         (string)1.3, (string)2, (string)2.1, (string)2.2,
                         (string)3, (string)3.1, (string)3.2, (string)4,
                         (string)4.1, (string)4.2 }
              profile: { (string)baseline, (string)constrained-baseline,
                         (string)main, (string)high }
```

```bash
probed caps: video/x-h264, stream-format=(string)byte-stream, alignment=(string)au,
level=(string){ 1, 1b, 1.1, 1.2, 1.3, 2, 2.1, 2.2, 3, 3.1, 3.2, 4, 4.1, 4.2 },
profile=(string){ baseline, constrained-baseline, main, high },
width=(int)[ 32, 1920, 2 ], height=(int)[ 32, 1920, 2 ],
colorimetry=(string){ bt709, bt601, smpte240m, 2:4:5:2, 2:4:5:3, 1:4:7:1,
                       2:4:7:1, 2:4:12:8, bt2020, 2:0:0:0 },
parsed=(boolean)true
```

**문제**: `h264parse`가 제공하는 `1:3:5:1` colorimetry는 v4l2h264dec가 지원하는 목록에 없음

### 3. 관련 이슈

- GStreamer 1.18~1.20에서 v4l2 하드웨어 가속 사용 시 알려진 문제
- Raspberry Pi Forums: https://forums.raspberrypi.com/viewtopic.php?t=305405
- GStreamer GitLab Issue: https://gitlab.freedesktop.org/gstreamer/gst-plugins-good/-/issues/958

## 해결 방법

### capssetter를 사용한 colorimetry 강제 설정

`h264parse`와 `v4l2h264dec` 사이에 `capssetter` 요소를 추가하여 v4l2h264dec가 지원하는 colorimetry(bt709)로 강제 설정

#### 테스트 파이프라인 (성공)

```bash
gst-launch-1.0 rtspsrc location='rtsp://...' latency=100 \
  ! rtpjitterbuffer \
  ! rtph264depay \
  ! h264parse \
  ! capssetter caps='video/x-h264,stream-format=byte-stream,alignment=au,colorimetry=bt709' \
  ! v4l2h264dec \
  ! videoconvert \
  ! autovideosink
```

### 코드 구현

#### gst_pipeline.py 수정

`_create_streaming_branch()` 메서드에서 `streaming_valve`와 `decoder` 사이에 capssetter 추가:

```python
# v4l2 디코더의 경우 colorimetry 협상 문제 해결을 위한 capssetter 추가
# GStreamer 1.18에서 v4l2h264dec는 h264parse가 제공하는 colorimetry 값을 거부할 수 있음
# 해결: capssetter로 v4l2h264dec가 지원하는 colorimetry(bt709)로 강제 설정
if decoder_name.startswith('v4l2') and not is_gstreamer_1_20_or_later():
    capssetter = Gst.ElementFactory.make("capssetter", "capssetter")
    if capssetter:
        # v4l2h264dec가 지원하는 colorimetry로 강제 설정
        # bt709는 v4l2h264dec가 지원하는 colorimetry 중 하나
        capssetter_caps = Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au,colorimetry=bt709")
        capssetter.set_property("caps", capssetter_caps)
        self.pipeline.add(capssetter)

        if not self.streaming_valve.link(capssetter):
            raise Exception("Failed to link streaming_valve → capssetter")
        logger.debug("[V4L2] Linked: streaming_valve → capssetter")

        if not capssetter.link(decoder):
            raise Exception("Failed to link capssetter → decoder")
        logger.debug(f"[V4L2] Linked: capssetter → decoder (forced colorimetry=bt709 for v4l2)")
    else:
        logger.warning("Failed to create capssetter, linking directly")
        if not self.streaming_valve.link(decoder):
            raise Exception("Failed to link streaming_valve → decoder")
        logger.debug("[STREAMING DEBUG] Linked: streaming_valve → decoder")
else:
    # 일반 디코더는 직접 연결
    if not self.streaming_valve.link(decoder):
        raise Exception("Failed to link streaming_valve → decoder")
    logger.debug("[STREAMING DEBUG] Linked: streaming_valve → decoder")
```

### 파이프라인 구조 변경

#### 이전 (오류 발생)
```
tee → stream_queue → streaming_valve → v4l2h264dec → videoconvert → ...
                                       ↑
                                  협상 실패
```

#### 이후 (정상 동작)
```
tee → stream_queue → streaming_valve → capssetter → v4l2h264dec → videoconvert → ...
                                          ↓
                                   colorimetry=bt709 강제
```

## 적용 조건

- **GStreamer 버전**: 1.18.x (1.20 이상에서는 문제 없음)
- **디코더**: `v4l2h264dec`, `v4l2h265dec` 등 v4l2 계열
- **플랫폼**: Raspberry Pi 4, 라즈베리파이 OS

## 설정 방법

### IT_RNVR.json 설정

```json
{
  "streaming": {
    "use_hardware_acceleration": true,
    "decoder_preference": [
      "v4l2h264dec",
      "avdec_h264",
      "omxh264dec"
    ]
  }
}
```

이제 `v4l2h264dec`를 우선순위 1위로 설정해도 정상 작동합니다.

## 테스트 결과

### 라즈베리파이 4 (GStreamer 1.18.4)

- **디코더**: bcm2835-codec-decode (/dev/video10)
- **RTSP URL**: rtsp://admin:***@192.168.0.131:554/Streaming/Channels/102
- **결과**: ✅ 정상 스트리밍

### 예상 로그

```
DEBUG | [V4L2] Linked: streaming_valve → capssetter
DEBUG | [V4L2] Linked: capssetter → decoder (forced colorimetry=bt709 for v4l2)
INFO  | Using H264 decoder: v4l2h264dec
INFO  | Hardware acceleration enabled - selected H264 decoder: v4l2h264dec
```

## 참고 사항

### colorimetry 옵션

v4l2h264dec가 지원하는 colorimetry 값:
- `bt709` (추천, HD 영상 표준)
- `bt601` (SD 영상 표준)
- `smpte240m`
- `bt2020` (4K/8K 영상 표준)
- 기타 수치 표현: `2:4:5:2`, `2:4:5:3`, `1:4:7:1`, `2:4:7:1`, `2:4:12:8`, `2:0:0:0`

대부분의 경우 `bt709` 사용 권장

### avdec_h264와의 비교

- **avdec_h264**: colorimetry 협상 문제 없음, CPU 부하 높음
- **v4l2h264dec** (수정 전): caps 협상 실패
- **v4l2h264dec + capssetter** (수정 후): 정상 작동, CPU 부하 낮음

## 결론

GStreamer 1.18에서 v4l2h264dec를 사용하려면 capssetter를 통한 colorimetry 강제 설정이 필수입니다. 이를 통해 하드웨어 가속을 활용하여 CPU 부하를 크게 줄일 수 있습니다.

---

**작성일**: 2025-11-05
**GStreamer 버전**: 1.18.4
**플랫폼**: Raspberry Pi 4 (bcm2835-codec)