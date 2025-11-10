# STORAGE_DISCONNECTED 에러 처리 로직 분석 및 개선

**작성일:** 2025-11-10
**대상 파일:** `camera/gst_pipeline.py`
**목적:** USB/외부 저장소 분리 감지 및 처리 로직 분석

---

## 목차
1. [STORAGE_DISCONNECTED 감지 로직](#1-storage_disconnected-감지-로직)
2. [처리 흐름 분석](#2-처리-흐름-분석)
3. [문제점 및 개선 사항](#3-문제점-및-개선-사항)
4. [테스트 시나리오](#4-테스트-시나리오)

---

## 1. STORAGE_DISCONNECTED 감지 로직

### 1.1 에러 분류 우선순위

`_classify_error()` 메서드는 **3단계 우선순위** 방식을 사용합니다:

```
1순위: GStreamer 에러 도메인 (가장 정확)
   ↓
2순위: 소스 엘리먼트 이름 (sink, splitmuxsink 등)
   ↓
3순위: 에러 메시지 문자열 (fallback)
```

### 1.2 감지 조건

#### 1단계: GStreamer 에러 도메인 (라인 1034-1084)

```python
# ResourceError 도메인 (리소스 접근 관련)
if domain == Gst.ResourceError.quark():
    # 리소스 없음 (USB 분리, 파일 없음)
    if error_code == Gst.ResourceError.NOT_FOUND:
        if src_name != "source":
            return ErrorType.STORAGE_DISCONNECTED

    # 쓰기 실패 (권한, I/O 에러)
    elif error_code == Gst.ResourceError.OPEN_WRITE:
        if src_name != "source":
            return ErrorType.STORAGE_DISCONNECTED

    # 읽기 실패
    elif error_code == Gst.ResourceError.READ:
        if src_name != "source":
            return ErrorType.STORAGE_DISCONNECTED

    # 기타 sink 관련 리소스 에러
    elif src_name.startswith("sink") or "splitmuxsink" in src_name:
        return ErrorType.STORAGE_DISCONNECTED

# CoreError 도메인 (상태 변경 실패)
elif domain == Gst.CoreError.quark():
    if error_code == Gst.CoreError.STATE_CHANGE:
        if src_name.startswith("sink") or "splitmuxsink" in src_name:
            return ErrorType.STORAGE_DISCONNECTED
```

**커버하는 에러 타입:**
- ✅ ResourceError.NOT_FOUND: USB 마운트 해제
- ✅ ResourceError.OPEN_WRITE: 파일 쓰기 실패
- ✅ ResourceError.READ: 파일 읽기 실패
- ✅ CoreError.STATE_CHANGE: sink 상태 변경 실패

#### 2단계: 소스 엘리먼트 이름 기반 (라인 1100-1119)

```python
# sink 또는 splitmuxsink 엘리먼트에서 발생한 에러
if src_name.startswith("sink") or "splitmuxsink" in src_name:
    # error_code 10: Could not write
    if (error_code == 10 and
        "could not write" in error_str and
        ("permission denied" in debug_str or
         "file descriptor" in debug_str)):
        return ErrorType.STORAGE_DISCONNECTED

    # error_code 3: No file name specified
    if (error_code == 3 and
        "no file name specified" in error_str and
        "gst_file_sink_open_file" in debug_str):
        return ErrorType.STORAGE_DISCONNECTED

    # error_code 4: State change failed
    if (error_code == 4 and
        "state change failed" in error_str and
        ("failed to start" in debug_str or "gstbasesink.c" in debug_str)):
        return ErrorType.STORAGE_DISCONNECTED
```

**커버하는 상황:**
- ✅ 파일 쓰기 중 권한 에러
- ✅ Bad file descriptor (USB 분리 후)
- ✅ 파일 경로 접근 불가
- ✅ sink 시작 실패

### 1.3 실제 USB 분리 시 발생하는 에러

**시나리오 1: 녹화 중 USB 제거**
```
Pipeline error from splitmuxsink: gst-resource-error-quark:
Could not write to file (10)
Debug info: gstfilesink.c(456): write: Input/output error
→ 감지 여부: ✅ ResourceError.OPEN_WRITE로 감지
```

**시나리오 2: 파일 회전 중 USB 없음**
```
Pipeline error from mp4mux: gst-resource-error-quark:
Could not write to resource (10)
Debug info: Bad file descriptor
→ 감지 여부: ⚠️ src_name이 "mp4mux"인 경우 놓칠 수 있음
```

**시나리오 3: 파일 경로 접근 불가**
```
Pipeline error from splitmuxsink: gst-resource-error-quark:
No such file or directory (3)
Debug info: gst_file_sink_open_file: failed to open file
→ 감지 여부: ✅ NOT_FOUND로 감지
```

### 1.4 감지 로직의 한계

#### ❌ **문제 1: 내부 muxer 에러 미감지**

splitmuxsink는 내부적으로 mp4mux/matroskamux를 사용합니다:

```
splitmuxsink (parent)
  └─ mp4mux (internal)      ← src_name이 "mp4mux"가 될 수 있음
      └─ filesink (internal)
```

**현재 조건:**
```python
if src_name.startswith("sink") or "splitmuxsink" in src_name:
```

**문제:**
- `src_name = "mp4mux"` → "sink"로 시작하지 않음
- `"splitmuxsink" in "mp4mux"` → False
- **결과: UNKNOWN으로 분류됨**

**개선안 (라인 1101 수정):**
```python
if (src_name.startswith("sink") or
    "splitmuxsink" in src_name or
    "mux" in src_name or          # ✅ mp4mux, matroskamux 감지
    "filesink" in src_name):       # ✅ 내부 filesink 감지
```

#### ❌ **문제 2: format-location 핸들러 예외 미처리**

`_on_format_location()` 메서드 (라인 1749-1760):

```python
def _on_format_location(self, splitmux, fragment_id):
    """파일 경로 생성 (splitmuxsink의 format-location 신호 핸들러)"""
    date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
    date_dir.mkdir(exist_ok=True)  # ❌ 예외 처리 없음
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")

    logger.info(f"[RECORDING DEBUG] Creating recording file: {file_path}")
    return file_path
```

**문제:**
- USB 분리 직후 파일 회전이 발생하면 `mkdir()` 실패
- Python 예외는 **GStreamer 버스로 전파되지 않음**
- 결과: 조용히 실패하고 녹화 중지되지만 알림 없음

**실제 발생 시나리오:**
```
1. 녹화 중 (파일: video_001.mp4)
2. USB 제거
3. 10분 경과 → splitmuxsink가 파일 회전 시도
4. format-location 신호 발생 → _on_format_location() 호출
5. date_dir.mkdir() 실패 → OSError 발생
6. ❌ 예외가 잡히지 않고 조용히 실패
7. 녹화 계속되는 것처럼 보이지만 실제로는 중지됨
```

**개선안 (라인 1749 수정):**
```python
def _on_format_location(self, splitmux, fragment_id):
    """파일 경로 생성 (splitmuxsink의 format-location 신호 핸들러)"""
    try:
        date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")

        logger.info(f"[RECORDING DEBUG] Creating recording file: {file_path}")
        return file_path

    except (OSError, PermissionError, FileNotFoundError) as e:
        logger.error(f"[STORAGE] USB disconnected during file rotation: {e}")

        # GLib 메인 루프에서 에러 핸들러 호출
        from gi.repository import GLib
        GLib.idle_add(self._handle_storage_error_from_callback, str(e))

        # 임시 경로 반환 (크래시 방지)
        return "/tmp/fallback.mp4"

def _handle_storage_error_from_callback(self, err_msg):
    """GLib 메인 루프에서 호출되는 storage 에러 핸들러"""
    self._handle_storage_error(Exception(err_msg))
    return False  # GLib.idle_add는 False 반환 시 1회만 실행
```

---

## 2. 처리 흐름 분석

### 2.1 전체 처리 흐름

```
[USB 분리 발생]
      ↓
[GStreamer 에러 발생]
      ↓
[버스 메시지 수신] (_on_bus_message)
      ↓
[에러 분류] (_classify_error)
      ↓
ErrorType.STORAGE_DISCONNECTED
      ↓
[_handle_storage_error 호출]
      ↓
┌─────────────────────────────┐
│ 1. stop_recording(storage_error=True) │
│    - split 신호 건너뜀      │
│    - recording_valve 닫기    │
│    - 상태 플래그 업데이트    │
├─────────────────────────────┤
│ 2. 플래그 설정              │
│    - _recording_branch_error = True │
│    - _recording_should_auto_resume = True │
├─────────────────────────────┤
│ 3. 재시도 스케줄링          │
│    - _schedule_recording_retry() │
│    - 6초마다, 최대 20회      │
└─────────────────────────────┘
      ↓
[재시도 루프] (_retry_recording)
      ↓
[USB 재연결 확인] (_validate_recording_path)
  - USB 마운트 확인
  - 권한 확인
  - 공간 확인
  - 파일 생성 테스트
      ↓
   성공? ──No──> 6초 후 재시도
      │
     Yes
      ↓
[녹화 재시작] (start_recording)
      ↓
✅ 자동 복구 완료
```

### 2.2 stop_recording(storage_error=True) 동작

**일반 중지 vs 저장소 에러 중지 비교:**

| 항목 | storage_error=False | storage_error=True |
|------|---------------------|---------------------|
| split-after 신호 | ✅ 발생 (파일 finalize) | ❌ 건너뜀 |
| recording_valve | ✅ 닫기 | ✅ 닫기 |
| 재시도 취소 | ✅ 취소 | ❌ 유지 |
| 자동 재개 플래그 | ❌ False | ✅ True (유지) |
| 마지막 파일 상태 | ✅ 정상 (moov atom) | ❌ 손상 가능 |

**storage_error=True 사용 이유:**
- USB가 이미 분리되어 파일 finalization 불가능
- split 신호 발생 시 에러만 추가로 발생
- 빠른 정리 및 재시도 시작

### 2.3 Recording Branch 격리

**중요**: 저장소 에러는 **Recording Branch에만 영향**을 줍니다.

**파이프라인 구조:**
```
RTSP Source → Decode → Tee ──┬──> Streaming Branch → Video Sink
                             │    (streaming_valve)
                             │    ✅ 계속 동작
                             │
                             └──> Recording Branch → splitmuxsink
                                  (recording_valve)
                                  ❌ 중지됨
```

**증거 (라인 1098-1099):**
```python
logger.info("[STREAMING] Streaming continues")
logger.info("[RECORDING] Will automatically resume when storage is available")
```

✅ **스트리밍은 영향 없이 계속 동작합니다.**

### 2.4 자동 복구 메커니즘

**재시도 파라미터:**
- **간격**: 6초 고정 (`_recording_retry_interval = 6.0`)
- **최대 횟수**: 20회 (`_max_recording_retry = 20`)
- **총 시간**: 약 2분 (6초 × 20회)

**_validate_recording_path() 5단계 검증:**

```python
# 1. USB 마운트 상태 확인
if recording_path_str.startswith('/media/'):
    mount_point = Path(*path_parts[:4])
    if not mount_point.exists():
        return False
    if not os.path.ismount(str(mount_point)):
        return False

# 2. 상위 디렉토리 존재 확인
if not parent_dir.exists():
    return False

# 3. 디렉토리 생성 시도
try:
    self.recording_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    return False

# 4. 접근 권한 확인 (R/W/X)
if not os.access(str(self.recording_dir), os.R_OK | os.W_OK | os.X_OK):
    return False

# 5. 디스크 공간 확인 (최소 1GB)
stat = os.statvfs(str(self.recording_dir))
free_gb = stat.f_bavail * stat.f_frsize / (1024**3)
if free_gb < 1.0:
    return False

# 6. 파일 생성 테스트
test_file = self.recording_dir / f".test_{self.camera_id}.tmp"
test_file.touch()
test_file.unlink()
```

✅ **매우 견고한 검증 로직**

---

## 3. 문제점 및 개선 사항

### 3.1 Critical Issues (즉시 개선 필요)

#### Issue #1: format-location 예외 미처리 ⚠️ (2025-11-10 수정됨)

**문제:**
- USB 분리 직후 파일 회전 시 Python 예외 발생
- GStreamer 버스로 전파되지 않아 감지 불가
- 조용히 실패하여 사용자 인지 불가

**실제 발생 로그 (2025-11-10):**
```
2025-11-10 13:47:24 | ERROR    | camera.gst_pipeline:_on_format_location:1823 | [STORAGE] USB disconnected during file rotation: [Errno 2] 그런 파일이나 디렉터리가 없습니다: '/media/itlog/NVR_MAIN/Recordings/cam_01/20251110'
2025-11-10 13:47:24 | CRITICAL | camera.gst_pipeline:_handle_storage_error:1202 | [STORAGE] USB disconnected: [Errno 2] 그런 파일이나 디렉터리가 없습니다: '/media/itlog/NVR_MAIN/Recordings/cam_01/20251110'
```

**영향:**
- 녹화가 중지되지만 UI에는 계속 녹화 중으로 표시
- 재시도 메커니즘이 시작되지 않음

**해결 방법:** ✅ 구현 완료 (라인 1823)
```python
def _on_format_location(self, splitmux, fragment_id):
    try:
        # 기존 로직
        date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True)
        # ...
        return file_path

    except (OSError, PermissionError, FileNotFoundError) as e:
        logger.error(f"[STORAGE] USB disconnected during file rotation: {e}")
        from gi.repository import GLib
        GLib.idle_add(self._handle_storage_error_from_callback, str(e))
        return "/tmp/fallback.mp4"

def _handle_storage_error_from_callback(self, err_msg):
    self._handle_storage_error(Exception(err_msg))
    return False
```

#### Issue #2: 내부 muxer 에러 미감지 ⚠️

**문제:**
- splitmuxsink 내부의 mp4mux/matroskamux 에러를 놓칠 수 있음
- `src_name = "mp4mux"`인 경우 UNKNOWN으로 분류

**영향:**
- USB 분리를 감지하지 못하고 재시도 시작 안 됨
- 에러 로그만 출력되고 복구 시도 없음

**해결 방법:**
```python
# _classify_error() 메서드 수정
if (src_name.startswith("sink") or
    "splitmuxsink" in src_name or
    "mux" in src_name or          # ✅ 추가
    "filesink" in src_name):       # ✅ 추가
    # ... 저장소 에러 분류 로직
```

#### Issue #3: UI 위젯 PermissionError 미처리 🆕 CRITICAL (2025-11-10 발생)

**문제:**
- USB 재연결 시 `/media/itlog/NVR_MAIN/Recordings` 경로의 권한이 변경됨
- `recording_control_widget.py`의 `_update_disk_usage()` 함수가 주기적으로 디스크 사용량을 확인
- `Path.exists()` 호출 시 `PermissionError` 발생하여 **프로그램 크래시**

**실제 발생 로그 (2025-11-10):**
```
2025-11-10 13:47:42 | DEBUG    | camera.gst_pipeline:_retry_recording:1444 | [RECORDING RETRY] Storage path still unavailable (retry 3/20)
Traceback (most recent call last):
  File "/media/itlog/NVR_MAIN/nvr_gstreamer/ui/recording_control_widget.py", line 468, in _update_disk_usage
  File "/usr/lib/python3.9/pathlib.py", line 1407, in exists
    self.stat()
  File "/usr/lib/python3.9/pathlib.py", line 1221, in stat
    return self._accessor.stat(self)
PermissionError: [Errno 13] 허가 거부: '/media/itlog/NVR_MAIN/Recordings'
```

**영향:**
- **프로그램 종료** (처리되지 않은 예외)
- USB 재연결 시 자동 복구 메커니즘이 작동하지 못함
- 사용자 경험 저하

**근본 원인:**
1. USB 재연결 시 마운트 포인트의 소유권/권한이 변경될 수 있음
2. `_update_disk_usage()`는 타이머로 주기적으로 호출되어 계속 시도
3. 예외 처리가 없어 첫 번째 PermissionError에서 프로그램 종료

**해결 방법:** ✅ 구현 완료 (recording_control_widget.py 라인 464-503)
```python
def _update_disk_usage(self):
    """디스크 사용량 업데이트 (타이머에서 호출)"""
    from pathlib import Path
    import os

    try:
        # 설정에서 녹화 디렉토리 가져오기
        config_manager = ConfigManager.get_instance()
        storage_config = config_manager.config.get('storage', {})
        recordings_path = storage_config.get('recording_path', './recordings')
        recordings_dir = Path(recordings_path)

        # USB 마운트 포인트 확인
        if recordings_path.startswith('/media/'):
            # USB 마운트 포인트 추출 (예: /media/itlog/NVR_MAIN)
            path_parts = recordings_path.split('/')
            if len(path_parts) >= 4:
                mount_point = '/' + '/'.join(path_parts[1:4])
                if not os.path.exists(mount_point):
                    self.disk_label.setText("⚠ Storage: USB Disconnected")
                    return

        if recordings_dir.exists():
            # 권한 확인을 위해 먼저 접근 테스트
            if not os.access(recordings_path, os.R_OK):
                self.disk_label.setText("⚠ Storage: Permission Denied")
                return

            total_size = sum(f.stat().st_size for f in recordings_dir.rglob("*.*") if f.is_file())
            file_count = len(list(recordings_dir.rglob("*.*")))
            disk_text = f"Disk Usage: {total_size / (1024*1024):.1f} MB ({file_count} files)"
        else:
            disk_text = "⚠ Storage: Directory Not Found"

        self.disk_label.setText(disk_text)

    except PermissionError as e:
        logger.warning(f"[STORAGE] Permission denied while checking disk usage: {e}")
        self.disk_label.setText("⚠ Storage: Permission Denied")
    except OSError as e:
        logger.warning(f"[STORAGE] OS error while checking disk usage: {e}")
        self.disk_label.setText("⚠ Storage: Not Available")
    except Exception as e:
        logger.error(f"[STORAGE] Unexpected error while checking disk usage: {e}")
        self.disk_label.setText("⚠ Storage: Error")
```

**추가 개선 (gst_pipeline.py 라인 1889-1898):**
- 마운트 포인트 권한 확인 로직 추가
- USB 재연결 시 권한 문제 사전 감지

```python
# 마운트 포인트 접근 권한 확인 (USB 재연결 시 권한 문제 방지)
try:
    if not os.access(str(mount_point), os.R_OK | os.X_OK):
        logger.error(f"[STORAGE] No read permission for mount point: {mount_point}")
        logger.error(f"[STORAGE] USB may have permission issues after reconnection")
        return False
except PermissionError as e:
    logger.error(f"[STORAGE] Permission denied accessing mount point: {e}")
    logger.error(f"[STORAGE] USB may have permission issues after reconnection")
    return False
```

**테스트 시나리오:**
1. USB 연결 상태에서 프로그램 시작
2. USB 제거 (umount)
3. USB 다른 권한으로 재마운트 (`sudo mount -o uid=root,gid=root ...`)
4. 예상: UI에 "⚠ Storage: Permission Denied" 표시, 프로그램 계속 실행
5. USB를 올바른 권한으로 재마운트 후 자동 복구 확인

### 3.2 High Priority Issues (다음 버전 개선)

#### Issue #4: 손상된 파일 정리 부재

**문제:**
- USB 분리 시 마지막 파일이 손상됨 (moov atom 없음)
- USB 재연결 시 손상된 파일이 그대로 남아있음

**해결 방법:**
```python
def _retry_recording(self):
    if self._validate_recording_path():
        # USB 재연결 시 손상된 파일 정리
        if hasattr(self, '_last_corrupted_file') and self._last_corrupted_file:
            self._cleanup_corrupted_file(self._last_corrupted_file)
            self._last_corrupted_file = None

        if self.start_recording():
            # 성공
            pass

def _cleanup_corrupted_file(self, file_path):
    """손상된 파일 정리 (0바이트 파일만 삭제)"""
    try:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                os.remove(file_path)
                logger.info(f"[STORAGE] Removed empty file: {file_path}")
            else:
                logger.info(f"[STORAGE] Keeping partial file: {file_path} ({file_size} bytes)")
    except Exception as e:
        logger.warning(f"[STORAGE] Failed to cleanup file: {e}")
```

#### Issue #5: 고정 재시도 간격

**문제:**
- 6초 고정 간격으로 20회 재시도
- 초기에는 너무 느리고, 후반에는 너무 빠름
- CPU 자원 낭비 가능

**해결 방법 (지수 백오프):**
```python
# 초기화
self._recording_retry_interval_base = 3.0  # 3초
self._recording_retry_interval_max = 30.0  # 최대 30초

def _retry_recording(self):
    # 지수 백오프 계산
    backoff_multiplier = min(2 ** (self._recording_retry_count - 1), 10)
    next_interval = min(
        self._recording_retry_interval_base * backoff_multiplier,
        self._recording_retry_interval_max
    )

    logger.debug(f"[RECORDING RETRY] Next retry in {next_interval:.1f}s")

    # 재시도 간격: 3s → 6s → 12s → 24s → 30s (최대)
```

### 3.3 Medium Priority Issues (선택적 개선)

#### Issue #6: _recording_branch_error 플래그 미사용

**문제:**
- 플래그를 설정하지만 실제로 확인하는 코드가 없음
- 의미 없는 변수

**해결 방법:**
```python
def start_recording(self) -> bool:
    # 에러 상태 확인
    if self._recording_branch_error:
        logger.warning("[RECORDING] Recording branch is in error state")
        self._reset_recording_branch()

    # ... 기존 로직

def _reset_recording_branch(self):
    """Recording Branch 에러 상태 리셋"""
    if self.splitmuxsink:
        self.splitmuxsink.set_state(Gst.State.READY)
        time.sleep(0.1)
        self.splitmuxsink.set_state(Gst.State.PLAYING)
        logger.debug("[RECORDING] Branch reset completed")

    self._recording_branch_error = False
```

#### Issue #7: 재시도 실패 원인 분석 부족

**문제:**
- start_recording() 실패 시 원인을 분석하지 않음
- 디버깅 어려움

**해결 방법:**
```python
def _retry_recording(self):
    if self._validate_recording_path():
        if self.start_recording():
            # 성공
            pass
        else:
            logger.warning("[RECORDING RETRY] Failed to start recording")
            self._analyze_recording_failure()  # ✅ 추가

def _analyze_recording_failure(self):
    """녹화 시작 실패 원인 분석"""
    if not self.pipeline:
        logger.error("[RETRY ANALYSIS] Pipeline not created")
    elif not self.splitmuxsink:
        logger.error("[RETRY ANALYSIS] splitmuxsink not available")
    elif self._recording_branch_error:
        logger.error("[RETRY ANALYSIS] Recording branch in error state")
    else:
        logger.error("[RETRY ANALYSIS] Unknown failure reason")
```

---

## 4. 테스트 시나리오

### 4.1 USB 분리 테스트

#### 시나리오 1: 녹화 중 USB 제거

**절차:**
1. 녹화 시작 (USB 마운트된 상태)
2. 1분 후 USB 제거 (`sudo umount /media/usb`)
3. 로그 확인

**예상 결과:**
```
[STORAGE] USB disconnected: ...
[RECORDING] Stopping recording due to storage error
[STREAMING] Streaming continues
[RECORDING RETRY] Scheduled (interval: 6s, max attempts: 20)
```

**확인 사항:**
- ✅ 스트리밍 계속 동작
- ✅ 녹화만 중지
- ✅ 재시도 스케줄링 시작
- ✅ 마지막 파일 부분 저장됨 (fragment 기반)

#### 시나리오 2: 파일 회전 중 USB 제거

**절차:**
1. 녹화 시작
2. 파일 회전 직전에 USB 제거 (10분 경과 시점)
3. 로그 확인

**예상 결과 (개선 전):**
```
❌ 조용히 실패 (format-location 예외)
```

**예상 결과 (개선 후):**
```
[STORAGE] USB disconnected during file rotation: ...
[STORAGE] USB disconnected: ...
[RECORDING RETRY] Scheduled
```

#### 시나리오 3: USB 재연결

**절차:**
1. 시나리오 1 실행
2. USB 재연결 (동일한 마운트 포인트)
3. 자동 복구 확인

**예상 결과:**
```
[RECORDING RETRY] Storage path available!
[RECORDING] Starting recording
[RECORDING RETRY] Recording resumed successfully!
```

**확인 사항:**
- ✅ 자동으로 녹화 재시작
- ✅ 새 파일 생성 시작
- ✅ 재시도 타이머 중지

### 4.2 엣지 케이스 테스트

#### 테스트 1: 잘못된 마운트 포인트

```bash
# 다른 경로에 USB 마운트
sudo mount /dev/sdb1 /media/usb2  # 원래는 /media/usb1

# 예상: _validate_recording_path() 실패
# 재시도 계속됨
```

#### 테스트 2: 읽기 전용 마운트

```bash
# 읽기 전용으로 마운트
sudo mount -o ro /dev/sdb1 /media/usb

# 예상: 파일 생성 테스트 실패
# STORAGE_DISCONNECTED 감지
```

#### 테스트 3: 디스크 공간 부족

```bash
# 작은 tmpfs 생성
sudo mount -t tmpfs -o size=100M tmpfs /media/test

# 예상: DISK_FULL로 분류 (NOT STORAGE_DISCONNECTED)
```

### 4.3 성능 테스트

#### 테스트 1: 재시도 오버헤드

**측정 항목:**
- CPU 사용률 (재시도 중)
- 메모리 사용량
- 스트리밍 프레임 드롭 여부

**예상:**
- CPU 증가 < 5%
- 메모리 증가 < 10MB
- 스트리밍 영향 없음

#### 테스트 2: 복구 속도

**측정 항목:**
- USB 재연결부터 녹화 재시작까지 시간

**예상:**
- 최소: 6초 (첫 재시도에서 성공)
- 최대: 120초 (20회 재시도 후 포기)

---

## 5. 개선 코드 요약

### 5.1 format-location 예외 처리 (Critical)

```python
def _on_format_location(self, splitmux, fragment_id):
    """파일 경로 생성 - USB 분리 시 예외 처리 추가"""
    try:
        date_dir = self.recording_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = str(date_dir / f"{self.camera_id}_{timestamp}.{self.file_format}")

        logger.info(f"[RECORDING DEBUG] Creating recording file: {file_path}")
        return file_path

    except (OSError, PermissionError, FileNotFoundError) as e:
        logger.error(f"[STORAGE] USB disconnected during file rotation: {e}")

        # GLib 메인 루프에서 에러 핸들러 호출
        from gi.repository import GLib
        GLib.idle_add(self._handle_storage_error_from_callback, str(e))

        # 임시 경로 반환 (크래시 방지)
        return "/tmp/fallback.mp4"

def _handle_storage_error_from_callback(self, err_msg):
    """콜백에서 호출되는 storage 에러 핸들러"""
    self._handle_storage_error(Exception(err_msg))
    return False  # GLib.idle_add는 False 반환 시 1회만 실행
```

### 5.2 내부 muxer 에러 감지 (Critical)

```python
def _classify_error(self, src_name, err, debug, error_code):
    # ... 기존 로직 ...

    # 저장소 관련 sink/muxer 에러 (개선)
    if (src_name.startswith("sink") or
        "splitmuxsink" in src_name or
        "mux" in src_name or          # ✅ mp4mux, matroskamux 감지
        "filesink" in src_name):       # ✅ 내부 filesink 감지

        # ... 저장소 에러 분류 로직
        return ErrorType.STORAGE_DISCONNECTED
```

### 5.3 손상된 파일 정리 (High Priority)

```python
def stop_recording(self, storage_error: bool = False) -> bool:
    # storage_error인 경우 현재 파일 경로 기록
    if storage_error and self.current_recording_file:
        self._last_corrupted_file = self.current_recording_file
        logger.warning(f"[STORAGE] File may be corrupted: {self._last_corrupted_file}")

    # ... 기존 로직

def _retry_recording(self):
    if self._validate_recording_path():
        # USB 재연결 시 손상된 파일 정리
        if hasattr(self, '_last_corrupted_file') and self._last_corrupted_file:
            self._cleanup_corrupted_file(self._last_corrupted_file)
            self._last_corrupted_file = None

        # 녹화 재시작
        if self.start_recording():
            logger.success("[RECORDING RETRY] Recording resumed!")

def _cleanup_corrupted_file(self, file_path):
    """손상된 파일 정리 (0바이트만 삭제)"""
    try:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                os.remove(file_path)
                logger.info(f"[STORAGE] Removed empty file: {file_path}")
            elif file_size < 1024:  # 1KB 미만
                logger.warning(f"[STORAGE] Very small file, likely corrupted: {file_path}")
            else:
                logger.info(f"[STORAGE] Keeping partial file for recovery: {file_path} ({file_size} bytes)")
    except Exception as e:
        logger.warning(f"[STORAGE] Failed to cleanup file: {e}")
```

---

## 6. 결론

### 6.1 현재 구현의 강점

✅ **체계적인 감지 로직**: GStreamer 도메인 기반으로 높은 정확도
✅ **Recording Branch 격리**: 스트리밍에 영향 없이 녹화만 중지
✅ **자동 복구**: USB 재연결 시 자동으로 녹화 재개
✅ **견고한 검증**: 5단계 저장소 경로 검증
✅ **Fragment 기반 MP4**: 부분 파일 손상 최소화

### 6.2 개선 효과

| 문제 | 이전 | 2025-11-10 개선 후 |
|------|------|---------|
| 파일 회전 중 USB 제거 | ❌ 조용히 실패 | ✅ 감지 및 재시도 (Issue #1) |
| UI 위젯 PermissionError | ❌ 프로그램 크래시 | ✅ 예외 처리 및 상태 표시 (Issue #3) |
| USB 재연결 권한 문제 | ⚠️ 감지 안됨 | ✅ 마운트 포인트 권한 확인 |
| 내부 muxer 에러 | ⚠️ UNKNOWN 분류 | 🔜 STORAGE_DISCONNECTED 분류 (Issue #2) |
| 손상된 파일 | ⚠️ 그대로 유지 | 🔜 0바이트 자동 삭제 (Issue #4) |
| 재시도 효율성 | ⚠️ 고정 간격 | 🔜 지수 백오프 (Issue #5, 선택) |

### 6.3 우선순위 요약

**완료됨 (2025-11-10):**
1. ✅ Issue #1: format-location 예외 처리 추가 (gst_pipeline.py)
2. ✅ Issue #3: UI 위젯 PermissionError 처리 (recording_control_widget.py)
3. ✅ USB 재연결 권한 확인 (gst_pipeline.py)

**다음 버전 (High Priority):**
4. Issue #2: 내부 muxer 에러 감지 개선
5. Issue #4: 손상된 파일 정리 로직
6. Issue #5: 지수 백오프 재시도

**선택적 (Medium Priority):**
7. Issue #6: _recording_branch_error 플래그 활용
8. Issue #7: 재시도 실패 원인 분석

---

**작성일:** 2025-11-10
**최종 업데이트:** 2025-11-10 (Issue #1, #3 해결)
**다음 검토 예정일:** Issue #2, #4 개선 완료 후
