# 카메라 연결 상태 다이어그램 (State Machine)

## 1. CameraStream 연결 상태 머신

```
                    ┌──────────────────┐
                    │  DISCONNECTED    │ (초기 상태)
                    │ (status 변수 저장)│
                    └─────────┬────────┘
                              │
                              │ connect()
                              ↓
                    ┌──────────────────┐
                    │  CONNECTING      │
                    │ (gst_pipeline    │
                    │  생성 중)         │
                    └─────────┬────────┘
                              │
                    ┌─────────┴──────────┐
                    ↓                    ↓
            [성공]                   [실패]
                    ↓                    ↓
        ┌───────────────────┐  ┌──────────────┐
        │   CONNECTED       │  │    ERROR     │
        │ (gst_pipeline     │  │ (_handle_    │
        │  시작)             │  │  connection_ │
        │                   │  │  error())    │
        └────────┬──────────┘  └──────┬───────┘
                 │                    │
                 │ [네트워크 끊김]     │ [자동 재연결]
                 │                    │
        ┌────────┴────────────────────┘
        ↓
    ┌──────────────────┐
    │  RECONNECTING    │ (streaming.py라인 168)
    │ (재연결 시도)    │
    └─────────┬────────┘
              │
    ┌─────────┴──────────┐
    ↓                    ↓
[성공]              [실패 with max retries]
    ↓                    ↓
 CONNECTED        ERROR (프로그램 레벨)
                   또는 DISCONNECTED
```

---

## 2. GstPipeline 파이프라인 상태 (gst_pipeline.py)

```
                  ┌──────────────────┐
                  │   파이프라인 생성│
                  │ (create_pipeline)│
                  └────────┬─────────┘
                           │
                           ↓
                  ┌──────────────────┐
                  │  파이프라인 시작│
                  │   (start())      │
                  └────────┬─────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ↓                                     ↓
┌──────────────────┐           ┌─────────────────────┐
│  _is_playing=T   │           │  파이프라인 오류     │
│  _main_loop 실행 │           │  _on_bus_message()  │
│  BUS 모니터링    │           │                     │
└────────┬─────────┘           └────────┬────────────┘
         │                              │
         │ [에러 감지]                   │ [에러 분류]
         │                              ↓
         │                   ┌──────────────────────┐
         │                   │  _classify_error()   │
         │                   │  ErrorType 결정      │
         │                   └────────┬─────────────┘
         │                            │
         │        ┌───────────┬───────┼────────┬──────────┐
         │        ↓           ↓       ↓        ↓          ↓
         │    RTSP_     STORAGE  DISK_FULL  DECODER  VIDEO_SINK
         │    NETWORK   DISC                 ERROR     ERROR
         │    ERROR     ERROR
         │        │           ↓       ↓        ↓          ↓
         │        │      [중지]  [자동정리]  [플러시]  [Streaming
         │        │      [재시도]              중지]
         │        │
         ↓        ↓
   [재연결 처리]
   _handle_rtsp_error()
        │
        ├─→ [비동기 처리]
        │   threading.Thread()
        │
        ├─→ stop()
        │   (_is_playing=F)
        │
        ├─→ _schedule_reconnect()
        │   지수 백오프
        │
        └─→ _reconnect()
            성공 시:
            ├─→ start()
            ├─→ _notify_connection_state_change(True)
            └─→ [녹화 자동 재개]
```

---

## 3. 네트워크 재연결 상태 플로우

