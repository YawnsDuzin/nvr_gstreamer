# 카메라 연결 끊김 에러 처리 분석

> 작성일: 2025-11-03
> 분석 대상: `camera/gst_pipeline.py` 에러 처리 로직

---

## 1. 에러 발생 시퀀스

### 1.1 RTSP 네트워크 에러 감지

```
10:53:29 | ERROR | Pipeline error from source: gst-resource-error-quark: Could not read from resource. (9)
         ↓
         에러 분류: ErrorType.RTSP_NETWORK
         ↓
         _handle_rtsp_error() 호출
```

**감지된 에러:**
- **소스**: `source` (rtspsrc 엘리먼트)
- **에러 코드**: `9` (GST_RESOURCE_ERROR_READ)
- **원인**: RTSP 네트워크 연결 끊김
- **GStreamer 내부**: `gstrtspsrc.c:6396 (gst_rtspsrc_loop_interleaved)`

### 1.2 후속 에러 연쇄 반응

네트워크 끊김 후 GStreamer 파이프라인에서 연쇄적으로 발생하는 에러들:

1. **Internal data stream error (10:53:29)**
   ```
   gst-stream-error-quark: Internal data stream error. (1)
   gstrtspsrc.c(6899): streaming stopped, reason error (-5)
   ```

2. **Could not write to resource (10:53:30)**
   ```
   gst-resource-error-quark: Could not write to resource. (10)
   gstrtspsrc_pause(): Could not send message. (Received end-of-file)
   ```

3. **Could not read from resource - 재발 (10:53:30)**
   ```
   gst-resource-error-quark: Could not read from resource. (9)
   ```

4. **Connection timeout (10:53:57 - 재연결 시도 실패)**
   ```
   gst-resource-error-quark: Could not open resource for reading and writing. (7)
   Failed to connect. (Timeout while waiting for server response)
   ```

---

## 2. 현재 에러 처리 흐름

### 2.1 에러 분류 시스템 ([gst_pipeline.py:670-702](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L670-L702))

```python
def _classify_error(self, src_name, err, debug, error_code):
    """에러 타입 분류"""
    # RTSP 네트워크 에러 (✅ 정상 감지)
    if (src_name == "source" and error_code == 9 and "could not read" in error_str):
        return ErrorType.RTSP_NETWORK

    # 저장소 분리 (✅ 감지)
    if (src_name in ["splitmuxsink", "sink"] and error_code == 10 and ...):
        return ErrorType.STORAGE_DISCONNECTED

    # 디스크 Full (✅ 감지)
    if ("space" in error_str or "no space" in error_str):
        return ErrorType.DISK_FULL

    # 디코더 에러 (✅ 감지)
    if "dec" in src_name and "decode" in error_str:
        return ErrorType.DECODER

    # Video sink 에러 (✅ 감지)
    if "videosink" in src_name or "output window" in error_str:
        return ErrorType.VIDEO_SINK

    # ❌ 알 수 없는 에러 → 버그 발생!
    return ErrorType.UNKNOWN
```

**문제점:**
- `Internal data stream error` (error_code=1)
- `Could not write to resource` (error_code=10, src_name="source")
- `Could not open resource` (error_code=7)

위 에러들이 **ErrorType.UNKNOWN**으로 분류되어 `_handle_unknown_error()` 호출 시도 → **메서드 누락으로 AttributeError 발생**

### 2.2 에러 핸들러 호출 ([gst_pipeline.py:635-653](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L635-L653))

```python
# 에러 타입별 처리
if error_type == ErrorType.RTSP_NETWORK:
    self._handle_rtsp_error(err)         # ✅ 구현됨
elif error_type == ErrorType.STORAGE_DISCONNECTED:
    self._handle_storage_error(err)      # ✅ 구현됨
elif error_type == ErrorType.DISK_FULL:
    self._handle_disk_full_error(err)    # ✅ 구현됨
elif error_type == ErrorType.DECODER:
    self._handle_decoder_error(err)      # ✅ 구현됨
elif error_type == ErrorType.VIDEO_SINK:
    self._handle_videosink_error(err)    # ✅ 구현됨
else:
    self._handle_unknown_error(src_name, err)  # ❌ 메서드 없음!
```

---

## 3. RTSP 에러 처리 상세

### 3.1 수정된 에러 처리 ([gst_pipeline.py:704-708](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L704-L708))

```python
def _handle_rtsp_error(self, err):
    """RTSP 에러 처리 - 전체 재시작"""
    logger.critical(f"[RTSP] Network error: {err}")

    # ✅ 수정됨: GLib 스레드 join 문제 해결
    # 별도 스레드로 비동기 정지 처리
    threading.Thread(target=self._async_stop_and_reconnect, daemon=True).start()

def _async_stop_and_reconnect(self):
    """비동기로 파이프라인 정지 및 재연결"""
    self.stop()
    self._schedule_reconnect()
```

**처리 순서:**
1. RTSP 네트워크 에러 감지
2. 별도 스레드에서 `stop()` 호출 → 파이프라인 정지
3. `_schedule_reconnect()` → 재연결 스케줄링

