# gst_pipeline.py 예외 처리 검토 및 개선 보고서

**작성일:** 2025-11-10
**대상 파일:** `camera/gst_pipeline.py`
**목적:** RTSP 네트워크 에러 및 저장소 예외 처리 분석 및 개선

---

## 1. 현재 예외 처리 구조 분석

### 1.1 RTSP 네트워크 에러 처리

#### 연결 타임아웃 및 재시도 설정
```python
# 라인 187-206
rtspsrc.set_property("latency", latency_ms)          # 기본 200ms
rtspsrc.set_property("tcp-timeout", tcp_timeout * 1000)  # 기본 10000ms
rtspsrc.set_property("timeout", connection_timeout * 1000000)  # 기본 10초
rtspsrc.set_property("retry", 5)  # 재시도 5회
```

**장점:**
- 설정 파일에서 동적으로 조정 가능
- rtspsrc 내장 재시도 메커니즘 활용

**문제점:**
- retry 값이 하드코딩 (5회 고정)
- 타임아웃이 너무 짧을 경우 불안정한 네트워크에서 빈번한 재연결

#### 네트워크 에러 분류
```python
# 라인 1023-1030
if src_name == "source":
    if error_code in [1, 7, 9, 10]:
        return ErrorType.RTSP_NETWORK
```

**처리 에러 코드:**
- 1: Internal data stream error
- 7: Could not open (재연결 타임아웃)
- 9: Could not read
- 10: Could not write

**문제점:**
- 매직 넘버 사용 (에러 코드 상수화 필요)
- GStreamer 버전별 에러 코드 차이 고려 안 됨

#### 재연결 로직 - 지수 백오프
```python
# 라인 1164-1185
def _schedule_reconnect(self):
    delay = min(5 * (2 ** self.retry_count), 60)  # 최대 60초
    self.retry_count += 1

    if self.retry_count >= self.max_retries:  # 기본 10회
        logger.error(f"Max retries ({self.max_retries}) reached")
        return  # ⚠️ 사용자 알림 없이 종료
```

**장점:**
- 지수 백오프로 네트워크 부하 감소
- 최대 재시도 제한으로 무한 루프 방지
- 비동기 처리로 GLib 스레드 블로킹 방지

**문제점:**
- 최대 재시도 초과 시 사용자 알림 없음
- 재연결 타이머 중복 생성 가능성 (race condition)

---

### 1.2 저장소 관련 에러 처리

#### 디스크 용량 부족 - ⚠️ 심각한 문제
```python
# 라인 1101-1104
def _handle_disk_full_error(self, err):
    logger.critical(f"[DISK] Disk full: {err}")
    self._handle_disk_full()  # ❌ 이 메서드가 구현되지 않음!
```

**문제:**
- `_handle_disk_full()` 메서드가 **정의되지 않음**
- 호출 시 `AttributeError` 발생하여 프로그램 크래시

**필요한 구현:**
```python
def _handle_disk_full(self):
    """디스크 용량 부족 처리"""
    # 1. 녹화 중지
    if self._is_recording:
        self.stop_recording()

    # 2. 자동 정리
    from core.storage import StorageService
    storage_service = StorageService()
    deleted_count = storage_service.auto_cleanup(
        max_age_days=7,
        min_free_space_gb=2.0
    )

    # 3. 공간 확보 확인 및 재시도
    if storage_service.get_free_space_gb() >= 2.0:
        self._recording_should_auto_resume = True
        self._schedule_recording_retry()
```

#### 저장소 경로 검증
```python
# 라인 1641-1748: _validate_recording_path()
# 5단계 검증 프로세스
# 1. USB 마운트 상태 확인
# 2. 디렉토리 생성 시도
# 3. 접근 권한 확인 (R/W/X)
# 4. 디스크 공간 확인 (최소 1GB)
# 5. 파일 생성 테스트
```

**장점:**
- 매우 상세한 사전 검증
- USB 마운트 상태까지 확인

**문제점:**
- 녹화 시작 시점에만 검증 (녹화 중 USB 제거 시 실시간 감지 불가)
- 테스트 파일 생성/삭제로 인한 I/O 오버헤드

