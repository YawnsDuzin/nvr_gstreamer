# GStreamer Python 예외처리 패턴 분석

## 목차
1. [개요 및 조사 범위](#1-개요-및-조사-범위)
2. [네트워크 연결 에러 처리](#2-네트워크-연결-에러-처리)
3. [저장매체 에러 처리](#3-저장매체-에러-처리)
4. [파이프라인 복구 전략](#4-파이프라인-복구-전략)
5. [실전 구현 패턴](#5-실전-구현-패턴)
6. [현재 프로젝트 개선안](#6-현재-프로젝트-개선안)

---

## 1. 개요 및 조사 범위

### 1.1 조사 대상 예외 상황

| 예외 상황 | 설명 | 심각도 | 복구 가능성 |
|----------|------|--------|-------------|
| **네트워크 끊김** | RTSP 카메라 연결 끊김 | 높음 | 자동 복구 가능 |
| **카메라 오프라인** | 카메라 전원 꺼짐/재부팅 | 높음 | 자동 복구 가능 |
| **디스크 Full** | 저장공간 부족 | 높음 | 파일 삭제 후 복구 |
| **USB/HDD 분리** | 외장 드라이브 물리적 분리 | 높음 | 재연결 후 복구 |
| **디코더 에러** | 손상된 스트림 | 중간 | 버퍼 플러시 후 복구 |
| **파일 권한 에러** | Write 권한 없음 | 낮음 | 수동 개입 필요 |
| **메모리 부족** | OOM (Out of Memory) | 치명적 | 프로세스 재시작 필요 |

### 1.2 조사 출처

**오픈소스 프로젝트:**
- [GStreamer 공식 예제](https://github.com/GStreamer/gst-python)
- [tylercubell/automatic-restart-gist](https://gist.github.com/tylercubell/14cf51a40c517e12c102c8f77831ee80)
- [acschristoph/python_gst_rtsp_player](https://github.com/acschristoph/python_gst_rtsp_player)
- [uutzinger/camera](https://github.com/uutzinger/camera)

**기술 문서:**
- [GStreamer Fallback Plugins](https://coaxion.net/blog/2020/07/automatic-retry-on-error-and-fallback-stream-handling-for-gstreamer-sources/)
- [GStreamer Discourse - RTSP Reconnection](https://discourse.gstreamer.org/t/rtsp-disconnect-and-reconnect-on-error-during-play/395)
- Stack Overflow 다수 질문/답변

---

## 2. 네트워크 연결 에러 처리

### 2.1 RTSP 카메라 재연결 - 기본 패턴

#### 2.1.1 패턴 1: 파이프라인 재시작 (가장 일반적) ✅

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import time

class RTSPReconnector:
    """RTSP 재연결 처리 클래스"""

    def __init__(self, rtsp_url, max_retries=10):
        self.rtsp_url = rtsp_url
        self.max_retries = max_retries
        self.retry_count = 0
        self.pipeline = None
        self.is_running = False
        self.reconnect_timer = None

    def create_pipeline(self):
        """파이프라인 생성"""
        pipeline_str = (
            f"rtspsrc location={self.rtsp_url} "
            "latency=200 protocols=tcp retry=5 timeout=10000000 ! "
            "rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! autovideosink"
        )
        self.pipeline = Gst.parse_launch(pipeline_str)

        # Bus 메시지 핸들러 연결
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def start(self):
        """스트리밍 시작"""
        if not self.pipeline:
            self.create_pipeline()

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Failed to start pipeline")
            self._schedule_reconnect()
            return False

        self.is_running = True
        self.retry_count = 0  # 성공 시 카운트 리셋
        print("Pipeline started successfully")
        return True

    def stop(self):
        """스트리밍 중지"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.is_running = False

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            src_name = message.src.get_name()
            print(f"Error from {src_name}: {err}")

            # rtspsrc 에러인 경우 재연결 시도
            if "rtspsrc" in src_name:
                if "Could not connect" in str(err) or "timeout" in str(err).lower():
                    print("RTSP connection error - scheduling reconnect...")
                    self._schedule_reconnect()
                    return True

            # 기타 에러 - 재연결 시도
            self._schedule_reconnect()

        elif t == Gst.MessageType.EOS:
            print("End of stream - reconnecting...")
            self._schedule_reconnect()

        return True

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프)"""
        if self.retry_count >= self.max_retries:
            print(f"Max retries ({self.max_retries}) reached - giving up")
            self.stop()
            return

        # 지수 백오프: 5, 10, 20, 40, 60, 60, ...초
        delay = min(5 * (2 ** self.retry_count), 60)
        self.retry_count += 1

        print(f"Reconnect attempt {self.retry_count}/{self.max_retries} in {delay}s...")

        # 기존 타이머 취소
        if self.reconnect_timer:
            self.reconnect_timer.cancel()

        # 새 타이머 시작
        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

    def _reconnect(self):
        """실제 재연결 수행"""
        print("Attempting to reconnect...")

        # 기존 파이프라인 정리
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            # 파이프라인 객체 유지 (재사용)

        # 짧은 대기 (리소스 해제 대기)
        time.sleep(0.5)

        # 재시작
        self.start()

def main():
    Gst.init(None)

    rtsp_url = "rtsp://admin:password@192.168.0.131:554/stream"
    reconnector = RTSPReconnector(rtsp_url)
    reconnector.start()

    # 메인 루프
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("Interrupted by user")
        reconnector.stop()

if __name__ == '__main__':
    main()
```

**특징:**
- ✅ 간단하고 안정적
- ✅ 지수 백오프 적용 (5, 10, 20, 40, 60초)
- ✅ 최대 재시도 횟수 제한
- ✅ 파이프라인 재사용 (성능)
- ❌ 재연결 중 비디오 중단

#### 2.1.2 패턴 2: Fallback Source (고급) ⭐

GStreamer Rust 플러그인의 `fallbacksrc` 사용:

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

class FallbackRTSPPlayer:
    """Fallback 메커니즘을 사용한 RTSP 플레이어"""

    def __init__(self, rtsp_url, fallback_url=None):
        self.rtsp_url = rtsp_url
        self.fallback_url = fallback_url or "videotestsrc pattern=snow ! video/x-raw,width=640,height=480"

    def create_pipeline(self):
        """Fallbacksrc를 사용한 파이프라인 생성"""
        # fallbacksrc 엘리먼트 사용
        pipeline_str = (
            f"fallbacksrc uri={self.rtsp_url} "
            f"fallback-uri={self.fallback_url} "
            "timeout=10000000000 "  # 10초 타임아웃
            "restart-timeout=5000000000 "  # 5초 후 재시도
            "retry-timeout=1000000000 "  # 1초 재시도 간격
            "! videoconvert ! autovideosink"
        )
        self.pipeline = Gst.parse_launch(pipeline_str)

        # Bus 설정
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ELEMENT:
            # fallbacksrc의 커스텀 메시지 처리
            structure = message.get_structure()
            if structure:
                name = structure.get_name()
                if name == "fallback-activated":
                    print("Fallback source activated - primary source failed")
                elif name == "fallback-deactivated":
                    print("Primary source recovered")

        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}")

        return True

    def start(self):
        """재생 시작"""
        self.create_pipeline()
        self.pipeline.set_state(Gst.State.PLAYING)

def main():
    Gst.init(None)

    rtsp_url = "rtsp://admin:password@192.168.0.131:554/stream"
    player = FallbackRTSPPlayer(rtsp_url)
    player.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
```

**특징:**
- ✅ **자동 재연결** (수동 코드 불필요)
- ✅ **Fallback 스트림** (메인 실패 시 대체)
- ✅ **무중단 전환** (사용자 경험 우수)
- ❌ GStreamer Rust 플러그인 필요 (추가 설치)
- ❌ GStreamer 1.14+ 필요

**설치 방법:**
```bash
# Rust 플러그인 설치
git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git
cd gst-plugins-rs
cargo build --release
cp target/release/libgstfallbackswitch.so /usr/lib/gstreamer-1.0/
```

#### 2.1.3 패턴 3: Input Selector (무중단 전환) 🔄

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

class InputSelectorRTSP:
    """Input Selector를 사용한 소스 전환"""

    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.pipeline = None
        self.input_selector = None
        self.rtsp_pad = None
        self.fallback_pad = None

    def create_pipeline(self):
        """Input Selector 파이프라인 생성"""
        self.pipeline = Gst.Pipeline.new("pipeline")

        # RTSP 소스
        rtsp_src = Gst.ElementFactory.make("rtspsrc", "rtsp")
        rtsp_src.set_property("location", self.rtsp_url)
        rtsp_src.set_property("latency", 200)
        rtsp_src.set_property("protocols", "tcp")

        rtsp_depay = Gst.ElementFactory.make("rtph264depay", "depay")
        rtsp_parse = Gst.ElementFactory.make("h264parse", "parse")
        rtsp_decode = Gst.ElementFactory.make("avdec_h264", "decode")

        # Fallback 소스 (테스트 패턴)
        fallback_src = Gst.ElementFactory.make("videotestsrc", "fallback")
        fallback_src.set_property("pattern", "snow")

        fallback_convert = Gst.ElementFactory.make("videoconvert", "fallback_convert")

        # Input Selector
        self.input_selector = Gst.ElementFactory.make("input-selector", "selector")
        self.input_selector.set_property("sync-streams", True)

        # 출력
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        sink = Gst.ElementFactory.make("autovideosink", "sink")

        # 파이프라인에 추가
        self.pipeline.add(rtsp_src, rtsp_depay, rtsp_parse, rtsp_decode)
        self.pipeline.add(fallback_src, fallback_convert)
        self.pipeline.add(self.input_selector, convert, sink)

        # RTSP 체인 연결 (rtspsrc는 동적 패드)
        rtsp_src.connect("pad-added", self._on_rtsp_pad_added, rtsp_depay)
        rtsp_depay.link(rtsp_parse)
        rtsp_parse.link(rtsp_decode)

        # Fallback 체인 연결
        fallback_src.link(fallback_convert)

        # Selector 출력 연결
        self.input_selector.link(convert)
        convert.link(sink)

        # Selector 입력 패드 연결
        # RTSP 소스 → Selector
        rtsp_src_pad = rtsp_decode.get_static_pad("src")
        self.rtsp_pad = self.input_selector.get_request_pad("sink_%u")
        rtsp_src_pad.link(self.rtsp_pad)

        # Fallback 소스 → Selector
        fallback_src_pad = fallback_convert.get_static_pad("src")
        self.fallback_pad = self.input_selector.get_request_pad("sink_%u")
        fallback_src_pad.link(self.fallback_pad)

        # 초기 활성 패드: RTSP
        self.input_selector.set_property("active-pad", self.rtsp_pad)

        # Bus 설정
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _on_rtsp_pad_added(self, src, pad, depay):
        """RTSP 동적 패드 연결"""
        sink_pad = depay.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)

    def _on_bus_message(self, bus, message):
        """버스 메시지 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            src_name = message.src.get_name()

            # RTSP 소스 에러 → Fallback으로 전환
            if "rtsp" in src_name or "depay" in src_name or "parse" in src_name:
                print(f"RTSP error: {err} - switching to fallback")
                self._switch_to_fallback()

        elif t == Gst.MessageType.EOS:
            src_name = message.src.get_name()
            if "rtsp" in src_name:
                print("RTSP EOS - switching to fallback")
                self._switch_to_fallback()

        return True

    def _switch_to_fallback(self):
        """Fallback 소스로 전환"""
        if self.input_selector and self.fallback_pad:
            self.input_selector.set_property("active-pad", self.fallback_pad)
            print("Switched to fallback source")

            # 5초 후 RTSP 재연결 시도
            GLib.timeout_add_seconds(5, self._try_reconnect_rtsp)

    def _try_reconnect_rtsp(self):
        """RTSP 재연결 시도"""
        print("Attempting to reconnect RTSP...")
        # RTSP 소스를 NULL로 설정 후 재시작
        rtsp_src = self.pipeline.get_by_name("rtsp")
        rtsp_src.set_state(Gst.State.NULL)

        # 짧은 대기
        GLib.timeout_add(500, self._restart_rtsp)
        return False  # 타이머 반복 안 함

    def _restart_rtsp(self):
        """RTSP 소스 재시작"""
        rtsp_src = self.pipeline.get_by_name("rtsp")
        ret = rtsp_src.set_state(Gst.State.PLAYING)

        if ret != Gst.StateChangeReturn.FAILURE:
            print("RTSP reconnected - switching back to RTSP")
            self.input_selector.set_property("active-pad", self.rtsp_pad)

        return False  # 타이머 반복 안 함

    def start(self):
        """재생 시작"""
        self.create_pipeline()
        self.pipeline.set_state(Gst.State.PLAYING)

def main():
    Gst.init(None)

    rtsp_url = "rtsp://admin:password@192.168.0.131:554/stream"
    player = InputSelectorRTSP(rtsp_url)
    player.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
```

**특징:**
- ✅ **무중단 전환** (RTSP ↔ Fallback)
- ✅ **파이프라인 유지** (PLAYING 상태 유지)
- ✅ **자동 복구 시도**
- ❌ 복잡한 구조
- ❌ 메모리 오버헤드 (2개 소스 유지)

### 2.2 재연결 전략 비교

| 전략 | 복잡도 | 재연결 속도 | 무중단 전환 | 리소스 사용 | 추천도 |
|------|--------|-------------|------------|-------------|--------|
| **파이프라인 재시작** | 낮음 | 느림 (5-60초) | ❌ | 낮음 | ⭐⭐⭐⭐⭐ |
| **Fallbacksrc** | 낮음 | 자동 | ✅ | 낮음 | ⭐⭐⭐⭐ |
| **Input Selector** | 높음 | 빠름 (5초) | ✅ | 높음 | ⭐⭐⭐ |

### 2.3 지수 백오프 (Exponential Backoff) 구현

```python
import time
import random

class ExponentialBackoff:
    """지수 백오프 재시도 전략"""

    def __init__(self, base_delay=5, max_delay=60, max_retries=10, jitter=True):
        """
        Args:
            base_delay: 초기 지연 시간 (초)
            max_delay: 최대 지연 시간 (초)
            max_retries: 최대 재시도 횟수
            jitter: 지터 추가 여부 (랜덤 요소)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.jitter = jitter
        self.retry_count = 0

    def get_delay(self):
        """현재 재시도 횟수에 대한 지연 시간 계산"""
        if self.retry_count >= self.max_retries:
            return None  # 더 이상 재시도 안 함

        # 지수 백오프: base * 2^retry_count
        delay = self.base_delay * (2 ** self.retry_count)

        # 최대 지연 시간 제한
        delay = min(delay, self.max_delay)

        # Jitter 추가 (AWS 권장 방식)
        if self.jitter:
            delay = random.uniform(0, delay)

        return delay

    def reset(self):
        """성공 시 카운트 리셋"""
        self.retry_count = 0

    def increment(self):
        """재시도 카운트 증가"""
        self.retry_count += 1
        return self.retry_count < self.max_retries

# 사용 예시
backoff = ExponentialBackoff(base_delay=5, max_delay=60, max_retries=10, jitter=True)

while True:
    try:
        # 연결 시도
        connect_to_rtsp()
        backoff.reset()  # 성공 시 리셋
        break
    except Exception as e:
        print(f"Connection failed: {e}")

        if not backoff.increment():
            print("Max retries reached")
            break

        delay = backoff.get_delay()
        if delay is None:
            break

        print(f"Retrying in {delay:.2f} seconds...")
        time.sleep(delay)
```

**지연 시간 예시 (base=5, max=60, jitter=False):**

| 재시도 | 계산 | 실제 지연 (초) |
|--------|------|---------------|
| 1 | 5 × 2^0 | 5 |
| 2 | 5 × 2^1 | 10 |
| 3 | 5 × 2^2 | 20 |
| 4 | 5 × 2^3 | 40 |
| 5 | 5 × 2^4 = 80 → max | 60 |
| 6+ | max | 60 |

**Jitter 적용 시:**
- 재시도 1: 0~5초 랜덤
- 재시도 2: 0~10초 랜덤
- 재시도 3: 0~20초 랜덤

**Jitter의 장점:**
- 여러 카메라 동시 재연결 시 충돌 방지
- 서버 부하 분산
- AWS 권장 방식

---

## 3. 저장매체 에러 처리

### 3.1 디스크 Full 감지 및 처리

#### 3.1.1 사전 예방 (Proactive)

```python
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta

class DiskSpaceManager:
    """디스크 공간 관리"""

    def __init__(self, recording_dir, min_free_gb=10, cleanup_threshold_gb=5):
        """
        Args:
            recording_dir: 녹화 디렉토리
            min_free_gb: 최소 여유 공간 (GB)
            cleanup_threshold_gb: 정리 시작 임계값 (GB)
        """
        self.recording_dir = Path(recording_dir)
        self.min_free_gb = min_free_gb
        self.cleanup_threshold_gb = cleanup_threshold_gb

    def get_free_space_gb(self):
        """사용 가능한 디스크 공간 (GB)"""
        stat = shutil.disk_usage(self.recording_dir)
        return stat.free / (1024 ** 3)

    def get_free_space_percent(self):
        """사용 가능한 디스크 공간 (%)"""
        stat = shutil.disk_usage(self.recording_dir)
        return (stat.free / stat.total) * 100

    def needs_cleanup(self):
        """정리 필요 여부"""
        free_gb = self.get_free_space_gb()
        return free_gb < self.cleanup_threshold_gb

    def auto_cleanup(self, max_age_days=30):
        """자동 파일 정리"""
        if not self.needs_cleanup():
            return

        print(f"Disk space low ({self.get_free_space_gb():.2f}GB) - cleaning up...")

        # 1단계: 오래된 파일 삭제 (날짜 기준)
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_count = self._delete_old_files(cutoff_date)
        print(f"Deleted {deleted_count} old files (>{max_age_days} days)")

        # 2단계: 여전히 부족하면 가장 오래된 파일부터 삭제
        if self.needs_cleanup():
            deleted_count = self._delete_oldest_files_until_space()
            print(f"Deleted {deleted_count} additional files to free space")

    def _delete_old_files(self, cutoff_date):
        """특정 날짜 이전 파일 삭제"""
        deleted = 0
        for file_path in self.recording_dir.rglob("*.mp4"):
            if not file_path.is_file():
                continue

            # 파일 수정 시간 확인
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_date:
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

        return deleted

    def _delete_oldest_files_until_space(self):
        """공간이 확보될 때까지 가장 오래된 파일 삭제"""
        deleted = 0

        # 모든 파일 목록 (수정 시간 순 정렬)
        files = sorted(
            self.recording_dir.rglob("*.mp4"),
            key=lambda p: p.stat().st_mtime
        )

        for file_path in files:
            if not self.needs_cleanup():
                break  # 충분한 공간 확보됨

            try:
                file_path.unlink()
                deleted += 1
                print(f"Deleted: {file_path.name} ({self.get_free_space_gb():.2f}GB free)")
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

        return deleted

# 사용 예시
disk_manager = DiskSpaceManager(
    recording_dir="/mnt/recordings",
    min_free_gb=10,
    cleanup_threshold_gb=5
)

# 주기적 체크 (타이머)
import threading

def check_disk_space():
    """주기적 디스크 공간 체크 (10분마다)"""
    while True:
        try:
            if disk_manager.needs_cleanup():
                disk_manager.auto_cleanup(max_age_days=30)
        except Exception as e:
            print(f"Disk cleanup error: {e}")

        time.sleep(600)  # 10분

# 백그라운드 스레드 시작
cleanup_thread = threading.Thread(target=check_disk_space, daemon=True)
cleanup_thread.start()
```

#### 3.1.2 에러 발생 시 처리 (Reactive)

```python
def _on_bus_message(self, bus, message):
    """버스 메시지 처리"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # filesink/splitmuxsink 에러 확인
        if "sink" in src_name.lower():
            # 에러 도메인 확인
            if err.domain == "gst-resource-error-quark":
                # 리소스 에러 코드 확인
                import errno

                # ENOSPC (No space left on device) = 28
                if "space" in str(err).lower() or "No space" in str(err):
                    print("Disk full error detected!")
                    self._handle_disk_full()
                    return True

                # EACCES (Permission denied) = 13
                elif "permission" in str(err).lower():
                    print("Permission error detected!")
                    self._handle_permission_error()
                    return True

        # 기타 에러 처리
        # ...

def _handle_disk_full(self):
    """디스크 Full 처리"""
    print("Handling disk full condition...")

    # 1. 녹화 일시 정지
    if self._is_recording:
        self.stop_recording()
        print("Recording stopped due to disk full")

    # 2. 디스크 정리 시도
    try:
        disk_manager.auto_cleanup(max_age_days=7)  # 7일 이상 파일 삭제

        # 3. 정리 후 재시작
        time.sleep(2)
        if disk_manager.get_free_space_gb() > 1:
            print(f"Space freed: {disk_manager.get_free_space_gb():.2f}GB")
            self.start_recording()
        else:
            print("Still not enough space - manual intervention required")
            # UI 알림 또는 이메일 전송
            self._notify_admin("Disk full - please free space")

    except Exception as e:
        print(f"Disk cleanup failed: {e}")
```

### 3.2 USB/HDD 분리 감지

#### 3.2.1 Linux - udev 이벤트 모니터링

```python
import pyudev
import threading

class StorageDeviceMonitor:
    """저장 장치 모니터링"""

    def __init__(self, mount_point="/mnt/recordings"):
        self.mount_point = mount_point
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='block')
        self.is_mounted = self._check_mount()

    def _check_mount(self):
        """마운트 상태 확인"""
        with open('/proc/mounts', 'r') as f:
            for line in f:
                if self.mount_point in line:
                    return True
        return False

    def start_monitoring(self):
        """모니터링 시작"""
        observer = pyudev.MonitorObserver(self.monitor, self._device_event)
        observer.start()
        print("Storage device monitoring started")

    def _device_event(self, action, device):
        """장치 이벤트 핸들러"""
        if action == 'remove':
            print(f"Device removed: {device.device_node}")

            # 녹화 디렉토리 장치인지 확인
            if not self._check_mount():
                print(f"Recording device unmounted: {self.mount_point}")
                self._handle_device_removed()

        elif action == 'add':
            print(f"Device added: {device.device_node}")

            # 자동 마운트 확인
            time.sleep(1)  # 마운트 대기
            if self._check_mount():
                print(f"Recording device mounted: {self.mount_point}")
                self._handle_device_added()

    def _handle_device_removed(self):
        """장치 제거 처리"""
        print("Handling device removal...")

        # 1. 녹화 중지
        if pipeline._is_recording:
            pipeline.stop_recording()
            print("Recording stopped due to device removal")

        # 2. 파이프라인은 계속 실행 (스트리밍 유지)
        # 녹화만 중지

        # 3. UI 알림
        print("⚠️  Recording device removed - insert device to resume recording")

    def _handle_device_added(self):
        """장치 추가 처리"""
        print("Handling device addition...")

        # 1. 디렉토리 확인
        if os.path.exists(self.mount_point):
            # 2. 녹화 재개
            if not pipeline._is_recording:
                pipeline.start_recording()
                print("✅ Recording resumed")

# 사용 예시
storage_monitor = StorageDeviceMonitor("/mnt/usb_recordings")
storage_monitor.start_monitoring()
```

**필수 패키지:**
```bash
pip install pyudev
```

#### 3.2.2 Windows - 드라이브 레터 모니터링

```python
import win32api
import win32file
import time
import threading

class WindowsDriveMonitor:
    """Windows 드라이브 모니터링"""

    def __init__(self, drive_letter="E:"):
        self.drive_letter = drive_letter
        self.is_available = self._check_drive()
        self.monitoring = False

    def _check_drive(self):
        """드라이브 존재 확인"""
        drives = win32api.GetLogicalDriveStrings()
        drives = [d for d in drives.split('\000') if d]
        return self.drive_letter + '\\' in drives

    def start_monitoring(self):
        """모니터링 시작"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print(f"Drive monitoring started: {self.drive_letter}")

    def _monitor_loop(self):
        """모니터링 루프"""
        while self.monitoring:
            current_state = self._check_drive()

            # 상태 변경 감지
            if current_state != self.is_available:
                if current_state:
                    print(f"Drive {self.drive_letter} connected")
                    self._handle_drive_connected()
                else:
                    print(f"Drive {self.drive_letter} disconnected")
                    self._handle_drive_disconnected()

                self.is_available = current_state

            time.sleep(2)  # 2초마다 체크

    def _handle_drive_connected(self):
        """드라이브 연결 처리"""
        # 녹화 재개
        if not pipeline._is_recording:
            pipeline.start_recording()

    def _handle_drive_disconnected(self):
        """드라이브 분리 처리"""
        # 녹화 중지
        if pipeline._is_recording:
            pipeline.stop_recording()

# 사용 예시
drive_monitor = WindowsDriveMonitor("E:")
drive_monitor.start_monitoring()
```

**필수 패키지:**
```bash
pip install pywin32
```

### 3.3 splitmuxsink 에러 처리

```python
def _on_bus_message(self, bus, message):
    """버스 메시지 처리"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        # splitmuxsink 에러 특별 처리
        if src_name == "splitmuxsink":
            print(f"splitmuxsink error: {err}")

            # 파일 쓰기 에러
            if "write" in str(err).lower():
                print("File write error - checking disk space...")

                # 디스크 공간 확인
                if disk_manager.get_free_space_gb() < 1:
                    self._handle_disk_full()
                else:
                    # 권한 또는 기타 I/O 에러
                    print("Disk has space but write failed - permission issue?")
                    self._handle_file_write_error()

            # 파일 분할 에러
            elif "split" in str(err).lower():
                print("File split error - attempting recovery...")
                self._recover_splitmuxsink()

def _recover_splitmuxsink(self):
    """splitmuxsink 복구"""
    print("Recovering splitmuxsink...")

    # 1. EOS 전송하여 현재 파일 정상 종료
    if self.splitmuxsink:
        pad = self.splitmuxsink.get_static_pad("video")
        if pad:
            pad.send_event(Gst.Event.new_eos())

    # 2. 짧은 대기
    time.sleep(0.5)

    # 3. splitmuxsink를 NULL로
    self.splitmuxsink.set_state(Gst.State.NULL)

    # 4. 새 location 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
    location_pattern = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")
    self.splitmuxsink.set_property("location", location_pattern)

    # 5. PLAYING 상태로 복구
    self.splitmuxsink.set_state(Gst.State.PLAYING)
    print("splitmuxsink recovered")
```

---

## 4. 파이프라인 복구 전략

### 4.1 전체 재시작 vs 부분 재시작

| 항목 | 전체 재시작 | 부분 재시작 |
|------|------------|------------|
| **복잡도** | 낮음 | 높음 |
| **복구 시간** | 느림 (5-10초) | 빠름 (1-2초) |
| **안정성** | 높음 | 중간 |
| **리소스** | 많음 | 적음 |
| **적용 대상** | RTSP 에러, 네트워크 끊김 | 파일 에러, 디코더 에러 |

### 4.2 Pad Probe를 사용한 부분 재시작

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

class PartialRestartPipeline:
    """부분 재시작 가능한 파이프라인"""

    def __init__(self):
        self.pipeline = None
        self.filesink = None
        self.probe_id = None

    def restart_filesink(self):
        """filesink만 재시작 (파이프라인은 계속 실행)"""
        print("Restarting filesink...")

        if not self.filesink:
            return

        # 1. Pad Probe 추가 (데이터 흐름 블록)
        sink_pad = self.filesink.get_static_pad("sink")
        self.probe_id = sink_pad.add_probe(
            Gst.PadProbeType.BLOCK_DOWNSTREAM,
            self._block_probe_callback
        )

    def _block_probe_callback(self, pad, info):
        """Pad Probe 콜백 - 데이터 흐름이 블록됨"""
        print("Data flow blocked")

        # 별도 스레드에서 재시작 수행
        thread = threading.Thread(target=self._do_restart_filesink)
        thread.start()

        # GST_PAD_PROBE_OK: 프로브 유지
        return Gst.PadProbeReturn.OK

    def _do_restart_filesink(self):
        """실제 filesink 재시작"""
        # 1. filesink를 NULL로
        self.filesink.set_state(Gst.State.NULL)
        print("filesink set to NULL")

        # 2. 새 파일 경로 설정
        new_location = self._generate_new_filename()
        self.filesink.set_property("location", new_location)
        print(f"New location: {new_location}")

        # 3. PLAYING 상태로 복구
        self.filesink.set_state(Gst.State.PLAYING)
        print("filesink set to PLAYING")

        # 4. Probe 제거 (데이터 흐름 재개)
        if self.probe_id:
            sink_pad = self.filesink.get_static_pad("sink")
            sink_pad.remove_probe(self.probe_id)
            self.probe_id = None
            print("Data flow resumed")

    def _generate_new_filename(self):
        """새 파일명 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"/recordings/video_{timestamp}.mp4"
```

**Pad Probe의 장점:**
- ✅ 파이프라인 전체를 재시작하지 않음
- ✅ 스트리밍은 계속 유지
- ✅ 빠른 복구 (1-2초)

**단점:**
- ❌ 복잡한 구현
- ❌ 스레드 안전성 고려 필요

### 4.3 Watchdog 타이머

```python
import threading
import time

class PipelineWatchdog:
    """파이프라인 감시 및 자동 복구"""

    def __init__(self, pipeline, timeout=30):
        """
        Args:
            pipeline: 감시할 파이프라인
            timeout: 무응답 판정 시간 (초)
        """
        self.pipeline = pipeline
        self.timeout = timeout
        self.last_activity = time.time()
        self.is_monitoring = False
        self.monitor_thread = None

    def update_activity(self):
        """활동 갱신 (버퍼 수신 시 호출)"""
        self.last_activity = time.time()

    def start(self):
        """감시 시작"""
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Watchdog started")

    def stop(self):
        """감시 중지"""
        self.is_monitoring = False

    def _monitor_loop(self):
        """감시 루프"""
        while self.is_monitoring:
            elapsed = time.time() - self.last_activity

            if elapsed > self.timeout:
                print(f"⚠️  Pipeline inactive for {elapsed:.1f}s - restarting...")
                self._restart_pipeline()
                self.last_activity = time.time()  # 리셋

            time.sleep(5)  # 5초마다 체크

    def _restart_pipeline(self):
        """파이프라인 재시작"""
        try:
            # NULL 상태로
            self.pipeline.set_state(Gst.State.NULL)
            time.sleep(0.5)

            # 재시작
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret != Gst.StateChangeReturn.FAILURE:
                print("✅ Pipeline restarted successfully")
            else:
                print("❌ Pipeline restart failed")

        except Exception as e:
            print(f"Restart error: {e}")

# 사용 예시
watchdog = PipelineWatchdog(pipeline, timeout=30)
watchdog.start()

# 버퍼 수신 시 활동 갱신
def on_new_sample(appsink):
    sample = appsink.emit("pull-sample")
    watchdog.update_activity()  # ← 활동 갱신
    return Gst.FlowReturn.OK

appsink.connect("new-sample", on_new_sample)
```

---

## 5. 실전 구현 패턴

### 5.1 종합 예외처리 클래스

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import time
from datetime import datetime
from pathlib import Path

class RobustNVRPipeline:
    """예외처리가 강화된 NVR 파이프라인"""

    def __init__(self, rtsp_url, recording_dir, camera_id):
        self.rtsp_url = rtsp_url
        self.recording_dir = Path(recording_dir)
        self.camera_id = camera_id

        # 파이프라인
        self.pipeline = None
        self.is_running = False
        self._is_recording = False

        # 재연결 관리
        self.backoff = ExponentialBackoff(base_delay=5, max_delay=60, max_retries=10)
        self.reconnect_timer = None

        # 디스크 관리
        self.disk_manager = DiskSpaceManager(
            recording_dir=recording_dir,
            min_free_gb=10,
            cleanup_threshold_gb=5
        )

        # Watchdog
        self.watchdog = None

    def create_pipeline(self):
        """파이프라인 생성"""
        # ... (파이프라인 생성 코드)

        # Bus 설정
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _on_bus_message(self, bus, message):
        """통합 에러 처리"""
        t = message.type

        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            src_name = message.src.get_name()

            # 1. RTSP 연결 에러
            if "rtspsrc" in src_name:
                self._handle_rtsp_error(err)

            # 2. 파일 쓰기 에러
            elif "sink" in src_name.lower():
                self._handle_sink_error(err)

            # 3. 디코더 에러
            elif "dec" in src_name:
                self._handle_decoder_error(err)

            # 4. 기타 에러
            else:
                self._handle_generic_error(err, src_name)

        elif t == Gst.MessageType.EOS:
            self._handle_eos()

        elif t == Gst.MessageType.WARNING:
            self._handle_warning(message)

        return True

    def _handle_rtsp_error(self, err):
        """RTSP 에러 처리"""
        print(f"RTSP error: {err}")

        # 연결 관련 에러인지 확인
        if any(keyword in str(err).lower() for keyword in ["connect", "timeout", "network"]):
            print("Network error detected - scheduling reconnect")
            self._schedule_reconnect()
        else:
            # 기타 RTSP 에러
            print("Other RTSP error - attempting restart")
            self._schedule_reconnect()

    def _handle_sink_error(self, err):
        """Sink 에러 처리"""
        print(f"Sink error: {err}")

        # 디스크 Full 체크
        if "space" in str(err).lower():
            print("Disk full detected")
            self._handle_disk_full()

        # 권한 에러
        elif "permission" in str(err).lower():
            print("Permission error - check directory permissions")
            # 녹화 중지
            if self._is_recording:
                self.stop_recording()

        # 기타 I/O 에러
        else:
            print("I/O error - attempting filesink recovery")
            self._recover_filesink()

    def _handle_decoder_error(self, err):
        """디코더 에러 처리"""
        print(f"Decoder error: {err}")

        # 손상된 스트림 - 버퍼 플러시 후 계속
        print("Flushing pipeline buffers...")
        self.pipeline.send_event(Gst.Event.new_flush_start())
        time.sleep(0.1)
        self.pipeline.send_event(Gst.Event.new_flush_stop(True))
        print("Pipeline flushed - continuing")

    def _handle_disk_full(self):
        """디스크 Full 처리"""
        print("Handling disk full...")

        # 1. 녹화 일시 중지
        if self._is_recording:
            self.stop_recording()

        # 2. 공간 확보
        try:
            self.disk_manager.auto_cleanup(max_age_days=7)

            # 3. 재시작
            time.sleep(2)
            if self.disk_manager.get_free_space_gb() > 2:
                print(f"Space freed: {self.disk_manager.get_free_space_gb():.2f}GB")
                self.start_recording()
            else:
                print("⚠️  Still not enough space - manual intervention needed")

        except Exception as e:
            print(f"Cleanup failed: {e}")

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프)"""
        delay = self.backoff.get_delay()
        if delay is None:
            print("Max retries reached")
            return

        print(f"Reconnecting in {delay:.2f}s (attempt {self.backoff.retry_count + 1})...")

        # 기존 타이머 취소
        if self.reconnect_timer:
            self.reconnect_timer.cancel()

        # 새 타이머
        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

        self.backoff.increment()

    def _reconnect(self):
        """재연결 수행"""
        print("Reconnecting...")

        # 파이프라인 재시작
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            time.sleep(0.5)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret != Gst.StateChangeReturn.FAILURE:
            print("✅ Reconnected successfully")
            self.backoff.reset()
        else:
            print("❌ Reconnect failed - retrying...")
            self._schedule_reconnect()

    def start(self):
        """시작"""
        if not self.pipeline:
            self.create_pipeline()

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Failed to start")
            return False

        self.is_running = True

        # Watchdog 시작
        self.watchdog = PipelineWatchdog(self.pipeline, timeout=30)
        self.watchdog.start()

        # 디스크 모니터링 시작
        self._start_disk_monitoring()

        return True

    def _start_disk_monitoring(self):
        """디스크 모니터링 시작"""
        def monitor():
            while self.is_running:
                try:
                    if self.disk_manager.needs_cleanup():
                        print("Proactive disk cleanup...")
                        self.disk_manager.auto_cleanup()
                except Exception as e:
                    print(f"Disk monitor error: {e}")

                time.sleep(600)  # 10분마다

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
```

### 5.2 에러 우선순위 처리

```python
class ErrorPriority:
    """에러 우선순위 정의"""
    CRITICAL = 1    # 즉시 중지
    HIGH = 2        # 빠른 복구 시도
    MEDIUM = 3      # 정상 복구 시도
    LOW = 4         # 로깅만

def classify_error(err, src_name):
    """에러 분류 및 우선순위 결정"""
    error_str = str(err).lower()

    # CRITICAL: 메모리 부족, 심각한 시스템 에러
    if any(kw in error_str for kw in ["memory", "allocation failed", "system"]):
        return ErrorPriority.CRITICAL

    # HIGH: 네트워크 끊김, 디스크 Full
    if any(kw in error_str for kw in ["connect", "network", "space", "timeout"]):
        return ErrorPriority.HIGH

    # MEDIUM: 디코더 에러, 포맷 에러
    if any(kw in error_str for kw in ["decode", "format", "stream"]):
        return ErrorPriority.MEDIUM

    # LOW: 경고성 에러
    return ErrorPriority.LOW

def _on_bus_message(self, bus, message):
    """우선순위 기반 에러 처리"""
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name()

        priority = classify_error(err, src_name)

        if priority == ErrorPriority.CRITICAL:
            print(f"❌ CRITICAL ERROR: {err}")
            # 즉시 중지
            self.stop()
            sys.exit(1)

        elif priority == ErrorPriority.HIGH:
            print(f"⚠️  HIGH PRIORITY ERROR: {err}")
            # 빠른 재연결 (지연 없음)
            self._reconnect_immediate()

        elif priority == ErrorPriority.MEDIUM:
            print(f"⚠️  MEDIUM PRIORITY ERROR: {err}")
            # 정상 재연결 (지수 백오프)
            self._schedule_reconnect()

        else:  # LOW
            print(f"ℹ️  LOW PRIORITY ERROR: {err}")
            # 로깅만
```

---

## 6. 현재 프로젝트 개선안

### 6.1 현재 구현 분석

**현재 프로젝트 (nvr_gstreamer) 예외처리 현황:**

| 항목 | 현재 상태 | 개선 필요 |
|------|----------|----------|
| **RTSP 재연결** | ❌ 없음 | ✅ 필요 |
| **지수 백오프** | ❌ 없음 | ✅ 필요 |
| **디스크 Full 처리** | ❌ 없음 | ✅ 필요 |
| **USB 분리 감지** | ❌ 없음 | ✅ 필요 |
| **Watchdog** | ❌ 없음 | ⚠️  선택적 |
| **에러 분류** | ✅ 있음 (소스별) | ⚠️  개선 가능 |

### 6.2 권장 개선사항

#### 6.2.1 우선순위 1: RTSP 재연결 (필수) ⭐⭐⭐⭐⭐

**위치:** `camera/streaming.py` - `CameraStream` 클래스

**현재 코드:**
```python
# camera/streaming.py
class CameraStream:
    def _on_error(self, err):
        # 에러 로깅만 있음
        logger.error(f"Stream error: {err}")
        self.status = StreamStatus.ERROR
```

**개선안:**
```python
# camera/streaming.py
class CameraStream:
    def __init__(self, config):
        # ...
        self.backoff = ExponentialBackoff(
            base_delay=5,
            max_delay=60,
            max_retries=10,
            jitter=True
        )
        self.reconnect_timer = None

    def _on_error(self, err):
        """에러 처리 with 자동 재연결"""
        logger.error(f"Stream error: {err}")
        self.status = StreamStatus.ERROR

        # 재연결 스케줄링
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프)"""
        delay = self.backoff.get_delay()
        if delay is None:
            logger.error(f"Max retries reached for {self.config.name}")
            self.status = StreamStatus.DISCONNECTED
            return

        logger.info(f"Reconnecting in {delay:.2f}s (attempt {self.backoff.retry_count + 1}/{self.backoff.max_retries})")

        if self.reconnect_timer:
            self.reconnect_timer.cancel()

        self.reconnect_timer = threading.Timer(delay, self._reconnect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

        self.backoff.increment()

    def _reconnect(self):
        """재연결 수행"""
        logger.info(f"Attempting to reconnect {self.config.name}")
        self.status = StreamStatus.RECONNECTING

        # 기존 파이프라인 정리
        if self.gst_pipeline:
            self.gst_pipeline.stop()
            time.sleep(0.5)

        # 재연결 시도
        if self.connect():
            logger.success(f"Reconnected successfully: {self.config.name}")
            self.backoff.reset()
        else:
            # 실패 - 다시 재시도
            self._schedule_reconnect()
```

#### 6.2.2 우선순위 2: 디스크 공간 관리 (필수) ⭐⭐⭐⭐⭐

**위치:** `core/storage.py` - `StorageService` 클래스

**현재 코드:**
```python
# core/storage.py
class StorageService:
    def auto_cleanup(self, camera_id: Optional[str] = None):
        # 오래된 파일 삭제만 있음
        self.cleanup_old_recordings(max_age_days, camera_id)
```

**개선안:**
```python
# core/storage.py
class StorageService:
    def __init__(self):
        # ...
        self.monitoring = False

    def start_monitoring(self, interval=600):
        """주기적 디스크 모니터링 시작 (10분)"""
        self.monitoring = True

        def monitor_loop():
            while self.monitoring:
                try:
                    self.check_and_cleanup()
                except Exception as e:
                    logger.error(f"Disk monitoring error: {e}")
                time.sleep(interval)

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("Disk space monitoring started")

    def check_and_cleanup(self):
        """디스크 체크 및 정리"""
        free_gb = self.get_free_space_gb()
        free_percent = self.get_free_space_percent()

        logger.debug(f"Disk space: {free_gb:.2f}GB ({free_percent:.1f}%)")

        # 임계값 체크
        if free_gb < self.min_free_gb or free_percent < 5:
            logger.warning(f"Low disk space: {free_gb:.2f}GB")
            self.auto_cleanup()

    def auto_cleanup(self, camera_id: Optional[str] = None):
        """자동 정리 (개선)"""
        # 1. 오래된 파일 삭제
        deleted = self.cleanup_old_recordings(self.max_age_days, camera_id)
        logger.info(f"Deleted {deleted} old files")

        # 2. 여전히 부족하면 가장 오래된 파일부터 삭제
        if self.get_free_space_gb() < self.min_free_gb:
            deleted = self.cleanup_until_space_available(camera_id)
            logger.info(f"Deleted {deleted} additional files")

    def cleanup_until_space_available(self, camera_id: Optional[str] = None):
        """공간 확보 시까지 삭제"""
        deleted = 0
        files = self._get_oldest_files(camera_id)

        for file_path in files:
            if self.get_free_space_gb() >= self.min_free_gb:
                break

            try:
                file_path.unlink()
                deleted += 1
                logger.debug(f"Deleted: {file_path.name}")
            except Exception as e:
                logger.error(f"Delete failed: {e}")

        return deleted
```

**메인 코드에서 시작:**
```python
# main.py
storage_service = StorageService()
storage_service.start_monitoring(interval=600)  # 10분마다
```

#### 6.2.3 우선순위 3: 버스 메시지 처리 개선 (권장) ⭐⭐⭐⭐

**위치:** `camera/gst_pipeline.py` - `_on_bus_message()` 메서드

**개선안:**
```python
# camera/gst_pipeline.py
def _on_bus_message(self, bus, message):
    """버스 메시지 처리 (개선)"""
    t = message.type

    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        src_name = message.src.get_name() if message.src else "unknown"

        # 에러 도메인 확인
        domain = err.domain
        code = err.code

        logger.error(f"Pipeline error from {src_name}: {err}")
        logger.debug(f"Domain: {domain}, Code: {code}")
        logger.debug(f"Debug info: {debug}")

        # 도메인별 처리
        if domain == "gst-resource-error-quark":
            self._handle_resource_error(src_name, code, err)
        elif domain == "gst-stream-error-quark":
            self._handle_stream_error(src_name, code, err)
        else:
            self._handle_generic_error(src_name, err)

    # ... 기타 메시지 타입

def _handle_resource_error(self, src_name, code, err):
    """리소스 에러 처리"""
    # code 3 = NOT_FOUND
    # code 6 = OPEN_WRITE
    # code 9 = NO_SPACE_LEFT

    if code == 9 or "space" in str(err).lower():
        logger.error("Disk full error detected")
        self._handle_disk_full()

    elif code == 6 or "write" in str(err).lower():
        logger.error("Write error - checking disk space")
        if storage_service.get_free_space_gb() < 1:
            self._handle_disk_full()
        else:
            logger.error("Disk has space - permission issue?")

    elif code == 3 or "not found" in str(err).lower():
        logger.error("Resource not found")

    # 기타 리소스 에러
    else:
        logger.error(f"Resource error: code={code}")

def _handle_disk_full(self):
    """디스크 Full 처리"""
    logger.error("Handling disk full...")

    # 1. 녹화 중지
    if self._is_recording:
        self.stop_recording()

    # 2. 공간 확보 시도
    try:
        storage_service.auto_cleanup()

        # 3. 재시작
        time.sleep(2)
        if storage_service.get_free_space_gb() > 2:
            logger.success(f"Space freed: {storage_service.get_free_space_gb():.2f}GB")
            self.start_recording()
        else:
            logger.error("Still not enough space")
            # UI 알림
            self._notify_recording_state_change(False)

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
```

#### 6.2.4 우선순위 4: BUFFERING 메시지 처리 (권장) ⭐⭐⭐

**추가:**
```python
# camera/gst_pipeline.py
def _on_bus_message(self, bus, message):
    # ...

    elif t == Gst.MessageType.BUFFERING:
        percent = message.parse_buffering()
        logger.debug(f"Buffering: {percent}%")

        # RTSP 스트리밍 시 버퍼링 처리
        if percent < 100:
            # 버퍼링 중 - PAUSED
            self.pipeline.set_state(Gst.State.PAUSED)
        elif self._is_playing:
            # 버퍼링 완료 - PLAYING 재개
            self.pipeline.set_state(Gst.State.PLAYING)
```

### 6.3 구현 우선순위 요약

| 우선순위 | 항목 | 중요도 | 난이도 | 예상 시간 |
|---------|------|--------|--------|----------|
| **1** | RTSP 재연결 + 지수 백오프 | 매우 높음 | 중간 | 4-6시간 |
| **2** | 디스크 공간 관리 | 매우 높음 | 낮음 | 2-3시간 |
| **3** | 버스 메시지 개선 (도메인별) | 높음 | 낮음 | 2시간 |
| **4** | BUFFERING 메시지 처리 | 중간 | 낮음 | 1시간 |
| **5** | USB/HDD 분리 감지 | 중간 | 중간 | 3-4시간 |
| **6** | Watchdog 타이머 | 낮음 | 중간 | 2-3시간 |

**총 예상 작업 시간:** 14-19시간

---

## 7. 참고 자료

### 7.1 오픈소스 프로젝트
- [GStreamer 공식 예제](https://github.com/GStreamer/gst-python)
- [tylercubell - Automatic Restart](https://gist.github.com/tylercubell/14cf51a40c517e12c102c8f77831ee80)
- [acschristoph - RTSP Player](https://github.com/acschristoph/python_gst_rtsp_player)
- [uutzinger - Camera](https://github.com/uutzinger/camera)

### 7.2 기술 문서
- [GStreamer Fallback Plugins](https://coaxion.net/blog/2020/07/automatic-retry-on-error-and-fallback-stream-handling-for-gstreamer-sources/)
- [GStreamer Discourse - RTSP Reconnection](https://discourse.gstreamer.org/t/rtsp-disconnect-and-reconnect-on-error-during-play/395)
- [Stack Overflow - Pipeline Restart](https://stackoverflow.com/questions/40965143/restarting-gstreamer-pipeline-in-python-on-eos)

### 7.3 Python 라이브러리
- [litl/backoff](https://github.com/litl/backoff) - Exponential Backoff 라이브러리
- [pyudev](https://pyudev.readthedocs.io/) - Linux 장치 모니터링
- [pywin32](https://github.com/mhammond/pywin32) - Windows API

---

**문서 버전:** 1.0
**작성일:** 2025-10-30
**대상 프로젝트:** nvr_gstreamer
**참고:** GStreamer 1.0, Python 3.8+