```
ERROR 발생
    │
    ├─→ _classify_error() = RTSP_NETWORK
    │
    └─→ threading.Thread(_async_stop_and_reconnect)
            │
            ├─→ was_recording = self._is_recording
            │   (현재 녹화 상태 저장)
            │
            ├─→ stop()
            │   ├─→ _is_playing = False
            │   ├─→ _stop_timestamp_update()
            │   ├─→ _cancel_recording_retry()
            │   ├─→ cancel reconnect_timer
            │   └─→ 파이프라인 정지
            │
            ├─→ if was_recording:
            │       _recording_should_auto_resume = True
            │
            └─→ _schedule_reconnect()
                    │
                    ├─→ [중복 방지]
                    │   if reconnect_timer.is_alive(): return
                    │
                    ├─→ [최대 재시도 체크]
                    │   if retry_count >= max_retries:
                    │       _notify_connection_state_change(False)
                    │       return
                    │
                    ├─→ [지수 백오프]
                    │   delay = min(5 * (2^retry_count), 60)
                    │   retry_count++
                    │
                    └─→ reconnect_timer = Timer(delay, _reconnect)
                            │
                            └─→ _reconnect()
                                    │
                                    ├─→ [중복 연결 방지]
                                    │   if _is_playing: return
                                    │
                                    ├─→ success = start()
                                    │
                                    ├─→ if success:
                                    │       retry_count = 0
                                    │
                                    │       if _recording_should_auto_resume:
                                    │           sleep(1.0)
                                    │           start_recording()
                                    │               │
                                    │               ├─→ 성공:
                                    │               │   _recording_should_auto_resume=F
                                    │               │
                                    │               └─→ 실패:
                                    │                   _schedule_recording_retry()
                                    │
                                    └─→ if not success:
                                            _schedule_reconnect()
                                            (무한 루프는 max_retries로 제한)
```

---

## 4. 저장소 에러 처리 상태 플로우

```
ERROR 감지
    │
    ├─→ _classify_error() = STORAGE_DISCONNECTED
    │
    └─→ _handle_storage_error()
            │
            ├─→ stop_recording(storage_error=True)
            │   ├─→ recording_valve.set_property("drop", True)
            │   ├─→ _is_recording = False
            │   └─→ [파일 정확히 finalize]
            │
            ├─→ _recording_branch_error = True
            ├─→ _recording_should_auto_resume = True
            │
            └─→ _schedule_recording_retry()
                    │
                    ├─→ _recording_retry_interval = 6초
                    ├─→ _max_recording_retry = 설정값
                    │
                    └─→ _recording_retry_timer = Timer(6, _retry_recording)
                            │
                            └─→ _retry_recording()
                                    │
                                    ├─→ [자동 재개 여부 확인]
                                    │   if not _recording_should_auto_resume:
                                    │       return
                                    │
                                    ├─→ [재시도 카운트 증가]
                                    │   _recording_retry_count++
                                    │   if > _max_recording_retry: return
                                    │
                                    ├─→ if _validate_recording_path():
                                    │       _recording_branch_error = False
                                    │       if start_recording():
                                    │           _recording_should_auto_resume=F
                                    │           return
                                    │       else:
                                    │           [재시도 타이머 재스케줄]
                                    │
                                    └─→ else: [저장소 여전히 접근 불가]
                                            [다음 재시도 스케줄]
```

---

## 5. 전체 시스템 상태 다이어그램

```
                           ┌─────────────┐
                           │  애플리케이션│
                           │    시작      │
                           └──────┬──────┘
                                  │
                                  ↓
                    ┌─────────────────────┐
                    │  CameraStream 생성   │
                    │  GstPipeline 생성   │
                    └──────────┬──────────┘
                               │
                               ↓
                    ┌─────────────────────┐
                    │   파이프라인 시작    │
                    │   (_is_playing=T)   │
                    └──────────┬──────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                          │                          │
    ↓                          ↓                          ↓
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  정상 동작   │       │  네트워크 끊김    │       │  저장소 에러     │
│ 스트리밍중   │       │  (RTSP ERROR)    │       │  (STORAGE ERROR) │
│ (옵션) 녹화  │       │                  │       │                  │
└──────────────┘       └────────┬─────────┘       └────────┬─────────┘
                                │                         │
                                ├─→ 파이프라인 전체       ├─→ 녹화만 중지
                                │   중지 및 재연결         │   스트리밍 유지
                                │   (완전 재시작)          │   자동 재시도
                                │                         │
                                ├─→ 지수 백오프           ├─→ 6초 간격 재시도
                                │   (5-60초)              │   (최대 횟수 제한)
                                │                         │
                                ├─→ 녹화 중이었으면       ├─→ 저장소 복구 시
                                │   자동 재개             │   자동 재개
                                │                         │
                                └─→ 최대 재시도           └─→ 최대 재시도
                                    초과 시 ERROR            초과 시 ERROR
                                    알림                     알림
```

---

## 6. UI 동기화 콜백 체인

