# 코드베이스 최적화 분석 (2025-11-13)

코드베이스의 비동기 처리, 메모리 관리, 리소스 관리, 성능 이슈를 분석한 결과입니다.

## 1. 메모리 누수 가능성

### 1.1 GstPipeline 콜백 정리 누락 (높음)
**파일**: `camera/gst_pipeline.py`
**위치**: `stop()` 메서드 (라인 1784-1843)

**이슈**:
- `cleanup_callbacks()` 메서드가 존재하지만 `stop()`에서 호출되지 않음
- 콜백 리스트(`_recording_state_callbacks`, `_connection_state_callbacks`)가 정리되지 않아 메모리 누수 가능
- 재연결 시 중복 콜백 등록 가능

**영향**:
```python
# 현재 코드
def stop(self):
    # ... 파이프라인 정지 로직
    self.pipeline = None  # 객체만 None으로 설정
    # cleanup_callbacks() 호출 없음!
```

**해결 방안**:
```python
def stop(self):
    # ... 기존 정지 로직
    
    # 콜백 정리 추가
    self.cleanup_callbacks()
    
    # 파이프라인 객체 초기화
    self.pipeline = None
```

---

### 1.2 ConfigManager DB 연결 미정리 (중간)
**파일**: `core/config.py`
**위치**: 클래스 전체

**이슈**:
- ConfigManager가 Singleton 패턴을 사용하지만 `db_manager.close()`가 프로그램 종료 시 호출되지 않음
- SQLite 연결이 열린 채로 남아있을 수 있음
- `reset_instance()`에서만 close() 호출됨 (테스트용)

**영향**:
```python
# main.py closeEvent에서 DB 정리 없음
def closeEvent(self, event: QCloseEvent):
    # ... 다른 정리 작업
    # ConfigManager DB 정리 없음!
    event.accept()
```

**해결 방안**:
```python
# main.py closeEvent에 추가
def closeEvent(self, event: QCloseEvent):
    # ... 기존 정리 작업
    
    # ConfigManager DB 정리
    config_manager = ConfigManager.get_instance()
    if hasattr(config_manager, 'db_manager'):
        config_manager.db_manager.close()
        logger.info("Database connection closed")
    
    event.accept()
```

---

### 1.3 GStreamer 파이프라인 명시적 해제 누락 (중간)
**파일**: `camera/playback.py`
**위치**: `PlaybackPipeline.stop()` (라인 268-278)

**이슈**:
- 파이프라인을 NULL 상태로만 설정하고 명시적으로 해제하지 않음
- GStreamer 객체가 Python GC에 의존하여 해제됨 (비확정적)
- 반복적인 재생/정지 시 메모리 누적 가능

**영향**:
```python
def stop(self):
    if self.pipeline:
        self._stop_position_timer()
        self.pipeline.set_state(Gst.State.NULL)
        # 파이프라인 객체 명시적 해제 없음
        self.state = PlaybackState.STOPPED
```

**해결 방안**:
```python
def stop(self):
    if self.pipeline:
        self._stop_position_timer()
        self.pipeline.set_state(Gst.State.NULL)
        
        # 버스 정리
        if self.bus:
            self.bus.remove_signal_watch()
            self.bus = None
        
        # 파이프라인 명시적 해제
        self.pipeline = None
        self.video_sink = None
        
        self.state = PlaybackState.STOPPED
```

---

### 1.4 RecordingScanThread 정리 불완전 (낮음)
**파일**: `ui/playback_widget.py`
**위치**: `_reset_scan_status()` (라인 820-831)

**이슈**:
- `deleteLater()`로 스레드 삭제를 Qt에 맡기지만 스레드가 여전히 실행 중일 수 있음
- `terminate()` 호출 후 `wait()` 없이 바로 다음 스캔 시작 가능
- 스레드 종료를 기다리지 않아 동시 실행 가능

**영향**:
```python
def scan_recordings(self):
    if self.scan_thread and self.scan_thread.isRunning():
        logger.warning("Scan already in progress, trying to stop it")
        self.scan_thread.terminate()  # 강제 종료
        if not self.scan_thread.wait(1000):  # 1초만 대기
            logger.error("Failed to stop previous scan thread")
            return  # 실패 시 return하지만 이미 새 스캔 시작됨
```

**해결 방안**:
```python
def scan_recordings(self):
    # 이전 스캔 완전 종료 대기
    if self.scan_thread and self.scan_thread.isRunning():
        logger.warning("Scan already in progress, waiting to stop")
        self.scan_thread.terminate()
        if not self.scan_thread.wait(3000):  # 3초 대기로 증가
            logger.error("Failed to stop previous scan thread")
            return
        self.scan_thread.deleteLater()
        self.scan_thread = None
    
    # 새 스캔 시작
    # ...
```

