# USB 재연결 시 PermissionError 프로그램 크래시 해결

**날짜:** 2025-11-10
**문제:** USB 연결 끊김 후 재연결 시 권한 문제로 프로그램 종료
**해결:** 예외 처리 및 권한 검증 로직 추가

---

## 문제 상황

### 발생한 에러

```
2025-11-10 13:47:24 | ERROR    | camera.gst_pipeline:_on_format_location:1823 | [STORAGE] USB disconnected during file rotation: [Errno 2] 그런 파일이나 디렉터리가 없습니다: '/media/itlog/NVR_MAIN/Recordings/cam_01/20251110'
2025-11-10 13:47:24 | CRITICAL | camera.gst_pipeline:_handle_storage_error:1202 | [STORAGE] USB disconnected: [Errno 2] 그런 파일이나 디렉터리가 없습니다: '/media/itlog/NVR_MAIN/Recordings/cam_01/20251110'
...
2025-11-10 13:47:42 | DEBUG    | camera.gst_pipeline:_retry_recording:1444 | [RECORDING RETRY] Storage path still unavailable (retry 3/20)
Traceback (most recent call last):
  File "/media/itlog/NVR_MAIN/nvr_gstreamer/ui/recording_control_widget.py", line 468, in _update_disk_usage
  File "/usr/lib/python3.9/pathlib.py", line 1407, in exists
    self.stat()
  File "/usr/lib/python3.9/pathlib.py", line 1221, in stat
    return self._accessor.stat(self)
PermissionError: [Errno 13] 허가 거부: '/media/itlog/NVR_MAIN/Recordings'
```

### 문제 원인

1. **USB 연결 해제**: 녹화 중 USB가 분리됨
2. **저장소 에러 감지**: `gst_pipeline.py`가 정상적으로 감지하고 재시도 시작
3. **USB 재연결**: USB가 다시 마운트될 때 권한이 변경됨
4. **PermissionError 발생**: UI 위젯이 주기적으로 디스크 사용량을 확인하는 중 권한 에러 발생
5. **프로그램 크래시**: 처리되지 않은 예외로 인해 프로그램 종료

### 시나리오

```
[녹화 중] → [USB 제거] → [재시도 시작] → [USB 재연결 (권한 변경)]
                                           ↓
                               [UI 위젯 디스크 확인]
                                           ↓
                               [PermissionError 발생]
                                           ↓
                               [프로그램 종료] ❌
```

---

## 해결 방법

### 1. UI 위젯 예외 처리 추가

**파일:** `ui/recording_control_widget.py`
**메서드:** `_update_disk_usage()`

#### 수정 내용

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

#### 개선 사항

1. **USB 마운트 포인트 확인**: `/media/itlog/NVR_MAIN` 경로 존재 여부를 먼저 확인
2. **권한 사전 확인**: `os.access()`로 읽기 권한을 먼저 테스트
3. **예외 처리**:
   - `PermissionError`: 권한 거부
   - `OSError`: 일반적인 I/O 에러
   - `Exception`: 기타 예외
4. **사용자 피드백**: UI에 상태 표시 ("⚠ Storage: Permission Denied" 등)

### 2. Pipeline 권한 검증 강화

**파일:** `camera/gst_pipeline.py`
**메서드:** `_validate_recording_path()`

#### 수정 내용

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

#### 개선 사항

1. **마운트 포인트 권한 확인**: USB 재연결 시 마운트 포인트의 읽기/실행 권한 확인
2. **예외 처리**: `PermissionError`를 명시적으로 처리
3. **조기 실패**: 권한 문제를 조기에 감지하여 불필요한 재시도 방지

---

## 동작 흐름 비교

### 이전 동작 (문제 발생)

```
[USB 제거] → [재시도 시작]
                ↓
         [USB 재연결 (권한 변경)]
                ↓
         [UI 위젯 디스크 확인]
                ↓
         [Path.exists() 호출]
                ↓
         [PermissionError 발생]
                ↓
         [프로그램 종료] ❌
```

### 개선 후 동작