```
GstPipeline 상태 변화
    │
    ├─→ _notify_connection_state_change(is_connected)
    │       │
    │       └─→ for callback in self.connection_callbacks:
    │               callback(camera_id, is_connected)
    │                   │
    │                   └─→ [MainWindow 수신]
    │                       │
    │                       ├─→ _on_camera_connected():
    │                       │   ├─→ GridView channel.set_connected(T)
    │                       │   ├─→ RecordingStatusItem.set_connected(T)
    │                       │   ├─→ PTZ Controller 활성화
    │                       │   └─→ 자동 녹화 시작
    │                       │
    │                       └─→ _on_camera_disconnected():
    │                           ├─→ GridView channel.set_connected(F)
    │                           └─→ RecordingStatusItem.set_connected(F)
    │
    └─→ _notify_recording_state_change(is_recording)
            │
            └─→ for callback in self.recording_callbacks:
                    callback(camera_id, is_recording)
                        │
                        └─→ [MainWindow 수신]
                            │
                            ├─→ on_recording_state_change(cam_id, is_rec):
                            │   ├─→ GridView channel.set_recording(is_rec)
                            │   ├─→ RecordingStatusItem.set_recording(is_rec)
                            │   ├─→ update_recording_status(cam_id, is_rec)
                            │   │
                            │   ├─→ if is_rec:
                            │   │   recording_started.emit(cam_id)
                            │   │
                            │   └─→ else:
                            │       recording_stopped.emit(cam_id)
```

---

## 7. 파일 분할 이벤트 시퀀스

```
┌─────────────────────────────────────────────────────────────┐
│ 시나리오 1: 자동 파일 회전 (max-size-time 초과)             │
└─────────────────────────────────────────────────────────────┘

splitmuxsink 시간 초과
        │
        ├─→ 내부적으로 이전 파일 finalize
        │
        ├─→ format-location 신호 발송
        │
        ├─→ _on_format_location() 핸들러 호출
        │   ├─→ 새 타임스탬프 생성
        │   ├─→ 새 파일경로 반환
        │   └─→ "recordings/cam_01/2025-11-10/cam_01_20251110_160000.mp4"
        │
        └─→ 새 파일로 계속 녹화


┌─────────────────────────────────────────────────────────────┐
│ 시나리오 2: 네트워크 재연결 시 파일 분할                     │
└─────────────────────────────────────────────────────────────┘

RTSP ERROR
        │
        ├─→ _async_stop_and_reconnect()
        │   ├─→ stop() [파이프라인 정지]
        │   │   ├─→ splitmuxsink buffer flush
        │   │   └─→ 이전 파일 finalize
        │   │
        │   └─→ _schedule_reconnect()
        │
        ├─→ [지수 백오프 대기]
        │
        ├─→ _reconnect() [파이프라인 재시작]
        │   ├─→ start()
        │   ├─→ PLAYING 상태 전환
        │   ├─→ splitmuxsink 초기화
        │   │
        │   └─→ [녹화 자동 재개]
        │       ├─→ sleep(1.0)
        │       └─→ start_recording()
        │           ├─→ format-location 신호
        │           └─→ 새 파일 시작
        │
        └─→ 결과: 
            ├─→ old_file.mp4 [이전 파일 - 정상 finalize됨]
            └─→ new_file.mp4 [새 파일 - 새로운 타임스탬프]


┌─────────────────────────────────────────────────────────────┐
│ 시나리오 3: 저장소 에러 시 파일 분할                         │
└─────────────────────────────────────────────────────────────┘

STORAGE ERROR
        │
        ├─→ _handle_storage_error()
        │   ├─→ stop_recording(storage_error=True)
        │   │   ├─→ recording_valve.set_property("drop", True)
        │   │   ├─→ [파일 강제 finalize]
        │   │   └─→ _is_recording = False
        │   │
        │   └─→ _schedule_recording_retry()
        │
        ├─→ [6초 간격 재시도]
        │
        ├─→ _retry_recording()
        │   ├─→ _validate_recording_path() [저장소 확인]
        │   │
        │   └─→ if 접근 가능:
        │       ├─→ start_recording()
        │       │   ├─→ format-location 신호
        │       │   └─→ 새 파일 시작
        │       │
        │       └─→ 결과:
        │           ├─→ old_file.mp4 [이전 파일 - 정상 finalize됨]
        │           └─→ new_file.mp4 [새 파일 - 새로운 타임스탬프]
```