---

## 2. 리소스 관리 이슈

### 2.1 BackupWorker/DeleteWorker 스레드 데몬 처리 (중간)
**파일**: `ui/backup_dialog.py`, `ui/delete_dialog.py`
**위치**: `BackupWorker._run_backup()`, `DeleteWorker._run_delete()`

**이슈**:
- 스레드가 `daemon=True`로 설정되어 프로그램 종료 시 강제 종료됨
- 백업/삭제 작업 중간에 종료되면 데이터 손실 가능
- 파일 복사 중 강제 종료 시 불완전한 파일 생성 가능

**영향**:
```python
# backup_dialog.py
self._thread = threading.Thread(target=self._run_backup, daemon=True)
self._thread.start()

# delete_dialog.py
self._thread = threading.Thread(target=self._run_delete, daemon=True)
self._thread.start()
```

**해결 방안**:
```python
# daemon=False로 변경하고 closeEvent에서 안전하게 종료
self._thread = threading.Thread(target=self._run_backup, daemon=False)
self._thread.start()

# closeEvent 개선
def closeEvent(self, event):
    if self.backup_worker and self.backup_worker.is_running():
        reply = QMessageBox.question(...)
        if reply == QMessageBox.Yes:
            self.backup_worker.stop()
            # 스레드 종료 대기
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)  # 5초로 증가
    event.accept()
```

---

### 2.2 SystemMonitorThread 종료 대기 누락 (낮음)
**파일**: `core/system_monitor.py`, `ui/main_window.py`
**위치**: `SystemMonitorThread.stop()`, `MainWindow.closeEvent()`

**이슈**:
- `stop()` 메서드가 `self.running = False` 후 `wait()` 호출하지만
- `main_window.py`의 `closeEvent`에서 `wait()` 완료를 확인하지 않음
- 스레드가 종료되기 전에 프로그램이 종료될 수 있음

**영향**:
```python
# main_window.py closeEvent
if self.monitor_thread:
    self.monitor_thread.stop()  # stop()만 호출, 완료 확인 안 함
```

**해결 방안**:
```python
# main_window.py closeEvent
if self.monitor_thread:
    self.monitor_thread.stop()
    # 종료 완료 대기 (최대 2초)
    if not self.monitor_thread.wait(2000):
        logger.warning("System monitor thread did not stop in time")
```

---

### 2.3 타이머 정리 불완전 (중간)
**파일**: 여러 파일 (`camera/gst_pipeline.py`, `ui/playback_widget.py`)
**위치**: 다양한 타이머 사용 위치

**이슈**:
- GLib.timeout_add로 생성된 타이머가 여러 곳에서 사용됨
- 일부 타이머는 source_remove()로 정리되지만 일부는 누락
- `_timestamp_update_timer`, `_frame_monitor_timer` 등

**영향**:
```python
# gst_pipeline.py
self._timestamp_update_timer = GLib.timeout_add(1000, self._update_timestamp)
# stop()에서 _stop_timestamp_update() 호출로 정리됨 (OK)

# 하지만 예외 발생 시 정리 보장 필요
```

**해결 방안**:
```python
# 타이머 정리를 finally 블록에서 보장
def stop(self):
    try:
        # ... 기존 정지 로직
        self._stop_timestamp_update()
        self._stop_frame_monitor()
        # ...
    except Exception as e:
        logger.error(f"Error during pipeline stop: {e}")
    finally:
        # 타이머 정리 보장
        if self._timestamp_update_timer:
            GLib.source_remove(self._timestamp_update_timer)
            self._timestamp_update_timer = None
        if self._frame_monitor_timer:
            GLib.source_remove(self._frame_monitor_timer)
            self._frame_monitor_timer = None
```

---

## 3. 비동기 처리 이슈

### 3.1 RecordingScanThread 중복 실행 방지 개선 (중간)
**파일**: `ui/playback_widget.py`
**위치**: `scan_recordings()` (라인 766-801)

**이슈**:
- 스캔 중복 실행을 `terminate()`로 강제 종료하여 방지
- 스레드 강제 종료는 안전하지 않음 (리소스 누수 가능)
- 1초 타임아웃은 대용량 스캔 시 불충분

**현재 코드**:
```python
if self.scan_thread and self.scan_thread.isRunning():
    logger.warning("Scan already in progress, trying to stop it")
    self.scan_thread.terminate()  # 위험!
    if not self.scan_thread.wait(1000):
        logger.error("Failed to stop previous scan thread")
        return
```