#### USB 분리 감지 및 복구
```python
# 라인 1081-1099: _handle_storage_error()
def _handle_storage_error(self, err):
    # 1. 녹화 중지 (storage_error 플래그로 split-now 신호 건너뛰기)
    self.stop_recording(storage_error=True)

    # 2. 에러 플래그 설정
    self._recording_branch_error = True

    # 3. 자동 재개 플래그 설정
    self._recording_should_auto_resume = True

    # 4. 녹화 재시도 스케줄링 (6초마다, 최대 20회 = 약 2분)
    self._schedule_recording_retry()
```

**장점:**
- 스트리밍은 유지하면서 녹화만 중지
- USB 재연결 시 자동 복구
- storage_error 플래그로 파일 finalization 건너뛰기

**문제점:**
- 최대 2분 재시도 후 포기 (장시간 USB 분리 시 수동 개입 필요)
- 재시도 중 CPU 자원 낭비 가능성

---

## 2. 일반적인 GStreamer 예외 처리 패턴과의 비교

### 2.1 표준 패턴 대비 부족한 점

#### 1) 에러 도메인(Domain) 미활용 ⚠️
**표준 패턴:**
```python
err, debug = message.parse_error()
domain = err.domain

if domain == Gst.CoreError.quark():
    # Core error
elif domain == Gst.ResourceError.quark():
    # Resource error (disk, network)
    if err.code == Gst.ResourceError.NO_SPACE_LEFT:
        # Disk full
    elif err.code == Gst.ResourceError.NOT_FOUND:
        # Network error
```

**현재 방식:**
```python
# 에러 메시지 문자열 매칭에 의존
error_str = str(err).lower()
if ("space" in error_str or "no space" in error_str):
    return ErrorType.DISK_FULL
```

**문제:**
- 로케일에 따라 메시지가 다를 수 있음
- GStreamer 버전별 메시지 변경 가능성

#### 2) BUFFERING 메시지 처리 누락 ⚠️
```python
# 표준 패턴
elif t == Gst.MessageType.BUFFERING:
    percent = message.parse_buffering()
    if percent < 100:
        # 버퍼링 중 - 불필요한 재연결 방지
        logger.info(f"Buffering: {percent}%")
    else:
        logger.info("Buffering complete")
```

**현재:**
- BUFFERING 메시지 처리 완전 누락
- 네트워크 일시적 지연 시 불필요한 재연결 발생 가능

#### 3) WARNING 메시지 활용 부족
```python
# 현재: 로그만 출력
elif t == Gst.MessageType.WARNING:
    logger.warning(f"Pipeline warning: {warn}")
```

**개선 방향:**
- Critical warning은 에러로 승격
- 반복되는 warning은 문제 징후로 감지

#### 4) QoS, CLOCK_LOST, LATENCY 메시지 무시
- **QoS**: 프레임 드롭 발생 시 성능 저하 감지
- **CLOCK_LOST**: 클럭 동기화 손실 시 파이프라인 복구
- **LATENCY**: 레이턴시 재계산 필요 시 처리

---

## 3. 심각한 문제점 및 누락 사항

### 3.1 Critical Issues (즉시 수정 필요)

#### ❌ Issue #1: `_handle_disk_full()` 메서드 미구현
- **위치:** 라인 1103
- **영향:** 디스크 용량 부족 시 프로그램 크래시
- **우선순위:** 🔴 Critical

#### ⚠️ Issue #2: 재연결 타이머 리소스 정리 누락
```python
def stop(self):
    self._stop_timestamp_update()       # ✓
    self._cancel_recording_retry()      # ✓
    # ❌ reconnect_timer 정리 누락!
```
- **위치:** stop() 메서드
- **영향:** 리소스 누수
- **우선순위:** 🔴 Critical

#### ⚠️ Issue #3: 에러 분류의 불안정성
- **현재:** 문자열 매칭 의존
- **문제:** 로케일/버전 변경 시 오작동
- **우선순위:** 🔴 Critical

### 3.2 High Priority Issues

#### Issue #4: BUFFERING 메시지 미처리
- **영향:** 불필요한 재연결로 인한 끊김 현상
- **우선순위:** 🟠 High

#### Issue #5: 콜백 해제 메커니즘 없음
```python
# 등록만 가능, 해제 불가
def register_recording_callback(self, callback):
    self._recording_state_callbacks.append(callback)
```
- **영향:** 메모리 누수, 중복 콜백 실행
- **우선순위:** 🟠 High

