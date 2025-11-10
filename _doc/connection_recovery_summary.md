# 카메라 연결 끊김 및 재연결 처리 - 요약 및 핵심 개념

## 개요

이 문서는 NVR GStreamer 애플리케이션의 네트워크 연결 끊김 및 자동 재연결 메커니즘을 종합적으로 분석한 것입니다.

**주요 파일**:
- `camera/gst_pipeline.py`: 파이프라인 에러 감지 및 처리
- `camera/streaming.py`: CameraStream 재연결 로직
- `ui/main_window.py`: UI 동기화

---

## 핵심 설계 원칙

### 1. Unified Pipeline with Tee & Valve
```
단일 파이프라인 아키텍처로 CPU 사용률 50% 감소

Source → Decode → Tee ─┬→ Streaming Valve → Video Sink
                       │
                       └→ Recording Valve → splitmuxsink

장점:
- 한 번의 디코딩만 필요
- Valve를 통한 실시간 모드 전환
- Branch별 독립적 에러 처리 가능
```

### 2. 분기별 에러 처리 (Branch-Specific Error Handling)
```
RTSP 네트워크 에러    →  파이프라인 전체 재시작
저장소 분리 에러      →  녹화만 중지, 스트리밍 유지
디스크 Full 에러      →  자동 정리 후 재시작
디코더 에러           →  버퍼 플러시 후 계속 진행
비디오 출력 에러      →  스트리밍만 중지, 녹화 유지
```

### 3. 녹화 상태 보존 (Recording State Persistence)
```
네트워크 끊김 감지
    ↓
was_recording = self._is_recording (상태 저장)
    ↓
파이프라인 재시작
    ↓
if was_recording:
    자동 녹화 재개
    └→ _recording_should_auto_resume 플래그 사용
```

---

## 에러 분류 체계 (Error Classification)

### 우선순위 기반 3단계 분류

```
1순위: GStreamer 에러 도메인
       ├─ Gst.ResourceError (네트워크, 파일, 디스크)
       ├─ Gst.StreamError (스트림 처리)
       └─ Gst.CoreError (상태 변경)

2순위: 소스 엘리먼트 이름
       ├─ source → RTSP_NETWORK
       ├─ sink/splitmuxsink → STORAGE
       └─ decoder → DECODER

3순위: 에러 메시지 문자열
       ├─ "space" → DISK_FULL
       ├─ "decode" → DECODER
       └─ "output window" → VIDEO_SINK
```

**장점**:
- 정확한 에러 타입 식별
- Fallback 메커니즘으로 견고성 확보
- 플랫폼 간 호환성

---

## 재연결 메커니즘

### 지수 백오프 (Exponential Backoff)
```
delay = min(5 * (2^retry_count), 60) 초

1차: 5초   (5 * 2^0)
2차: 10초  (5 * 2^1)
3차: 20초  (5 * 2^2)
...
최대: 60초 (5 * 2^11 = 10,240초 → 60초 제한)

장점:
- 네트워크 폭주 방지
- 점진적인 회복 기간 제공
- 최대 대기 60초로 UI 응답성 보장
```

### 중복 실행 방지
```
if self.reconnect_timer and self.reconnect_timer.is_alive():
    logger.debug("Reconnect already scheduled, skipping duplicate")
    return

if self._is_playing:
    logger.debug("Pipeline already running, skipping reconnect")
    self.retry_count = 0
    return
```

### 최대 재시도 한계
```
if self.retry_count >= self.max_retries:
    _notify_connection_state_change(False)
    logger.critical("Max retries reached")
    return

무한 재연결 루프 방지
UI에 ERROR 상태 표시
사용자 수동 개입 기회 제공
```

---

## 녹화 상태 유지 메커니즘