```
[USB 제거] → [재시도 시작]
                ↓
         [USB 재연결 (권한 변경)]
                ↓
         ┌─ [Pipeline 권한 검증]
         │      ↓
         │   [권한 없음 감지]
         │      ↓
         │   [재시도 계속]
         │
         └─ [UI 위젯 디스크 확인]
                ↓
            [마운트 포인트 확인]
                ↓
            [os.access() 권한 확인]
                ↓
            [권한 없음]
                ↓
            [UI에 "⚠ Storage: Permission Denied" 표시] ✅
                ↓
            [프로그램 계속 실행] ✅
```

---

## 테스트 시나리오

### 테스트 1: USB 제거 및 재연결

**절차:**
1. 프로그램 실행 및 녹화 시작
2. USB 연결 해제 (`sudo umount /media/itlog/NVR_MAIN`)
3. USB 재연결 (동일한 권한)
4. 자동 복구 확인

**예상 결과:**
- ✅ 스트리밍 계속 동작
- ✅ 녹화 자동 재개
- ✅ UI에 디스크 사용량 정상 표시
- ✅ 프로그램 계속 실행

### 테스트 2: 권한 변경된 USB 재연결

**절차:**
1. 프로그램 실행 및 녹화 시작
2. USB 연결 해제
3. USB 읽기 전용으로 재마운트 (`sudo mount -o ro /dev/sdb1 /media/itlog/NVR_MAIN`)
4. UI 상태 확인

**예상 결과:**
- ✅ UI에 "⚠ Storage: Permission Denied" 표시
- ✅ 재시도 계속 진행
- ✅ 프로그램 계속 실행 (크래시 없음)
- ✅ 스트리밍 정상 동작

### 테스트 3: 다른 권한으로 재마운트

**절차:**
1. 프로그램 실행 및 녹화 시작
2. USB 연결 해제
3. USB를 root 소유로 재마운트 (`sudo mount -o uid=root,gid=root /dev/sdb1 /media/itlog/NVR_MAIN`)
4. UI 상태 확인

**예상 결과:**
- ✅ Pipeline 권한 검증 실패
- ✅ UI에 "⚠ Storage: Permission Denied" 표시
- ✅ 재시도 계속 진행
- ✅ 프로그램 계속 실행

### 테스트 4: 올바른 권한으로 재마운트 후 복구

**절차:**
1. 테스트 2 또는 3 실행 후
2. USB를 올바른 권한으로 재마운트 (`sudo mount -o uid=itlog,gid=itlog /dev/sdb1 /media/itlog/NVR_MAIN`)
3. 자동 복구 확인

**예상 결과:**
- ✅ 권한 검증 통과
- ✅ 녹화 자동 재개
- ✅ UI에 디스크 사용량 정상 표시
- ✅ 재시도 타이머 중지

---

## 수정 파일 목록

### 1. `ui/recording_control_widget.py`
- **라인:** 459-503
- **변경 내용:** `_update_disk_usage()` 메서드에 예외 처리 및 권한 확인 추가

### 2. `camera/gst_pipeline.py`
- **라인:** 1889-1898
- **변경 내용:** `_validate_recording_path()` 메서드에 마운트 포인트 권한 확인 추가

### 3. `_doc/storage_disconnected_handling_review.md`
- **섹션:** Issue #3 추가
- **변경 내용:** USB 재연결 PermissionError 문제 및 해결 방법 문서화

---

## 관련 이슈

- **Issue #1**: format-location 예외 처리 (완료)
- **Issue #3**: UI 위젯 PermissionError 처리 (완료) ← **이번 수정**
- **Issue #2**: 내부 muxer 에러 감지 (예정)
- **Issue #4**: 손상된 파일 정리 (예정)

---

## 결론

### 개선 효과

1. **프로그램 안정성 향상**: USB 재연결 시 권한 문제로 인한 크래시 방지
2. **사용자 경험 개선**: UI에 명확한 상태 표시
3. **자동 복구 보장**: 권한 문제 해결 시 자동으로 녹화 재개
4. **스트리밍 연속성**: USB 문제와 관계없이 스트리밍 계속 동작

### 핵심 원칙

1. **방어적 프로그래밍**: 모든 I/O 작업에 예외 처리
2. **사전 검증**: `os.access()`로 권한을 먼저 확인
3. **우아한 실패**: 크래시 대신 상태 표시 및 재시도
4. **격리 설계**: Recording Branch 문제가 Streaming Branch에 영향 없음

---

**작성자:** Claude Code
**참조 문서:** `_doc/storage_disconnected_handling_review.md`