**해결 방안**:
1. 강제 종료 대신 우아한 종료 구현
2. 스레드에 취소 플래그 추가
3. 타임아웃 증가

```python
# RecordingScanThread에 취소 플래그 추가
class RecordingScanThread(QThread):
    def __init__(self, ...):
        super().__init__()
        self._cancel_requested = False
    
    def cancel(self):
        self._cancel_requested = True
    
    def run(self):
        for file_path in date_dir.iterdir():
            if self._cancel_requested:
                logger.info("Scan cancelled")
                return
            # ... 파일 처리

# playback_widget.py
if self.scan_thread and self.scan_thread.isRunning():
    logger.warning("Scan already in progress, cancelling")
    self.scan_thread.cancel()  # 우아한 취소
    if not self.scan_thread.wait(3000):  # 3초로 증가
        logger.error("Failed to stop previous scan thread")
        return
```

---

### 3.2 BackupDialog 스레드 종료 대기 시간 부족 (낮음)
**파일**: `ui/backup_dialog.py`
**위치**: `BackupWorker.stop()` (라인 62-75)

**이슈**:
- 스레드 종료 대기 시간이 3초로 고정됨
- 대용량 파일 복사 중 3초는 불충분할 수 있음
- 복사 중인 파일이 손상될 수 있음

**현재 코드**:
```python
def stop(self):
    if not self._is_running:
        return
    
    logger.info("Stopping backup...")
    self._stop_requested = True
    
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=3.0)  # 3초만 대기
    
    self._is_running = False
```

**해결 방안**:
```python
def stop(self):
    if not self._is_running:
        return
    
    logger.info("Stopping backup...")
    self._stop_requested = True
    
    # 현재 파일 복사 완료까지 대기 (최대 10초)
    if self._thread and self._thread.is_alive():
        logger.info("Waiting for current file copy to complete...")
        self._thread.join(timeout=10.0)  # 10초로 증가
        
        if self._thread.is_alive():
            logger.warning("Backup thread did not stop gracefully")
    
    self._is_running = False
```

---

### 3.3 PlaybackPipeline position_timer 타이밍 이슈 (낮음)
**파일**: `camera/playback.py`
**위치**: `_start_position_timer()` (라인 434-450)

**이슈**:
- 100ms 간격으로 position 업데이트 (초당 10회)
- UI 업데이트 빈도가 높아 CPU 사용량 증가 가능
- duration 조회가 매번 실행됨 (파이프라인 쿼리)

**현재 코드**:
```python
def update_position():
    if self.state == PlaybackState.PLAYING:
        position = self.get_position()
        duration = self.get_duration()  # 매번 쿼리
        
        if self.on_position_changed and duration > 0:
            self.on_position_changed(position, duration)
        return True
    return False

self._position_timer = GLib.timeout_add(100, update_position)  # 100ms
```

**해결 방안**:
```python
def _start_position_timer(self):
    # duration은 한 번만 조회 (변경되지 않으므로)
    cached_duration = self.get_duration()
    
    def update_position():
        if self.state == PlaybackState.PLAYING:
            position = self.get_position()
            
            if self.on_position_changed and cached_duration > 0:
                self.on_position_changed(position, cached_duration)
            return True
        return False
    
    if self._position_timer:
        GLib.source_remove(self._position_timer)
    
    # 200ms로 증가 (초당 5회로 감소)
    self._position_timer = GLib.timeout_add(200, update_position)
```

---

## 4. 성능 이슈

### 4.1 PlaybackManager duration 조회 비활성화 (해결됨)
**파일**: `ui/playback_widget.py`
**위치**: `RecordingScanThread.run()` (라인 106-109)

**현재 상태**: ✅ 이미 해결됨
- duration 조회가 주석 처리되어 성능 문제 해결
- duration=0으로 설정하여 스캔 속도 대폭 향상

```python
# Duration 조회 건너뛰기 (성능 개선)
# 라즈베리파이에서 duration 조회가 너무 느리고 멈추는 경우가 있어서 비활성화
# duration = self._get_file_duration(str(file_path), Gst)
duration = 0  # duration은 나중에 재생 시점에 가져오도록 함
```

**참고사항**:
- `_get_file_duration()` 메서드는 남아있지만 사용되지 않음
- 필요 시 재생 시점에 duration 조회 가능

---

### 4.2 StorageService 파일 스캔 동기 실행 (중간)
**파일**: `core/storage.py`
**위치**: `get_recordings_for_camera()`, `get_all_recordings()` (라인 315-378)