#### Issue #6: 최대 재시도 초과 시 사용자 알림 없음
```python
if self.retry_count >= self.max_retries:
    logger.error("Max retries reached")
    return  # ❌ UI 업데이트 없음
```
- **영향:** 사용자가 연결 실패 인지 불가
- **우선순위:** 🟠 High

### 3.3 Medium Priority Issues

#### Issue #7: 동시다발적 에러 처리 미흡
- 네트워크 끊김 + USB 분리 동시 발생 시 처리 로직 충돌 가능
- 우선순위: 🟡 Medium

#### Issue #8: 파이프라인 상태 변경 실패 시 복구 없음
```python
ret = self.pipeline.set_state(Gst.State.PLAYING)
if ret == Gst.StateChangeReturn.FAILURE:
    logger.error("Failed to start pipeline")
    return False  # ❌ 리소스 정리 없이 종료
```
- 우선순위: 🟡 Medium

#### Issue #9: 메인 루프 스레드 강제 종료 미흡
```python
self._thread.join(timeout=2.0)
# 타임아웃 후에도 스레드가 살아있을 수 있음
```
- 우선순위: 🟡 Medium

---

## 4. 개선 권장 사항

### 4.1 즉시 적용 (Critical Priority)

#### 1. `_handle_disk_full()` 메서드 구현
```python
def _handle_disk_full(self):
    """디스크 용량 부족 처리 - 자동 정리 및 재시도"""
    logger.critical("[DISK] Disk full detected")

    # 1. 녹화 중지
    if self._is_recording:
        self.stop_recording()

    # 2. StorageService를 통한 자동 정리
    try:
        from core.storage import StorageService
        storage_service = StorageService()

        # 오래된 파일 삭제 (예: 7일 이상)
        deleted_count = storage_service.auto_cleanup(
            max_age_days=7,
            min_free_space_gb=2.0
        )

        logger.info(f"[DISK] Cleaned up {deleted_count} old files")

        # 3. 공간 확보 확인
        time.sleep(1.0)
        free_gb = storage_service.get_free_space_gb()

        if free_gb >= 2.0:
            logger.success(f"[DISK] Space freed: {free_gb:.2f}GB")
            # 녹화 자동 재개
            self._recording_should_auto_resume = True
            self._schedule_recording_retry()
        else:
            logger.error("[DISK] Still not enough space after cleanup")
            # UI 알림
            self._notify_recording_state_change(False)

    except Exception as e:
        logger.error(f"[DISK] Cleanup failed: {e}")
```

#### 2. 재연결 타이머 정리 추가
```python
def stop(self):
    """파이프라인 정지 및 리소스 정리"""
    # 기존 로직...
    self._stop_timestamp_update()
    self._cancel_recording_retry()

    # ✅ 재연결 타이머 정리 추가
    if self.reconnect_timer:
        if self.reconnect_timer.is_alive():
            self.reconnect_timer.cancel()
        self.reconnect_timer = None

    # 나머지 로직...
```

#### 3. 에러 도메인 기반 분류로 개선
```python
def _classify_error(self, message, err, debug):
    """에러 분류 - 도메인/코드 우선, 메시지 문자열은 fallback"""
    domain = err.domain
    code = err.code
    src_name = message.src.get_name()

    # 1. 도메인 우선 확인
    if domain == Gst.ResourceError.quark():
        if code == Gst.ResourceError.NOT_FOUND:
            if src_name == "source":
                return ErrorType.RTSP_NETWORK
        elif code == Gst.ResourceError.OPEN_WRITE:
            return ErrorType.STORAGE_DISCONNECTED
        elif code == Gst.ResourceError.NO_SPACE_LEFT:
            return ErrorType.DISK_FULL
        elif code == Gst.ResourceError.READ:
            if src_name == "source":
                return ErrorType.RTSP_NETWORK
            else:
                return ErrorType.STORAGE_DISCONNECTED

    elif domain == Gst.StreamError.quark():
        if src_name == "source":
            return ErrorType.RTSP_NETWORK

    # 2. 소스 엘리먼트 확인 (fallback)
    error_str = str(err).lower()

    if src_name == "source":
        if code in [1, 7, 9, 10]:
            return ErrorType.RTSP_NETWORK

    elif src_name.startswith("sink") or "splitmuxsink" in src_name:
        if ("space" in error_str or "no space" in error_str):
            return ErrorType.DISK_FULL
        else:
            return ErrorType.STORAGE_DISCONNECTED

    # 3. 메시지 내용 확인 (최후 fallback)
    if ("space" in error_str or "no space" in error_str):
        return ErrorType.DISK_FULL

    return ErrorType.UNKNOWN
```