### 3.2 파이프라인 정지 ([gst_pipeline.py:920-948](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L920-L948))

```python
def stop(self):
    """파이프라인 정지"""
    logger.info(f"Stopping pipeline for {self.camera_name}")

    # 1. 타임스탬프 업데이트 타이머 정지 ✅
    self._stop_timestamp_update()

    # 2. 녹화 중이면 먼저 정지 ✅
    if self._is_recording:
        self.stop_recording()

    # 3. 파이프라인 NULL 상태로 전환 ✅
    self.pipeline.set_state(Gst.State.NULL)
    self._is_playing = False

    # 4. 메인 루프 종료 ✅
    if self._main_loop:
        self._main_loop.quit()

    # 5. 스레드 종료 대기 (✅ 이제 안전함 - 비동기 처리)
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=2.0)
```

**녹화 정지 처리 ([gst_pipeline.py:1017-1058](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L1017-L1058))**
```
1. recording_valve 닫기 (drop=True)
   ✅ 10:53:29 | [RECORDING DEBUG] Recording valve closed

2. splitmuxsink에 split-now 신호 전송
   ✅ 10:53:29 | [RECORDING DEBUG] Emitted split-now signal

3. 파일 저장 완료
   ✅ 10:53:30 | Recording stopped: E:/_recordings/cam_01/20251103/cam_01_20251103_105241.mkv

4. UI 동기화 콜백 호출
   ✅ 10:53:30 | [RECORDING SYNC] Notifying recording state change: cam_01 -> False
   ✅ 10:53:30 | [UI SYNC] Recording state callback: cam_01 -> False
   ✅ 10:53:30 | [UI SYNC] Updated Grid View for cam_01: recording=False
```

### 3.3 재연결 스케줄링 ([gst_pipeline.py:776-792](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L776-L792))

```python
def _schedule_reconnect(self):
    """재연결 스케줄링 (지수 백오프)"""
    if self.retry_count >= self.max_retries:
        logger.error(f"Max retries ({self.max_retries}) reached")
        return

    # 지수 백오프: 5초 → 10초 → 20초 → 40초 → 최대 60초
    delay = min(5 * (2 ** self.retry_count), 60)
    self.retry_count += 1

    logger.info(f"Reconnecting in {delay}s (attempt {self.retry_count}/{self.max_retries})")

    # 타이머로 재연결 스케줄
    self.reconnect_timer = threading.Timer(delay, self._reconnect)
    self.reconnect_timer.start()
```

**로그 분석:**
```
10:53:30 | Reconnecting in 5s (attempt 1/10)   ← 첫 번째 시도
10:53:30 | Reconnecting in 10s (attempt 2/10)  ← 두 번째 시도 (중복 호출 의심)
10:53:40 | Attempting to reconnect...          ← 10초 후 재연결 (2번째 스케줄)
```

**의심되는 문제:**
- `_schedule_reconnect()`가 **두 번 호출**됨
- 원인: 에러가 연쇄적으로 발생하면서 여러 번 `_handle_rtsp_error()` 호출

---

## 4. 주요 문제점

### 4.1 ❌ 치명적 버그: `_handle_unknown_error` 메서드 누락

**에러 메시지:**
```python
AttributeError: 'GstPipeline' object has no attribute '_handle_unknown_error'.
Did you mean: '_handle_decoder_error'?
```

**발생 원인:**
- 코드 653라인에서 `self._handle_unknown_error(src_name, err)` 호출
- 메서드가 구현되지 않음

**영향:**
- 알 수 없는 에러 발생 시 예외로 인해 에러 처리 중단
- 에러 로그만 남고 복구 시도 없음

### 4.2 ⚠️ 에러 분류 미흡

**현재 UNKNOWN으로 분류되는 중요 에러들:**

1. **Internal data stream error** (error_code=1)
   - RTSP 스트리밍 중단 에러
   - 원인: 네트워크 끊김 후속 에러
   - **처리 필요**: RTSP_NETWORK와 동일하게 처리해야 함

2. **Could not write to resource** (error_code=10, src_name="source")
   - RTSP 소스가 서버에 메시지 전송 실패
   - 원인: 연결 종료 후 PAUSE 시도
   - **처리 필요**: RTSP_NETWORK와 동일하게 처리 (무시 가능)

3. **Could not open resource** (error_code=7)
   - 재연결 시 타임아웃
   - 원인: 서버 응답 없음 (Timeout while waiting for server response)
   - **처리 필요**: RTSP_NETWORK와 동일하게 처리

### 4.3 ⚠️ 중복 재연결 스케줄링

**문제:**
```
10:53:30 | Reconnecting in 5s (attempt 1/10)
10:53:30 | Reconnecting in 10s (attempt 2/10)  ← 같은 시간에 중복 호출
```

**원인:**
- 에러가 연쇄적으로 발생 (3개의 에러 거의 동시 발생)
- 각 에러마다 `_handle_rtsp_error()` → `_schedule_reconnect()` 호출

