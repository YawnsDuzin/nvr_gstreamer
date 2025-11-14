# GStreamer Python Bus Message 처리 패턴 분석

## 목차
1. [오픈소스 프로젝트 조사](#1-오픈소스-프로젝트-조사)
2. [Bus Message 처리 방법 3가지](#2-bus-message-처리-방법-3가지)
3. [실제 프로젝트 코드 분석](#3-실제-프로젝트-코드-분석)
4. [패턴별 장단점 비교](#4-패턴별-장단점-비교)
5. [현재 프로젝트와 비교](#5-현재-프로젝트와-비교)
6. [모범 사례 및 권장사항](#6-모범-사례-및-권장사항)

---

## 1. 오픈소스 프로젝트 조사

### 1.1 조사 대상 프로젝트

| 프로젝트 | 설명 | 언어 | Bus 처리 방식 |
|---------|------|------|--------------|
| **GStreamer/gst-python** | GStreamer 공식 Python 바인딩 예제 | Python | 비동기 (MainLoop) |
| **Pitivi** | GNOME 비디오 편집기 | Python | 비동기 + 커스텀 핸들러 |
| **Transmageddon** | 비디오 트랜스코더 | Python | 비동기 (MainLoop) |
| **tamaggo/gstreamer-examples** | RTSP 녹화 예제 | Python | 폴링 (poll) |
| **jackersson/gstreamer-python** | GStreamer Python 튜토리얼 | Python | 비동기 (MainLoop) |
| **gkralik/python-gst-tutorial** | 기본 튜토리얼 모음 | Python | 메시지별 핸들러 분리 |

### 1.2 주요 참고 자료

**공식 문서:**
- [GStreamer Bus 문서](https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html)
- [GStreamer Application Development Manual - Bus](https://gstreamer.freedesktop.org/documentation/application-development/basics/bus.html)
- [Python GStreamer Tutorial](https://brettviren.github.io/pygst-tutorial-org/pygst-tutorial.html)

**GitHub 저장소:**
- [GStreamer/gst-python](https://github.com/GStreamer/gst-python)
- [tamaggo/gstreamer-examples](https://github.com/tamaggo/gstreamer-examples)
- [jackersson/gstreamer-python](https://github.com/jackersson/gstreamer-python)
- [gkralik/python-gst-tutorial](https://github.com/gkralik/python-gst-tutorial)

---

## 2. Bus Message 처리 방법 3가지

GStreamer에서 Bus Message를 처리하는 방법은 크게 3가지입니다:

### 2.1 방법 1: 비동기 처리 (GLib MainLoop) ✅ 가장 일반적

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def on_bus_message(bus, message, loop):
    """비동기 메시지 핸들러"""
    t = message.type

    if t == Gst.MessageType.EOS:
        print("End-of-stream")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}, {debug}")
        loop.quit()

    return True  # 계속 메시지 수신

# 설정
pipeline = Gst.Pipeline()
bus = pipeline.get_bus()
bus.add_signal_watch()  # 비동기 시그널 활성화
bus.connect("message", on_bus_message, loop)

# 메인 루프 실행
loop = GLib.MainLoop()
pipeline.set_state(Gst.State.PLAYING)
loop.run()
```

**특징:**
- GLib MainLoop가 별도 스레드에서 메시지 처리
- 메시지가 도착하면 콜백 자동 호출
- 가장 일반적이고 권장되는 방법
- GUI 애플리케이션에 적합

### 2.2 방법 2: 폴링 (Polling) 🔄

```python
def poll_messages(pipeline):
    """폴링 방식 메시지 처리"""
    bus = pipeline.get_bus()

    while True:
        # 1초 타임아웃으로 메시지 대기
        msg = bus.poll(Gst.MessageType.ANY, 1 * Gst.SECOND)

        if msg is None:
            # 타임아웃 - 메시지 없음
            continue

        if msg.type == Gst.MessageType.EOS:
            print("End-of-stream")
            break
        elif msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            print(f"Error: {err}, {debug}")
            break
        elif msg.type == Gst.MessageType.WARNING:
            warn, debug = msg.parse_warning()
            print(f"Warning: {warn}, {debug}")

    pipeline.set_state(Gst.State.NULL)
```

**특징:**
- 블로킹 방식 (메시지가 올 때까지 대기)
- MainLoop 불필요
- 간단한 스크립트나 CLI 애플리케이션에 적합
- 타임아웃 설정 가능

### 2.3 방법 3: 동기 핸들러 (Sync Handler) ⚡ 고급

```python
def sync_handler(bus, message, user_data):
    """동기 메시지 핸들러 (메시지 발생 스레드에서 즉시 처리)"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Sync Error: {err}")
        # 즉시 처리 (스레드 마샬링 없음)

    # Gst.BusSyncReply.PASS: 다른 핸들러로 전달
    # Gst.BusSyncReply.DROP: 메시지 버림
    # Gst.BusSyncReply.ASYNC: 비동기 큐에 추가
    return Gst.BusSyncReply.PASS

# 설정
bus = pipeline.get_bus()
bus.set_sync_handler(sync_handler, None)
```

**특징:**
- 메시지 발생 스레드에서 즉시 처리 (스레드 마샬링 없음)
- 가장 빠른 응답 속도
- 복잡하고 위험 (데드락 가능)
- 특수한 경우에만 사용 (비디오 오버레이 등)

---

## 3. 실제 프로젝트 코드 분석

### 3.1 GStreamer 공식 예제 (helloworld.py)

**출처:** [GStreamer/gst-python/examples/helloworld.py](https://github.com/GStreamer/gst-python/blob/master/examples/helloworld.py)

```python
#!/usr/bin/env python3
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def bus_call(bus, message, loop):
    """Bus 메시지 핸들러"""
    t = message.type

    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        loop.quit()

    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()

    return True

def main(args):
    # GStreamer 초기화
    Gst.init(None)

    # 파이프라인 생성
    pipeline = Gst.parse_launch(
        "filesrc location=sintel_trailer-480p.webm ! "
        "decodebin ! autovideosink"
    )

    # Bus 설정
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # 재생 시작
    pipeline.set_state(Gst.State.PLAYING)

    # 메인 루프 실행
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    # 정리
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
```

**분석:**

| 항목 | 내용 |
|------|------|
| **처리 방식** | 비동기 (GLib MainLoop) |
| **메시지 타입** | EOS, ERROR만 처리 |
| **에러 처리** | `parse_error()` 사용, 에러 발생 시 루프 종료 |
| **종료 처리** | EOS/ERROR 시 `loop.quit()` |
| **장점** | 매우 간단하고 명확, 기본 패턴 |
| **단점** | WARNING, STATE_CHANGED 등 미처리 |

### 3.2 RTSP 녹화 예제 (tamaggo/gstreamer-examples)

**출처:** [tamaggo/gstreamer-examples/test_gst_rtsp_subtitles_client.py](https://github.com/tamaggo/gstreamer-examples/blob/master/test_gst_rtsp_subtitles_client.py)

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import time

def main():
    Gst.init(None)

    # RTSP 녹화 파이프라인 생성
    pipeline_str = (
        "rtspsrc location=rtsp://example.com/stream ! "
        "rtph264depay ! h264parse ! mp4mux ! "
        "filesink location=output.mp4"
    )
    pipeline = Gst.parse_launch(pipeline_str)

    # Bus 획득
    bus = pipeline.get_bus()

    # 파이프라인 시작
    pipeline.set_state(Gst.State.PLAYING)

    start_time = time.time()
    max_duration = 10  # 10초간 녹화

    # 폴링 루프
    while True:
        # 1초 타임아웃으로 메시지 폴링
        msg = bus.poll(Gst.MessageType.ANY, int(1e6))  # 1초 = 1,000,000 나노초

        if msg is None:
            # 타임아웃 - 메시지 없음
            elapsed = time.time() - start_time
            if elapsed > max_duration:
                print(f"Recording completed: {elapsed:.1f}s")
                # EOS 전송하여 파일 정상 종료
                pipeline.send_event(Gst.Event.new_eos())

                # EOS 메시지 대기
                eos_msg = bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
                break
            continue

        # 메시지 타입 확인
        if msg.type == Gst.MessageType.EOS:
            print("End-of-stream received")
            break

        elif msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            print(f"Error: {err}")
            print(f"Debug: {debug}")
            break

        elif msg.type == Gst.MessageType.WARNING:
            warn, debug = msg.parse_warning()
            print(f"Warning: {warn}")
            print(f"Debug: {debug}")

        elif msg.type == Gst.MessageType.STATE_CHANGED:
            # 상태 변경 메시지 (로깅만)
            if msg.src == pipeline:
                old, new, pending = msg.parse_state_changed()
                print(f"State: {old.value_nick} -> {new.value_nick}")

        elif msg.type == Gst.MessageType.STREAM_STATUS:
            # 스트림 상태 메시지 (무시)
            pass

    # 정리
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    main()
```

**분석:**

| 항목 | 내용 |
|------|------|
| **처리 방식** | 폴링 (Polling) |
| **메시지 타입** | EOS, ERROR, WARNING, STATE_CHANGED, STREAM_STATUS |
| **타임아웃** | 1초 (1,000,000 나노초) |
| **녹화 종료** | 시간 기반 + EOS 전송 |
| **장점** | MainLoop 불필요, 타임아웃 제어 가능 |
| **단점** | 블로킹 방식, GUI와 통합 어려움 |

### 3.3 고급 예제 (basic-tutorial-5.py)

**출처:** [gkralik/python-gst-tutorial/basic-tutorial-5.py](https://github.com/gkralik/python-gst-tutorial/blob/master/basic-tutorial-5.py)

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, GLib, Gtk

class GTK_Main:
    def __init__(self):
        # 파이프라인 생성
        self.playbin = Gst.ElementFactory.make("playbin", "playbin")

        # Bus 설정 - 메시지 타입별 핸들러 분리
        bus = self.playbin.get_bus()
        bus.add_signal_watch()

        # 각 메시지 타입별로 별도 핸들러 연결
        bus.connect("message::error", self.on_error)
        bus.connect("message::eos", self.on_eos)
        bus.connect("message::state-changed", self.on_state_changed)
        bus.connect("message::application", self.on_application_message)

        # 동기 핸들러도 함께 사용 (비디오 오버레이용)
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self.on_sync_message)

        self.state = Gst.State.NULL

    def on_error(self, bus, msg):
        """에러 메시지 핸들러"""
        err, dbg = msg.parse_error()
        print("ERROR:", msg.src.get_name(), ":", err.message)
        if dbg:
            print("Debug info:", dbg)

        # UI 업데이트
        self.playbin.set_state(Gst.State.READY)

    def on_eos(self, bus, msg):
        """EOS 메시지 핸들러"""
        print("End-Of-Stream reached")
        self.playbin.set_state(Gst.State.READY)

    def on_state_changed(self, bus, msg):
        """상태 변경 메시지 핸들러"""
        old, new, pending = msg.parse_state_changed()

        # 파이프라인 레벨의 상태 변경만 처리
        if not msg.src == self.playbin:
            return

        self.state = new
        print("State changed from {0} to {1}".format(
            Gst.Element.state_get_name(old),
            Gst.Element.state_get_name(new)))

        # PAUSED 상태에 도달하면 UI 업데이트
        if old == Gst.State.READY and new == Gst.State.PAUSED:
            self.refresh_ui()

    def on_application_message(self, bus, msg):
        """애플리케이션 메시지 핸들러"""
        if msg.get_structure().get_name() == "tags-changed":
            # 태그 변경 시 스트림 재분석
            self.analyze_streams()

    def on_sync_message(self, bus, msg):
        """동기 메시지 핸들러 (비디오 오버레이용)"""
        if msg.get_structure() is None:
            return

        message_name = msg.get_structure().get_name()
        if message_name == "prepare-window-handle":
            # 비디오 윈도우 핸들 설정
            imagesink = msg.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_window_handle(self.movie_window.get_property('window').get_xid())

    def refresh_ui(self):
        """UI 업데이트"""
        # 스트림 정보 가져오기
        n_video = self.playbin.get_property("n-video")
        n_audio = self.playbin.get_property("n-audio")
        n_text = self.playbin.get_property("n-text")

        print(f"Streams: video={n_video}, audio={n_audio}, text={n_text}")

def main():
    Gst.init(None)
    GTK_Main()
    Gtk.main()

if __name__ == '__main__':
    main()
```

**분석:**

| 항목 | 내용 |
|------|------|
| **처리 방식** | 비동기 (GLib MainLoop) + 메시지별 핸들러 분리 |
| **메시지 타입** | ERROR, EOS, STATE_CHANGED, APPLICATION, SYNC 메시지 |
| **특징** | 각 메시지 타입별로 별도 핸들러 함수 |
| **UI 통합** | GTK+ 3.0과 통합, 비디오 오버레이 지원 |
| **장점** | 코드 구조 명확, 각 메시지 독립 처리 |
| **단점** | 핸들러 함수 많아짐 |

### 3.4 jackersson/gstreamer-python 예제

**출처:** [jackersson/gstreamer-python](https://github.com/jackersson/gstreamer-python)

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

def on_message(bus: Gst.Bus, message: Gst.Message, loop: GObject.MainLoop):
    """
    Bus 메시지 핸들러

    GStreamer Message Types:
    https://lazka.github.io/pgi-docs/Gst-1.0/flags.html#Gst.MessageType
    """
    mtype = message.type

    if mtype == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()

    elif mtype == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}")
        print(f"Debug: {debug}")
        loop.quit()

    elif mtype == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        print(f"Warning: {err}")
        print(f"Debug: {debug}")

    elif mtype == Gst.MessageType.STATE_CHANGED:
        # 상태 변경 로깅
        old_state, new_state, pending_state = message.parse_state_changed()
        print(f"State changed: {old_state.value_nick} -> {new_state.value_nick}")

    return True

class GstPipeline:
    """GStreamer 파이프라인 래퍼"""

    def __init__(self, pipeline_str: str):
        self.pipeline = Gst.parse_launch(pipeline_str)

        # Bus 설정
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", on_message, self.loop)

        self.loop = GObject.MainLoop()

    def run(self):
        """파이프라인 실행"""
        self.pipeline.set_state(Gst.State.PLAYING)

        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("Interrupted")

        # 정리
        self.pipeline.set_state(Gst.State.NULL)

def main():
    Gst.init(None)

    pipeline_str = (
        "videotestsrc num-buffers=100 ! "
        "video/x-raw,format=RGB,width=640,height=480 ! "
        "videoconvert ! autovideosink"
    )

    pipeline = GstPipeline(pipeline_str)
    pipeline.run()

if __name__ == '__main__':
    main()
```

**분석:**

| 항목 | 내용 |
|------|------|
| **처리 방식** | 비동기 (GObject MainLoop) |
| **메시지 타입** | EOS, ERROR, WARNING, STATE_CHANGED |
| **구조** | 클래스 기반 파이프라인 래퍼 |
| **문서화** | 메시지 타입 문서 링크 제공 |
| **장점** | 재사용 가능한 클래스 구조 |
| **단점** | 기본적인 에러 처리만 제공 |

---

## 4. 패턴별 장단점 비교

### 4.1 비동기 처리 (GLib/GObject MainLoop)

```python
# 패턴
bus.add_signal_watch()
bus.connect("message", on_message, loop)
loop = GLib.MainLoop()
loop.run()
```

**장점:**
- ✅ **비블로킹**: 메인 스레드가 블록되지 않음
- ✅ **이벤트 기반**: 메시지 도착 시 자동 처리
- ✅ **GUI 통합**: GTK+, Qt와 자연스럽게 통합
- ✅ **멀티 파이프라인**: 여러 파이프라인 동시 처리 가능
- ✅ **타이머/이벤트**: GLib의 다른 기능 활용 가능

**단점:**
- ❌ **복잡도**: MainLoop 관리 필요
- ❌ **스레드 안전성**: 콜백 내 스레드 안전성 고려 필요
- ❌ **디버깅**: 비동기 처리로 디버깅 어려움

**적합한 경우:**
- GUI 애플리케이션 (PyQt, GTK+)
- 장시간 실행되는 서비스
- 여러 파이프라인 동시 관리
- 이벤트 기반 아키텍처

### 4.2 폴링 (Polling)

```python
# 패턴
while True:
    msg = bus.poll(Gst.MessageType.ANY, timeout)
    if msg:
        # 처리
```

**장점:**
- ✅ **간단함**: MainLoop 불필요
- ✅ **명확한 흐름**: 순차적 실행
- ✅ **타임아웃 제어**: 정확한 타임아웃 설정
- ✅ **디버깅 쉬움**: 동기식 실행

**단점:**
- ❌ **블로킹**: 메시지 대기 중 블록됨
- ❌ **CPU 사용**: 폴링 루프로 CPU 사용 증가
- ❌ **GUI 통합 어려움**: 메인 스레드 블록
- ❌ **멀티 파이프라인 어려움**: 하나씩만 처리

**적합한 경우:**
- 간단한 CLI 스크립트
- 단일 파이프라인
- 시간 제한 있는 작업 (녹화 등)
- 테스트/디버깅

### 4.3 메시지별 핸들러 분리

```python
# 패턴
bus.connect("message::error", on_error)
bus.connect("message::eos", on_eos)
bus.connect("message::state-changed", on_state_changed)
```

**장점:**
- ✅ **코드 구조 명확**: 각 메시지 타입별 함수
- ✅ **유지보수 쉬움**: 메시지별 독립 수정
- ✅ **테스트 쉬움**: 각 핸들러 독립 테스트
- ✅ **선택적 처리**: 필요한 메시지만 연결

**단점:**
- ❌ **함수 개수 증가**: 메시지 타입마다 함수 필요
- ❌ **상태 공유**: 핸들러 간 상태 공유 복잡
- ❌ **오버헤드**: 각 메시지별 시그널 연결 오버헤드

**적합한 경우:**
- 대규모 프로젝트
- 많은 메시지 타입 처리
- 팀 협업 개발
- 명확한 코드 구조 필요

---

## 5. 현재 프로젝트와 비교

### 5.1 현재 프로젝트 구현 (nvr_gstreamer)

```python
# camera/gst_pipeline.py Line 606-648
def _on_bus_message(self, bus, message):
    """버스 메시지 처리"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name() if message.src else "unknown"
        logger.error(f"Pipeline error from {src_name}: {err}")
        logger.debug(f"Error debug info: {debug}")

        # 녹화 관련 엘리먼트에서 에러 발생 시 특별 처리
        if src_name in ["splitmuxsink", "record_parse", "recording_valve", "record_queue"]:
            logger.error(f"[RECORDING DEBUG] Recording branch error from {src_name}: {err}")
            if self.recording_valve:
                valve_drop = self.recording_valve.get_property("drop")
                logger.error(f"[RECORDING DEBUG] Current recording_valve drop={valve_drop}")

        # Video sink 에러인 경우 (윈도우 핸들 없음 또는 테스트 모드)
        if "videosink" in src_name or "Output window" in str(err):
            logger.warning(f"Video sink error (ignoring): {err}")
            if not self.window_handle:
                logger.debug("No window handle - video sink error ignored")
                return

        # 다른 중요한 에러는 파이프라인 중지
        self.stop()

    elif t == Gst.MessageType.EOS:
        logger.info("End of stream")

    elif t == Gst.MessageType.STATE_CHANGED:
        if message.src == self.pipeline:
            old_state, new_state, pending_state = message.parse_state_changed()
            logger.debug(f"Pipeline state: {old_state.value_nick} -> {new_state.value_nick}")

    elif t == Gst.MessageType.WARNING:
        warn, debug = message.parse_warning()
        src_name = message.src.get_name() if message.src else "unknown"
        logger.warning(f"Pipeline warning from {src_name}: {warn}")
        if src_name in ["splitmuxsink", "record_parse", "recording_valve"]:
            logger.warning(f"[RECORDING DEBUG] Recording branch warning: {warn}")
```

### 5.2 비교 분석

| 항목 | 오픈소스 예제 | 현재 프로젝트 | 평가 |
|------|--------------|--------------|------|
| **처리 방식** | 비동기 (MainLoop) | 비동기 (MainLoop) | ✅ 동일 |
| **메시지 타입** | EOS, ERROR, (WARNING) | EOS, ERROR, WARNING, STATE_CHANGED | ✅ 더 포괄적 |
| **에러 분류** | 일괄 처리 | 소스별 분류 처리 | ✅ 더 정교함 |
| **로깅** | print 사용 | loguru 사용 | ✅ 더 체계적 |
| **에러 복구** | 즉시 종료 | 선택적 종료/무시 | ✅ 더 유연함 |
| **디버그 정보** | 기본 출력 | 상세 디버그 정보 | ✅ 더 자세함 |

**현재 프로젝트의 강점:**

1. **소스별 에러 분류**
   ```python
   # 녹화 브랜치 에러 → 로깅만
   if src_name in ["splitmuxsink", "record_parse", "recording_valve", "record_queue"]:
       logger.error(f"[RECORDING DEBUG] Recording branch error")
       # 파이프라인은 계속 실행

   # 비디오 싱크 에러 (윈도우 없음) → 무시
   if "videosink" in src_name and not self.window_handle:
       return  # 테스트 모드

   # 기타 중요 에러 → 파이프라인 중지
   self.stop()
   ```

2. **상세한 디버그 정보**
   ```python
   # Valve 상태 확인
   valve_drop = self.recording_valve.get_property("drop")
   logger.error(f"Current recording_valve drop={valve_drop}")
   ```

3. **체계적인 로깅**
   ```python
   # loguru 사용으로 로그 레벨별 관리
   logger.error()   # 에러
   logger.warning() # 경고
   logger.debug()   # 디버그
   logger.info()    # 정보
   ```

**개선 가능한 점:**

1. **메시지별 핸들러 분리 고려**
   ```python
   # 현재: 하나의 큰 함수
   def _on_bus_message(self, bus, message):
       # 50줄 이상의 if-elif 체인

   # 개선안: 메시지별 분리
   def _on_error_message(self, bus, message):
       # 에러 처리만

   def _on_eos_message(self, bus, message):
       # EOS 처리만

   def _on_state_changed_message(self, bus, message):
       # 상태 변경 처리만
   ```

2. **INFO 메시지 처리 추가**
   ```python
   elif t == Gst.MessageType.INFO:
       info, debug = message.parse_info()
       logger.info(f"Pipeline info: {info}")
   ```

3. **BUFFERING 메시지 처리 (RTSP 스트리밍)**
   ```python
   elif t == Gst.MessageType.BUFFERING:
       percent = message.parse_buffering()
       logger.debug(f"Buffering: {percent}%")

       # 버퍼링이 100% 미만이면 일시정지
       if percent < 100:
           self.pipeline.set_state(Gst.State.PAUSED)
       else:
           self.pipeline.set_state(Gst.State.PLAYING)
   ```

---

## 6. 모범 사례 및 권장사항

### 6.1 일반적인 패턴

```python
class GstPipeline:
    """GStreamer 파이프라인 베스트 프랙티스"""

    def __init__(self):
        self.pipeline = Gst.Pipeline.new("pipeline")

        # Bus 설정
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_bus_message)

        # MainLoop (PyQt/GTK 사용 시 불필요)
        self.loop = GLib.MainLoop()

    def _on_bus_message(self, bus, message):
        """통합 메시지 핸들러"""
        t = message.type

        # 1. EOS - 정상 종료
        if t == Gst.MessageType.EOS:
            self._handle_eos(message)

        # 2. ERROR - 에러 처리
        elif t == Gst.MessageType.ERROR:
            self._handle_error(message)

        # 3. WARNING - 경고 처리
        elif t == Gst.MessageType.WARNING:
            self._handle_warning(message)

        # 4. STATE_CHANGED - 상태 변경
        elif t == Gst.MessageType.STATE_CHANGED:
            self._handle_state_changed(message)

        # 5. BUFFERING - 버퍼링 (RTSP 스트리밍)
        elif t == Gst.MessageType.BUFFERING:
            self._handle_buffering(message)

        # 6. INFO - 정보 메시지
        elif t == Gst.MessageType.INFO:
            self._handle_info(message)

        return True

    def _handle_eos(self, message):
        """EOS 처리"""
        logger.info("End-of-stream received")
        self.pipeline.set_state(Gst.State.NULL)
        self.loop.quit()

    def _handle_error(self, message):
        """에러 처리"""
        err, debug = message.parse_error()
        src_name = message.src.get_name() if message.src else "unknown"

        logger.error(f"Error from {src_name}: {err}")
        logger.debug(f"Debug info: {debug}")

        # 에러 타입별 분류
        error_domain = err.domain
        error_code = err.code

        if error_domain == "gst-resource-error-quark":
            self._handle_resource_error(src_name, error_code, err)
        elif error_domain == "gst-stream-error-quark":
            self._handle_stream_error(src_name, error_code, err)
        elif error_domain == "gst-core-error-quark":
            self._handle_core_error(src_name, error_code, err)
        else:
            # 알 수 없는 에러 - 파이프라인 중지
            self.stop()

    def _handle_resource_error(self, src_name, code, err):
        """리소스 에러 (파일, 네트워크 등)"""
        from gi.repository import GLib

        if code == GLib.Error.NOT_FOUND:
            logger.error(f"Resource not found: {src_name}")
        elif code == GLib.Error.OPEN_READ:
            logger.error(f"Cannot open for reading: {src_name}")
        elif code == GLib.Error.OPEN_WRITE:
            logger.error(f"Cannot open for writing: {src_name}")

        # 재연결 시도 또는 종료
        self.stop()

    def _handle_stream_error(self, src_name, code, err):
        """스트림 에러 (디코딩, 포맷 등)"""
        logger.error(f"Stream error from {src_name}: {err}")
        self.stop()

    def _handle_warning(self, message):
        """경고 처리"""
        warn, debug = message.parse_warning()
        src_name = message.src.get_name() if message.src else "unknown"

        logger.warning(f"Warning from {src_name}: {warn}")
        if debug:
            logger.debug(f"Debug info: {debug}")

        # 경고는 파이프라인 계속 실행

    def _handle_state_changed(self, message):
        """상태 변경 처리"""
        # 파이프라인 레벨의 상태 변경만 처리
        if message.src != self.pipeline:
            return

        old, new, pending = message.parse_state_changed()
        logger.debug(f"State: {old.value_nick} -> {new.value_nick}")

        # 상태별 처리
        if new == Gst.State.PLAYING:
            logger.info("Pipeline is now playing")
        elif new == Gst.State.PAUSED:
            logger.info("Pipeline is paused")

    def _handle_buffering(self, message):
        """버퍼링 처리 (RTSP 스트리밍)"""
        percent = message.parse_buffering()
        logger.debug(f"Buffering: {percent}%")

        # 100% 미만이면 일시정지
        if percent < 100:
            self.pipeline.set_state(Gst.State.PAUSED)
        elif self.target_state == Gst.State.PLAYING:
            self.pipeline.set_state(Gst.State.PLAYING)

    def _handle_info(self, message):
        """정보 메시지 처리"""
        info, debug = message.parse_info()
        src_name = message.src.get_name() if message.src else "unknown"
        logger.info(f"Info from {src_name}: {info}")
```

### 6.2 에러 도메인별 처리

GStreamer 에러는 **도메인(domain)**과 **코드(code)**로 분류됩니다:

| 도메인 | 설명 | 주요 코드 |
|--------|------|-----------|
| **gst-core-error-quark** | GStreamer 코어 에러 | FAILED, TOO_LAZY, NOT_IMPLEMENTED |
| **gst-library-error-quark** | 라이브러리 에러 | INIT, SHUTDOWN, SETTINGS |
| **gst-resource-error-quark** | 리소스 에러 | NOT_FOUND, BUSY, OPEN_READ, OPEN_WRITE |
| **gst-stream-error-quark** | 스트림 에러 | FAILED, DECODE, ENCODE, FORMAT |

```python
def _handle_error_by_domain(self, message):
    """에러 도메인별 처리"""
    err, debug = message.parse_error()

    # 도메인 확인
    domain = err.domain
    code = err.code

    if domain == "gst-resource-error-quark":
        # 리소스 에러
        if code == 3:  # NOT_FOUND
            logger.error("Resource not found - check file/URL")
            # 재연결 시도
            self.schedule_reconnect()
        elif code == 6:  # OPEN_WRITE
            logger.error("Cannot write to file - check permissions")
            # 녹화 중지
            self.stop_recording()

    elif domain == "gst-stream-error-quark":
        # 스트림 에러
        if code == 1:  # FAILED
            logger.error("Stream processing failed")
        elif code == 6:  # DECODE
            logger.error("Decoding failed - codec issue?")

    # 기타 에러 - 파이프라인 중지
    self.stop()
```

### 6.3 RTSP 스트리밍 특화 처리

```python
def _on_bus_message_rtsp(self, bus, message):
    """RTSP 스트리밍 특화 메시지 처리"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # RTSP 연결 에러
        if "rtspsrc" in src_name:
            if "Could not connect" in str(err):
                logger.error("RTSP connection failed - retrying...")
                self.schedule_reconnect(delay=5)
                return
            elif "timeout" in str(err).lower():
                logger.error("RTSP timeout - retrying...")
                self.schedule_reconnect(delay=3)
                return

        # 기본 에러 처리
        self._handle_error(message)

    elif t == Gst.MessageType.BUFFERING:
        percent = message.parse_buffering()

        # RTSP는 버퍼링 시 일시정지 필요
        if percent < 100:
            logger.debug(f"RTSP buffering: {percent}%")
            self.pipeline.set_state(Gst.State.PAUSED)
        else:
            logger.debug("RTSP buffering complete")
            self.pipeline.set_state(Gst.State.PLAYING)

    elif t == Gst.MessageType.ELEMENT:
        # rtspsrc의 커스텀 메시지 처리
        structure = message.get_structure()
        if structure and structure.has_name("GstUDPSrcTimeout"):
            logger.warning("UDP timeout - network issue?")
```

### 6.4 권장 로깅 구조

```python
# loguru 사용 예시
from loguru import logger

# 로거 설정
logger.add(
    "logs/gstreamer_{time}.log",
    rotation="100 MB",
    retention="10 days",
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

def _on_bus_message(self, bus, message):
    """메시지 핸들러 with 체계적 로깅"""
    t = message.type
    src_name = message.src.get_name() if message.src else "unknown"

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()

        # 에러 로깅 (자동으로 스택 트레이스 포함)
        logger.error(
            f"GStreamer Error\n"
            f"  Source: {src_name}\n"
            f"  Error: {err}\n"
            f"  Debug: {debug}"
        )

        # 에러 컨텍스트 추가
        logger.opt(depth=1).error(f"Pipeline state: {self.pipeline.get_state(0)}")

    elif t == Gst.MessageType.WARNING:
        warn, debug = message.parse_warning()

        logger.warning(
            f"GStreamer Warning\n"
            f"  Source: {src_name}\n"
            f"  Warning: {warn}\n"
            f"  Debug: {debug}"
        )

    elif t == Gst.MessageType.STATE_CHANGED:
        if message.src == self.pipeline:
            old, new, pending = message.parse_state_changed()
            logger.debug(f"Pipeline state: {old.value_nick} → {new.value_nick}")
```

### 6.5 단위 테스트 가능한 구조

```python
class GstPipeline:
    """테스트 가능한 파이프라인 구조"""

    def __init__(self, error_handler=None, eos_handler=None):
        self.pipeline = Gst.Pipeline.new("pipeline")

        # 의존성 주입 (테스트 시 mock 주입 가능)
        self.error_handler = error_handler or self._default_error_handler
        self.eos_handler = eos_handler or self._default_eos_handler

        # Bus 설정
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _on_bus_message(self, bus, message):
        """메시지 핸들러 (테스트 가능)"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            return self.error_handler(message)
        elif t == Gst.MessageType.EOS:
            return self.eos_handler(message)

    def _default_error_handler(self, message):
        """기본 에러 핸들러"""
        err, debug = message.parse_error()
        logger.error(f"Error: {err}")
        self.stop()

    def _default_eos_handler(self, message):
        """기본 EOS 핸들러"""
        logger.info("End-of-stream")
        self.stop()

# 테스트 코드
import unittest
from unittest.mock import Mock

class TestGstPipeline(unittest.TestCase):
    def test_error_handling(self):
        """에러 처리 테스트"""
        # Mock 에러 핸들러
        mock_error_handler = Mock()

        # 파이프라인 생성 (mock 주입)
        pipeline = GstPipeline(error_handler=mock_error_handler)

        # 에러 메시지 시뮬레이션
        # ... (실제 테스트 코드)

        # 핸들러 호출 확인
        mock_error_handler.assert_called_once()
```

---

## 7. 요약 및 결론

### 7.1 핵심 패턴 비교

| 패턴 | 사용 사례 | 복잡도 | 추천도 |
|------|----------|--------|--------|
| **비동기 (MainLoop)** | GUI 앱, 장기 실행 서비스 | 중간 | ⭐⭐⭐⭐⭐ |
| **폴링 (Polling)** | CLI 스크립트, 단순 작업 | 낮음 | ⭐⭐⭐ |
| **메시지별 핸들러** | 대규모 프로젝트 | 높음 | ⭐⭐⭐⭐ |
| **동기 핸들러** | 특수 용도 (오버레이) | 매우 높음 | ⭐⭐ |

### 7.2 현재 프로젝트 평가

**강점:**
- ✅ 비동기 처리 (MainLoop) 사용 → 올바른 선택
- ✅ 소스별 에러 분류 → 정교한 에러 처리
- ✅ 체계적 로깅 (loguru) → 디버깅 용이
- ✅ 선택적 에러 무시 → 유연한 운영

**개선 가능:**
- 📝 메시지별 핸들러 분리 고려 (가독성)
- 📝 BUFFERING 메시지 처리 추가 (RTSP 안정성)
- 📝 에러 도메인별 분류 (정교한 복구)
- 📝 단위 테스트 구조 개선

### 7.3 최종 권장사항

**1. 기본 패턴 (모든 프로젝트)**
```python
# 비동기 처리 + 통합 핸들러
bus.add_signal_watch()
bus.connect("message", self._on_bus_message)
```

**2. 중급 패턴 (중대형 프로젝트)**
```python
# 메시지별 핸들러 분리
bus.connect("message::error", self._on_error)
bus.connect("message::eos", self._on_eos)
bus.connect("message::warning", self._on_warning)
```

**3. 고급 패턴 (엔터프라이즈)**
```python
# 에러 도메인별 + 소스별 분류 + 체계적 로깅
def _handle_error(self, message):
    domain = err.domain
    code = err.code
    src_name = message.src.get_name()

    # 도메인별 분류
    # 소스별 분류
    # 컨텍스트 로깅
```

---

**문서 버전:** 1.0
**작성일:** 2025-10-30
**참고 프로젝트:** GStreamer/gst-python, Pitivi, tamaggo/gstreamer-examples 등