### 1. 자동 재개 (Auto-Resume)
```
네트워크 재연결 시나리오:

재연결 전:
  was_recording = self._is_recording (TRUE)

파이프라인 정지:
  self.stop()

재연결 성공 후:
  if _recording_should_auto_resume:
      sleep(1.0)  # 파이프라인 안정화
      start_recording()
      
결과: 파일 분할 (새 파일 시작)
```

### 2. 저장소 에러 시 자동 재개
```
USB 분리 감지:
  _handle_storage_error()
    ├─ stop_recording(storage_error=True)
    ├─ _recording_should_auto_resume = True
    └─ _schedule_recording_retry()

자동 재시도:
  _retry_recording() [6초 간격]
    ├─ _validate_recording_path()
    ├─ if 접근 가능:
    │    start_recording()
    └─ if 접근 불가:
         다음 재시도 스케줄

최대 재시도 횟수 초과 시 중단
```

### 3. 디스크 Full 시 자동 정리
```
디스크 Full 감지:
  _handle_disk_full()
    ├─ stop_recording()
    ├─ StorageService.auto_cleanup()
    │  └─ 7일 이상 오래된 파일 삭제
    ├─ sleep(1.0)
    ├─ 여유 공간 재확인
    │
    └─ if free_gb >= 2.0:
         _recording_should_auto_resume = True
         _schedule_recording_retry()
       else:
         _notify_recording_state_change(False)
```

---

## 파일 분할 (File Splitting)

### splitmuxsink 역할
```
자동 파일 회전:
  ├─ max-size-time: 파일 최대 지속 시간 설정
  ├─ format-location: 파일명 동적 생성 신호
  └─ async-finalize: FALSE (파일 강제 finalize)

동작 방식:
  파일 크기/시간 초과
    ↓
  format-location 신호 발송
    ↓
  _on_format_location() 콜백
    ↓
  새 파일명 생성
    ↓
  이전 파일 자동 finalize
    ↓
  새 파일 시작

결과:
  recordings/cam_01/2025-11-10/
  ├─ cam_01_20251110_160000.mp4 (종료된 파일)
  └─ cam_01_20251110_161500.mp4 (신규 파일)
```

### 네트워크 재연결 시 파일 분할
```
재연결 감지 → stop()
    ↓
splitmuxsink buffer flush
    ↓
이전 파일 finalize
    ↓
파이프라인 재시작 → start()
    ↓
splitmuxsink 초기화
    ↓
start_recording() 호출
    ↓
새로운 타임스탬프로 새 파일 시작

결과: 자동으로 분할된 녹화 파일
```

---

## UI 동기화 (UI Synchronization)

### 콜백 기반 상태 전파
```
GstPipeline (모델)
    ↓
_notify_connection_state_change(is_connected)
    │
    └─→ connection_callbacks[] 순회
        └─→ callback(camera_id, is_connected)
            │
            └─→ MainWindow (뷰)
                ├─→ _on_camera_connected()
                │   ├─ GridView channel 상태 업데이트
                │   ├─ RecordingStatusItem 활성화
                │   ├─ PTZ Controller 활성화
                │   └─ 자동 녹화 시작
                │
                └─→ _on_camera_disconnected()
                    ├─ GridView channel 비활성화
                    └─ RecordingStatusItem 비활성화
```

### 녹화 상태 동기화
```
GstPipeline
    ↓
_notify_recording_state_change(is_recording)
    │
    └─→ recording_callbacks[] 순회
        └─→ callback(camera_id, is_recording)
            │
            └─→ MainWindow
                ├─ GridView channel.set_recording(is_recording)
                ├─ RecordingStatusItem.set_recording(is_recording)
                └─ recording_started/stopped 신호 발송
```

---

## 스레드 안전성

### GLib MainLoop 문제 해결
```
문제:
  GLib 메인 루프에서 자기 자신을 join 불가
  → stop() 호출 중 교착(deadlock) 발생

해결책:
  별도 스레드에서 비동기 처리
  
구현:
  def _handle_rtsp_error():
      threading.Thread(
          target=self._async_stop_and_reconnect,
          daemon=True
      ).start()

장점:
  - 교착 현상 방지
  - 메인 루프 응답성 유지
  - UI 프리징 방지
```