**영향:**
- 여러 개의 재연결 타이머가 동시에 실행
- retry_count가 비정상적으로 증가
- 불필요한 재연결 시도 중복

### 4.4 ⚠️ Qt 메타타입 경고

**경고 메시지:**
```
QObject::connect: Cannot queue arguments of type 'QVector<int>'
(Make sure 'QVector<int>' is registered using qRegisterMetaType().)
```

**원인:**
- PyQt5 시그널/슬롯에서 `QVector<int>` 타입 미등록
- 스레드 간 시그널 전달 시 발생

**영향:**
- UI 업데이트 지연 가능성
- 심각하지 않음 (경고 수준)

---

## 5. 정상 동작하는 부분

### ✅ 에러 감지 및 분류
- RTSP 네트워크 에러 정확히 감지
- `_classify_error()`에서 에러 타입별 분류

### ✅ 녹화 정지 처리
1. Valve 닫기 (recording_valve.drop = True)
2. splitmuxsink에 split-now 신호 전송
3. 파일 저장 완료 확인
4. UI 동기화 콜백 완료
   - Grid View 업데이트
   - Recording Control Widget 업데이트

### ✅ 재연결 시도
- 지수 백오프로 재연결 스케줄
- 타이머 기반 비동기 재연결
- 10초 후 재연결 시도 확인

### ✅ 스레드 join 문제 해결
- GLib 스레드에서 직접 `stop()` 호출하지 않음
- 별도 스레드로 비동기 정지 처리

---

## 6. 해결 방안

### 6.1 우선순위 높음: `_handle_unknown_error` 메서드 구현

```python
def _handle_unknown_error(self, src_name, err):
    """알 수 없는 에러 처리"""
    logger.warning(f"[UNKNOWN] Unhandled error from {src_name}: {err}")

    # RTSP 소스 관련 에러면 재연결 시도
    if src_name == "source":
        logger.info("[UNKNOWN] Source error detected, attempting reconnection")
        threading.Thread(target=self._async_stop_and_reconnect, daemon=True).start()
    else:
        # 다른 소스 에러는 로그만 남기고 무시
        logger.debug(f"[UNKNOWN] Non-critical error from {src_name}, ignoring")
```

### 6.2 우선순위 높음: 에러 분류 개선

```python
def _classify_error(self, src_name, err, debug, error_code):
    """에러 타입 분류 (개선)"""
    error_str = str(err).lower()
    debug_str = str(debug).lower() if debug else ""

    # RTSP 네트워크 에러 (확장)
    if src_name == "source":
        # error_code 9: Could not read
        # error_code 10: Could not write (파이프라인 정지 중)
        # error_code 7: Could not open (재연결 타임아웃)
        # error_code 1: Internal data stream error
        if error_code in [1, 7, 9, 10]:
            return ErrorType.RTSP_NETWORK

    # ... 나머지 분류 로직
```

### 6.3 우선순위 중간: 중복 재연결 방지

```python
def _schedule_reconnect(self):
    """재연결 스케줄링 (중복 방지)"""
    # 이미 재연결 타이머가 실행 중이면 무시
    if self.reconnect_timer and self.reconnect_timer.is_alive():
        logger.debug("Reconnect already scheduled, skipping duplicate")
        return

    if self.retry_count >= self.max_retries:
        logger.error(f"Max retries ({self.max_retries}) reached")
        return

    # ... 나머지 로직
```

### 6.4 우선순위 낮음: Qt 메타타입 등록

```python
# main.py 또는 ui/__init__.py에 추가
from PyQt5.QtCore import qRegisterMetaType, QVector

# 애플리케이션 초기화 시 등록
qRegisterMetaType("QVector<int>")
```

---

## 7. 결론

### 현재 상태 요약

| 구분 | 상태 | 비고 |
|------|------|------|
| 에러 감지 | ✅ 정상 | RTSP 네트워크 에러 정확히 감지 |
| 에러 분류 | ⚠️ 부분 정상 | 일부 에러가 UNKNOWN으로 분류 |
| 에러 핸들러 | ❌ 버그 | `_handle_unknown_error` 누락 |
| 녹화 정지 | ✅ 정상 | Valve 닫기, 파일 저장, UI 동기화 완료 |
| 재연결 시도 | ⚠️ 부분 정상 | 중복 스케줄링 발생 |
| 스레드 처리 | ✅ 수정됨 | 비동기 정지 처리로 join 문제 해결 |

### 즉시 수정 필요

1. **`_handle_unknown_error` 메서드 구현** (치명적 버그)
2. **에러 분류 로직 개선** (안정성 향상)
3. **중복 재연결 방지** (리소스 낭비 방지)

---

## 참고 자료

- GStreamer RTSP 소스 에러 코드: [GstResourceError](https://gstreamer.freedesktop.org/documentation/gstreamer/gsterror.html)
- 파이프라인 에러 처리: [camera/gst_pipeline.py:617-760](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L617-L760)
- 재연결 로직: [camera/gst_pipeline.py:776-792](d:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer\camera\gst_pipeline.py#L776-L792)