**이슈**:
- 파일 스캔이 동기적으로 실행되어 UI 블로킹 가능
- 대량의 파일이 있을 경우 응답 지연
- glob 패턴 사용하지만 디렉토리 순회는 동기

**현재 코드**:
```python
def get_recordings_for_camera(self, camera_id: str) -> List[Dict[str, any]]:
    recordings = []
    camera_path = self.recordings_path / camera_id
    
    # 동기 스캔
    for date_dir in sorted(camera_path.iterdir(), reverse=True):
        for file in sorted(date_dir.glob("*.mp4"), reverse=True):
            stat = file.stat()
            recordings.append({...})
    
    return recordings
```

**해결 방안**:
1. 비동기 스캔 구현 (QThread 사용)
2. 캐싱 메커니즘 추가
3. 페이지네이션 구현

```python
class RecordingScanWorker(QThread):
    scan_completed = pyqtSignal(list)
    
    def __init__(self, camera_id: str, recordings_path: Path):
        super().__init__()
        self.camera_id = camera_id
        self.recordings_path = recordings_path
    
    def run(self):
        recordings = []
        camera_path = self.recordings_path / self.camera_id
        
        for date_dir in sorted(camera_path.iterdir(), reverse=True):
            for file in sorted(date_dir.glob("*.mp4"), reverse=True):
                recordings.append({...})
        
        self.scan_completed.emit(recordings)

# StorageService에서 비동기 스캔 사용
def get_recordings_for_camera_async(self, camera_id: str, callback):
    worker = RecordingScanWorker(camera_id, self.recordings_path)
    worker.scan_completed.connect(callback)
    worker.start()
    return worker
```

---

### 4.3 BackupWorker MD5 계산 블로킹 (낮음)
**파일**: `ui/backup_dialog.py`
**위치**: `_calculate_md5()` (라인 195-202)

**이슈**:
- MD5 계산이 동기적으로 실행되어 UI 블로킹 가능
- 대용량 파일의 경우 계산 시간이 오래 걸림
- 진행률 업데이트가 MD5 계산 중 멈춤

**현재 코드**:
```python
def _calculate_md5(self, file_path: Path) -> str:
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

# 백업 루프에서 동기 호출
if self.verification:
    source_md5 = self._calculate_md5(source)
    dest_md5 = self._calculate_md5(dest_path)
```

**해결 방안**:
1. 청크 단위 MD5 계산 중 진행률 업데이트
2. 취소 가능하도록 개선

```python
def _calculate_md5_with_progress(self, file_path: Path, file_name: str) -> str:
    md5_hash = hashlib.md5()
    file_size = file_path.stat().st_size
    bytes_read = 0
    
    with open(file_path, 'rb') as f:
        while True:
            if self._stop_requested:
                return None
            
            chunk = f.read(4096)
            if not chunk:
                break
            
            md5_hash.update(chunk)
            bytes_read += len(chunk)
            
            # 진행률 업데이트 (10MB마다)
            if bytes_read % (10 * 1024 * 1024) == 0:
                progress_pct = int((bytes_read / file_size) * 100)
                self.signals.log_message.emit(
                    f"MD5 검증 중: {file_name} ({progress_pct}%)",
                    "info"
                )
    
    return md5_hash.hexdigest()
```

---

### 4.4 CameraStream 재연결 지연 (낮음)
**파일**: `camera/streaming.py`
**위치**: `reconnect()` (라인 157-178)

**이슈**:
- 재연결 시 `time.sleep(self.config.reconnect_delay)` 사용
- 동기적 sleep으로 스레드 블로킹
- reconnect_delay 값에 따라 UI 응답성 저하 가능

**현재 코드**:
```python
def reconnect(self, frame_callback=None, enable_recording=False) -> bool:
    self.status = StreamStatus.RECONNECTING
    logger.info(f"Attempting to reconnect to camera: {self.config.name}")
    
    # Disconnect first
    self.disconnect()
    
    # Wait before reconnecting
    time.sleep(self.config.reconnect_delay)  # 동기 블로킹
    
    # Try to connect
    return self.connect(frame_callback, enable_recording=enable_recording)
```

**해결 방안**:
```python
def reconnect(self, frame_callback=None, enable_recording=False) -> bool:
    self.status = StreamStatus.RECONNECTING
    logger.info(f"Attempting to reconnect to camera: {self.config.name}")
    
    # Disconnect first
    self.disconnect()
    
    # Non-blocking delay using QTimer
    from PyQt5.QtCore import QTimer
    
    def delayed_connect():
        self.connect(frame_callback, enable_recording=enable_recording)
    
    QTimer.singleShot(self.config.reconnect_delay * 1000, delayed_connect)
    return True
```