---

## 8. 에러 복구 의사결정 트리

```
                          ERROR 감지
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ↓                   ↓
            _classify_error()      다른 메시지
            ErrorType 결정         (무시)
                    │
        ┌───────────┼───────────┬──────────┬──────────┐
        ↓           ↓           ↓          ↓          ↓
    RTSP_      STORAGE_   DISK_FULL  DECODER  VIDEO_
    NETWORK    DISC                  ERROR    SINK
    ERROR      ERROR                         ERROR
        │           │           │          │          │
        ↓           ↓           ↓          ↓          ↓
    [전체 중지] [녹화만 중지] [자동    [플러시] [스트리밍
    [전체 재연결] [스트리밍 유지]정리]  [무시]   중지만]
                [자동 재개]  [자동    [녹화 유지]
                타이머      재개]
                시작        타이머
                            시작
        │           │           │          │          │
        ↓           ↓           ↓          ↓          ↓
    지수        6초           복구 후   재생 계속  파이프라인
    백오프      간격          재시도   (무영향)   상태유지
    (5-60초)    재시도         타이머
    
    최대       최대 재시도   최대 재시도
    재시도     초과=FAIL    초과=FAIL
    초과=
    FAIL
```

---

## 9. 녹화 상태 전이

```
START_RECORDING() 호출
        │
        ├─→ 프리콘디션 체크
        │   ├─→ 저장소 경로 유효성
        │   ├─→ 디스크 여유 공간
        │   └─→ pipeline state = PLAYING
        │
        ├─→ recording_valve.set_property("drop", False)
        │   [recording branch 열기]
        │
        ├─→ self._is_recording = True
        │
        ├─→ format-location 신호 설정
        │   [파일명 동적 생성 준비]
        │
        └─→ _notify_recording_state_change(True)
            [UI 콜백 발송]


STOP_RECORDING(storage_error=False) 호출
        │
        ├─→ recording_valve.set_property("drop", True)
        │   [recording branch 닫기]
        │
        ├─→ self._is_recording = False
        │
        ├─→ if not storage_error:
        │       GStreamer EOS 신호
        │       [파일 graceful finalize]
        │
        └─→ _notify_recording_state_change(False)
            [UI 콜백 발송]
```

---

## 10. 시간대별 이벤트 타임라인 (예시: 네트워크 재연결)

```
Time  Event                          Action                     State
────────────────────────────────────────────────────────────────────────
0ms   ┌─────────────────────────────────────────────────────────┐
      │ 정상: 스트리밍 + 녹화 중                                 │
      │ _is_playing=T, _is_recording=T                           │
      └─────────────────────────────────────────────────────────┘

T0ms  → RTSP 네트워크 끊김 감지
      → _on_bus_message() 호출
      → ERROR 메시지 파싱

T+10ms → _classify_error() = RTSP_NETWORK
      → _handle_rtsp_error() 호출
      → threading.Thread() 시작

T+20ms → _async_stop_and_reconnect()
      → was_recording = True (저장)
      → stop() 호출
      → _is_playing = False
      → 파이프라인 정지

T+100ms → [파이프라인 정지 완료]
      → _schedule_reconnect()
      → 첫 재시도 delay = 5초 설정

T+5100ms → _reconnect() 실행
      → start() 호출
      → 파이프라인 재시작 시도

T+5200ms → [파이프라인 시작 성공]
      → _is_playing = True
      → retry_count = 0
      → _recording_should_auto_resume=T 확인

T+5300ms → sleep(1.0) [파이프라인 안정화]

T+6300ms → start_recording()
      → recording_valve 열기
      → _is_recording = True
      → format-location 신호

T+6350ms → [녹화 재개 완료]
      → _notify_recording_state_change(True)
      → UI 콜백 발송

T+6400ms → ┌─────────────────────────────────────────────────────┐
      │ 복구: 스트리밍 + 녹화 재개 (파일 분할됨)                 │
      │ _is_playing=T, _is_recording=T                           │
      │ new_file.mp4 시작됨                                      │
      └─────────────────────────────────────────────────────────┘
```