### 4.2 높은 우선순위 (High Priority)

#### 4. BUFFERING 메시지 처리 추가
```python
def _on_bus_message(self, bus, message):
    t = message.type

    # 기존 처리...

    elif t == Gst.MessageType.BUFFERING:
        percent = message.parse_buffering()
        src_name = message.src.get_name() if message.src else "unknown"

        if percent < 100:
            logger.info(f"[BUFFERING] {src_name}: {percent}% - Network slow")
            # 버퍼링 중이므로 재연결하지 않음
            # 필요시 파이프라인 일시 정지
            # self.pipeline.set_state(Gst.State.PAUSED)
        else:
            logger.info(f"[BUFFERING] {src_name}: Complete")
            # 버퍼링 완료 - 재생 재개
            # self.pipeline.set_state(Gst.State.PLAYING)
```

#### 5. 콜백 해제 메커니즘 추가
```python
def unregister_recording_callback(self, callback):
    """녹화 상태 변경 콜백 해제"""
    if callback in self._recording_state_callbacks:
        self._recording_state_callbacks.remove(callback)
        logger.debug(f"Recording callback unregistered for {self.camera_id}")

def unregister_connection_callback(self, callback):
    """연결 상태 변경 콜백 해제"""
    if callback in self._connection_state_callbacks:
        self._connection_state_callbacks.remove(callback)
        logger.debug(f"Connection callback unregistered for {self.camera_id}")

def cleanup_callbacks(self):
    """모든 콜백 정리 (파이프라인 종료 시 호출)"""
    self._recording_state_callbacks.clear()
    self._connection_state_callbacks.clear()
    logger.debug(f"All callbacks cleared for {self.camera_id}")
```

#### 6. 최대 재시도 초과 시 사용자 알림
```python
def _schedule_reconnect(self):
    """재연결 스케줄링 - 지수 백오프"""
    if self.retry_count >= self.max_retries:
        logger.error(f"[RECONNECT] Max retries ({self.max_retries}) reached for {self.camera_id}")

        # ✅ 사용자 알림 추가
        self._notify_connection_state_change(False)

        # ✅ UI 상태 업데이트 (ERROR 상태로 변경)
        # 상위 CameraStream 클래스에서 처리하도록 알림

        return

    # 나머지 로직...
```

### 4.3 중간 우선순위 (Medium Priority)

#### 7. QoS, CLOCK_LOST 메시지 처리
```python
elif t == Gst.MessageType.QOS:
    # 프레임 드롭 발생 - 성능 저하
    logger.warning(f"[QoS] Frame drops detected on {self.camera_id}")
    # 필요시 비트레이트 조정 또는 사용자 알림

elif t == Gst.MessageType.CLOCK_LOST:
    # 클럭 동기화 손실 - 파이프라인 재시작
    logger.warning(f"[CLOCK] Clock lost, recalculating...")
    self.pipeline.set_state(Gst.State.PAUSED)
    self.pipeline.set_state(Gst.State.PLAYING)

elif t == Gst.MessageType.LATENCY:
    # 레이턴시 재계산
    logger.debug(f"[LATENCY] Recalculating latency...")
    self.pipeline.recalculate_latency()
```

#### 8. 에러 코드 상수화
```python
# 파일 상단에 추가
class RtspErrorCode:
    """RTSP 에러 코드 상수"""
    INTERNAL_ERROR = 1
    COULD_NOT_OPEN = 7
    COULD_NOT_READ = 9
    COULD_NOT_WRITE = 10

class SplitmuxErrorCode:
    """splitmuxsink 에러 코드 상수"""
    NO_FILE_NAME = 3
    STATE_CHANGE_FAILED = 4
    COULD_NOT_WRITE = 10

# 사용
if error_code in [RtspErrorCode.INTERNAL_ERROR,
                  RtspErrorCode.COULD_NOT_OPEN,
                  RtspErrorCode.COULD_NOT_READ]:
    return ErrorType.RTSP_NETWORK
```