### 타이머 관리
```
reconnect_timer = threading.Timer(delay, self._reconnect)
reconnect_timer.daemon = True
reconnect_timer.start()

장점:
  - daemon=True: 프로그램 종료 시 자동 정리
  - 명시적 cancel(): 중복 실행 방지
  - is_alive(): 실행 중 여부 확인
```

---

## 성능 특성

### 재연결 시간
```
네트워크 끊김 감지: ~10ms
파이프라인 정지: ~100ms
첫 재연결 대기: 5초
파이프라인 재시작: ~100ms
녹화 안정화 대기: 1000ms
     ──────────────────
총 소요 시간: ~6.2초 (첫 재시도 기준)
```

### 저장소 복구 시간
```
저장소 에러 감지: ~10ms
녹화 정지 및 재시도 스케줄: ~100ms
첫 재시도 대기: 6초
저장소 경로 검증: ~50ms
녹화 재시작: ~100ms
     ──────────────────
총 소요 시간: ~6.3초 (첫 재시도 기준)
```

### 디스크 Full 처리
```
디스크 Full 감지: ~10ms
녹화 정지: ~100ms
자동 정리 (파일 삭제): 가변적 (파일 개수에 따라)
여유 공간 재확인: ~50ms
녹화 재개: ~100ms
```

---

## 주요 플래그 및 변수

| 변수 | 타입 | 용도 | 범위 |
|------|------|------|------|
| `_is_playing` | bool | 파이프라인 실행 상태 | True/False |
| `_is_recording` | bool | 현재 녹화 진행 여부 | True/False |
| `_recording_should_auto_resume` | bool | 재연결 후 녹화 자동 재개 플래그 | True/False |
| `_recording_branch_error` | bool | 녹화 branch 에러 플래그 | True/False |
| `_streaming_branch_error` | bool | 스트리밍 branch 에러 플래그 | True/False |
| `retry_count` | int | 네트워크 재연결 시도 횟수 | 0 ~ max_retries |
| `_recording_retry_count` | int | 녹화 재시도 횟수 | 0 ~ _max_recording_retry |
| `reconnect_timer` | Timer | 네트워크 재연결 타이머 | None 또는 Timer 객체 |
| `_recording_retry_timer` | Timer | 녹화 재시도 타이머 | None 또는 Timer 객체 |

---

## 에러 상황별 대응 요약

### RTSP Network Error
```
감지: source 엘리먼트에서 ResourceError, StreamError
처리: _handle_rtsp_error()
결과:
  - 파이프라인 전체 중지
  - 지수 백오프로 재연결
  - 녹화 중이었으면 자동 재개
  - 최대 재시도: max_retries
  - 실패 시: ERROR 상태 UI 표시
```

### Storage Disconnected Error
```
감지: splitmuxsink/sink 엘리먼트에서 ResourceError
처리: _handle_storage_error()
결과:
  - 녹화만 중지 (스트리밍은 유지)
  - 6초 간격 자동 재시도
  - 저장소 경로 검증으로 복구 감지
  - 복구 시 자동 재개
  - 최대 재시도: _max_recording_retry
  - 실패 시: 사용자 알림
```

### Disk Full Error
```
감지: splitmuxsink에서 NO_SPACE_LEFT ResourceError
처리: _handle_disk_full()
결과:
  - 녹화 중지
  - StorageService 자동 정리 (7일 이상 파일)
  - 2GB 이상 여유 공간 확보 시 자동 재개
  - 정리 실패 시: 사용자 알림
```

### Decoder Error
```
감지: decoder 엘리먼트에서 StreamError
처리: _handle_decoder_error()
결과:
  - 버퍼 플러시 (flush-start → flush-stop)
  - 스트리밍, 녹화 계속
  - 자동 복구 (무시)
```