---

## 5. 추가 최적화 제안

### 5.1 설정 저장 최적화 (낮음)
**파일**: `core/config.py`
**위치**: `save_config()` (라인 181-255)

**제안**:
- 현재 모든 섹션을 매번 저장하는 방식
- 변경된 섹션만 저장하도록 개선 가능
- Dirty flag 패턴 적용

```python
class ConfigManager:
    def __init__(self, ...):
        # ...
        self._dirty_sections = set()  # 변경된 섹션 추적
    
    def mark_section_dirty(self, section: str):
        self._dirty_sections.add(section)
    
    def save_config(self, save_ui: bool = False) -> bool:
        # 변경된 섹션만 저장
        for section in self._dirty_sections:
            if section == "cameras":
                self.db_manager.save_cameras(self.config["cameras"])
            elif section == "recording":
                self.db_manager.save_recording_config(self.config["recording"])
            # ...
        
        self._dirty_sections.clear()
```

---

### 5.2 GStreamer 파이프라인 재사용 (낮음)
**파일**: `camera/gst_pipeline.py`
**위치**: 전체 클래스

**제안**:
- 현재 재연결 시 파이프라인을 완전히 재생성
- 파이프라인 재사용으로 초기화 시간 단축 가능
- READY 상태로 전환 후 재사용

```python
def reconnect(self):
    # 파이프라인 재생성 대신 재사용
    if self.pipeline:
        self.pipeline.set_state(Gst.State.READY)
        # RTSP URL만 업데이트
        rtspsrc = self.pipeline.get_by_name("source")
        rtspsrc.set_property("location", self.rtsp_url)
        self.pipeline.set_state(Gst.State.PLAYING)
    else:
        self.create_pipeline()
        self.start()
```

---

### 5.3 로깅 성능 개선 (낮음)
**파일**: 전체 프로젝트
**위치**: 로거 사용 전반

**제안**:
- 높은 빈도로 호출되는 함수에서 `logger.trace()` 사용 고려
- 조건부 로깅으로 성능 향상

```python
# 현재: 매번 문자열 포맷팅
logger.debug(f"Frame received: {frame_count}, timestamp: {timestamp}")

# 개선: 로그 레벨 체크 후 포맷팅
if logger.level("DEBUG").no <= logger._core.min_level:
    logger.debug(f"Frame received: {frame_count}, timestamp: {timestamp}")
```

---

## 6. 우선순위 요약

### 즉시 수정 필요 (높음)
1. **GstPipeline 콜백 정리 누락** - 메모리 누수 직접 원인
   - `stop()` 메서드에 `cleanup_callbacks()` 추가

### 조만간 수정 권장 (중간)
1. **ConfigManager DB 연결 미정리** - 리소스 누수
2. **GStreamer 파이프라인 명시적 해제** - 메모리 누적
3. **BackupWorker/DeleteWorker 데몬 스레드** - 데이터 손실 가능
4. **타이머 정리 불완전** - 리소스 누수
5. **RecordingScanThread 중복 실행** - 안정성
6. **StorageService 동기 스캔** - 성능

### 선택적 개선 (낮음)
1. RecordingScanThread 정리
2. SystemMonitorThread 종료 대기
3. BackupDialog 종료 대기 시간
4. PlaybackPipeline 타이머 간격
5. BackupWorker MD5 블로킹
6. CameraStream 재연결 지연
7. 기타 최적화 제안

---

## 7. 테스트 권장사항

각 개선사항 적용 후 다음을 테스트:

1. **메모리 누수 테스트**:
   - 장시간 실행 후 메모리 사용량 모니터링
   - 카메라 연결/해제 반복 테스트
   - 재생/정지 반복 테스트

2. **리소스 정리 테스트**:
   - 프로그램 종료 후 프로세스/파일 핸들 확인
   - DB 연결 상태 확인
   - GStreamer 파이프라인 정리 확인

3. **성능 테스트**:
   - 대량 파일 스캔 속도 측정
   - UI 응답성 테스트
   - CPU/메모리 사용량 측정

4. **안정성 테스트**:
   - 백업/삭제 작업 중 강제 종료
   - 네트워크 끊김 시나리오
   - 저장소 공간 부족 시나리오

---

## 관련 문서
- `_doc/gst_pipeline_architecture.md` - 파이프라인 아키텍처
- `_doc/gstreamer_exception_handling_patterns.md` - 예외 처리 패턴
- `_doc/playback_scan_stuck_issue_fix.md` - 재생 스캔 개선사항
- `_doc/db_migration_complete.md` - DB 마이그레이션 문서