#### 9. 메인 루프 스레드 강제 종료 개선
```python
def stop(self):
    # 기존 로직...

    # 메인 루프 종료 요청
    if self.main_loop:
        self.main_loop.quit()

    # 스레드 종료 대기
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=2.0)

        # ✅ 타임아웃 후 확인
        if self._thread.is_alive():
            logger.warning(f"[THREAD] Main loop thread did not stop in time for {self.camera_id}")
            # Python에서는 스레드 강제 종료 불가
            # 하지만 프로그램 종료 시 daemon 스레드는 자동 종료됨
```

---

## 5. 테스트 권장 사항

### 5.1 네트워크 에러 시뮬레이션
```bash
# 1. 네트워크 차단
sudo iptables -A OUTPUT -d <RTSP_SERVER_IP> -j DROP

# 2. 테스트 후 복구
sudo iptables -D OUTPUT -d <RTSP_SERVER_IP> -j DROP
```

### 5.2 디스크 용량 부족 시뮬레이션
```bash
# 1. 작은 크기의 tmpfs 생성
sudo mkdir -p /tmp/test_storage
sudo mount -t tmpfs -o size=100M tmpfs /tmp/test_storage

# 2. IT_RNVR.json에서 recording_path를 /tmp/test_storage로 설정

# 3. 테스트 후 정리
sudo umount /tmp/test_storage
```

### 5.3 USB 분리 시뮬레이션
```bash
# 1. USB 마운트
# 2. 녹화 시작
# 3. USB 강제 마운트 해제
sudo umount /media/usb_device

# 4. USB 재연결
# 5. 자동 녹화 재개 확인
```

---

## 6. 요약 및 결론

### 6.1 현재 상태 평가
- **양호한 점:**
  - RTSP 네트워크 에러 감지 및 재연결 로직 구현
  - USB 분리 감지 및 자동 복구 메커니즘
  - 지수 백오프 재연결 전략
  - 상세한 저장소 경로 검증

- **심각한 문제:**
  - `_handle_disk_full()` 메서드 미구현 (크래시 가능)
  - 재연결 타이머 리소스 누수
  - 에러 분류의 불안정성 (문자열 매칭)

- **개선 필요:**
  - BUFFERING 메시지 처리 누락
  - 콜백 해제 메커니즘 없음
  - 최대 재시도 초과 시 사용자 알림 부족

### 6.2 우선순위별 작업 계획

**Phase 1: Critical (즉시 수정)**
1. `_handle_disk_full()` 구현
2. 재연결 타이머 정리 추가
3. 에러 도메인 기반 분류

**Phase 2: High Priority (1주일 내)**
4. BUFFERING 메시지 처리
5. 콜백 해제 메커니즘
6. 최대 재시도 알림

**Phase 3: Medium Priority (2주일 내)**
7. QoS, CLOCK_LOST 메시지 처리
8. 에러 코드 상수화
9. 메인 루프 스레드 정리 개선

### 6.3 일반적인 GStreamer 패턴 준수 여부

| 패턴 | 준수 여부 | 비고 |
|------|----------|------|
| 에러 도메인 활용 | ❌ 미준수 | 문자열 매칭 의존 |
| BUFFERING 처리 | ❌ 미준수 | 메시지 처리 누락 |
| WARNING 활용 | ⚠️ 부분 준수 | 로그만 출력 |
| 재연결 로직 | ✅ 준수 | 지수 백오프 적용 |
| 리소스 정리 | ⚠️ 부분 준수 | 타이머 정리 누락 |
| QoS 모니터링 | ❌ 미준수 | 메시지 무시 |
| 상태 변경 확인 | ⚠️ 부분 준수 | 복구 로직 부족 |

---

## 7. 참고 문서

- `_doc/gstreamer_exception_handling_patterns.md` - GStreamer 예외 처리 패턴
- `_doc/gst_pipeline_architecture.md` - 파이프라인 아키텍처
- `_doc/camera_disconnect_error_analysis.md` - 카메라 연결 해제 에러 분석
- GStreamer 공식 문서: https://gstreamer.freedesktop.org/documentation/

---

**검토 완료일:** 2025-11-10
**다음 검토 예정일:** Phase 1 완료 후