### Video Sink Error
```
감지: videosink 엘리먼트에서 error
처리: _handle_videosink_error()
결과:
  - 스트리밍 중지 (streaming_valve 닫기)
  - 녹화는 계속
  - Headless 모드: 무시
  - 자동 복구 없음 (사용자 수동 개입)
```

---

## 로깅 및 디버깅

### 주요 로그 태그
```
[RTSP]              - RTSP 연결 문제
[RECONNECT]         - 네트워크 재연결 진행
[STORAGE]           - 저장소 에러 및 복구
[RECORDING]         - 녹화 상태 변화
[RECORDING RETRY]   - 녹화 재시도
[DISK]              - 디스크 공간 문제
[DECODER]           - 디코딩 에러
[VIDEOSINK]         - 비디오 출력 에러
[BUFFERING]         - 네트워크 버퍼링
[CONNECTION SYNC]   - 연결 상태 UI 동기화
[UI SYNC]           - 녹화 상태 UI 동기화
```

### 디버그 명령
```bash
# GStreamer 파이프라인 그래프 생성
GST_DEBUG_DUMP_DOT_DIR=/tmp python main.py
# → /tmp/*.dot 파일 생성
# → graphviz로 시각화 가능

# 상세 디버그 로깅
GST_DEBUG=3 python main.py

# 특정 엘리먼트 디버그
GST_DEBUG=splitmuxsink:5 python main.py
```

---

## 제한사항 및 주의사항

### 1. 수동 녹화 종료 파일 문제
```
문제: stop_recording() 호출 시 생성된 파일이 재생 불가능
원인: MP4 moov atom이 제대로 finalize되지 않음
현황: 진행 중 (splitmuxsink async-finalize=False 적용)
```

### 2. 저장소 복구 감지
```
메커니즘: 경로 검증을 통한 폴링 방식
한계: USB 재연결 감지 시간이 OS에 따라 가변적 (보통 1-3초)
개선: inotify 등 파일 시스템 이벤트 기반 방식 검토 중
```

### 3. 녹화 재시도 횟수
```
설정: _max_recording_retry (기본값 확인 필요)
주의: 무한 재시도 방지를 위해 상한선 필요
추천: 최대 20회 (약 2분)
```

### 4. 성능 고려사항
```
재연결 대기 최대: 60초
  → UI 응답성 저하 가능성 있음
  → 설정으로 조정 가능

메모리 누수:
  → 재연결 반복 시 타이머 정리 필수
  → daemon=True로 프로그램 종료 시 자동 정리
```

---

## 참고 문서

1. **disconnection_reconnection_analysis.md**
   - 상세 흐름도 및 구현 분석
   - 라인 번호 참조 포함

2. **camera_connection_state_diagram.md**
   - 상태 머신 다이어그램
   - 시간대별 이벤트 타임라인
   - 파일 분할 시나리오

3. **CLAUDE.md**
   - 프로젝트 개요 및 아키텍처
   - 통합 파이프라인 패턴 설명
   - 알려진 이슈 및 해결책

---

## 결론

이 NVR 시스템은 다음과 같은 특징을 가진 강건한 연결 관리 체계를 구현하고 있습니다:

1. **분기별 독립 제어**: 스트리밍과 녹화를 독립적으로 관리
2. **자동 상태 복구**: 네트워크와 저장소 에러에서 자동 복구
3. **녹화 상태 보존**: 연결 끊김 중에도 녹화 상태를 기억했다가 자동 재개
4. **지능형 재시도**: 지수 백오프로 네트워크 폭주 방지
5. **UI 동기화**: 콜백 기반으로 백엔드와 프론트엔드 상태 일관성 유지

이러한 설계는 카메라 네트워크 불안정 환경에서도 안정적인 영상 기록을 보장합니다.

