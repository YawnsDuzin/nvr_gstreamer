# 카메라 연결 끊김 및 재연결 처리 흐름도 분석

## 1. 에러 감지 및 분류 단계

### 1.1 GStreamer 버스 메시지 처리
```
GStreamer Pipeline ERROR Event
                  ↓
        _on_bus_message() [라인 995]
                  ↓
    ┌─────────────┴─────────────┐
    ↓                           ↓
ERROR 메시지 파싱         다른 메시지 무시
- src_name 확인              (EOS, STATE_CHANGED,
- error_code 확인             BUFFERING, WARNING)
- debug info 추출
```

### 1.2 에러 타입 분류 (우선순위)
```
_classify_error() [라인 1064]
     ↓
┌────────────────────────────────────────┐
│ 1순위: GStreamer 에러 도메인 확인      │
│   - Gst.ResourceError                  │
│   - Gst.StreamError                    │
│   - Gst.CoreError                      │
└────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────┐
│ 2순위: 소스 엘리먼트 이름 기반 분류     │
│   - source → RTSP_NETWORK              │
│   - sink/splitmuxsink → STORAGE        │
│   - decoder → DECODER                  │
└────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────┐
│ 3순위: 에러 메시지 문자열 분석          │
│   - "no space" → DISK_FULL             │
│   - "decode" → DECODER                 │
│   - "output window" → VIDEO_SINK       │
└────────────────────────────────────────┘
     ↓
Return ErrorType enum값
  - ErrorType.RTSP_NETWORK
  - ErrorType.STORAGE_DISCONNECTED
  - ErrorType.DISK_FULL
  - ErrorType.DECODER
  - ErrorType.VIDEO_SINK
  - ErrorType.UNKNOWN
```

---

## 2. NETWORK ERROR 처리 흐름 (RTSP 연결 끊김)

```
ERROR 감지
    ↓
_classify_error() → ErrorType.RTSP_NETWORK
    ↓
_handle_rtsp_error() [라인 1191]
    │
    ├─→ [GLib 스레드 문제 해결]
    │   GLib 메인 루프에서 직접 stop() 호출 불가
    │   → 별도 스레드로 비동기 처리
    │
    └─→ threading.Thread(target=_async_stop_and_reconnect)
            ↓
        _async_stop_and_reconnect() [라인 1306]
            ├─→ was_recording = self._is_recording 저장
            │   (재연결 후 녹화 자동 재개 판단용)
            │
            ├─→ self.stop() [라인 1314]
            │   파이프라인 정지
            │
            ├─→ if was_recording:
            │       self._recording_should_auto_resume = True
            │   (녹화 중이었으면 재연결 후 자동 재개)
            │
            └─→ _schedule_reconnect()
                    ↓
                _schedule_reconnect() [라인 1324]
                    ├─→ 중복 방지 체크
                    │   (이미 타이머 실행 중이면 무시)
                    │
                    ├─→ 최대 재시도 횟수 초과 체크
                    │   if retry_count >= max_retries:
                    │       _notify_connection_state_change(False)
                    │       return ERROR 상태
                    │
                    ├─→ 지수 백오프 계산
                    │   delay = min(5 * (2 ** retry_count), 60)
                    │   예: 1차 5s, 2차 10s, 3차 20s, ..., 최대 60s
                    │
                    └─→ reconnect_timer 시작
                            Timer(delay, _reconnect)
                                ↓
                            _reconnect() [라인 1355]
                                ├─→ 이미 연결된 상태면 무시
                                │   (중복 실행 방지)
                                │
                                ├─→ success = self.start()
                                │   파이프라인 재시작 시도
                                │
                                ├─→ if success:
                                │       retry_count = 0 초기화
                                │
                                │       if _recording_should_auto_resume:
                                │           sleep(1.0)  [파이프라인 안정화]
                                │           start_recording()
                                │               ├─→ 성공 시:
                                │               │   _recording_should_auto_resume = False
                                │               └─→ 실패 시:
                                │                   _schedule_recording_retry()
                                │
                                └─→ if not success:
                                        _schedule_reconnect()
                                        (무한 재시도는 max_retries로 제한됨)
```

---

## 3. STORAGE ERROR 처리 흐름 (USB 분리)

```
ERROR 감지
    ↓
_classify_error() → ErrorType.STORAGE_DISCONNECTED
    ↓
_handle_storage_error() [라인 1200]
    │
    ├─→ [스트리밍 유지 + 녹화만 중지]
    │   스트리밍은 계속 동작
    │   녹화 branch만 중지
    │
    ├─→ stop_recording(storage_error=True)
    │   [라인 1205]
    │   ├─→ recording_valve.set_property("drop", True)
    │   ├─→ self._is_recording = False
    │   └─→ storage_error=True로 split-now 신호 건너뜀
    │
    ├─→ self._recording_branch_error = True
    │   (에러 플래그 설정)
    │
    ├─→ self._recording_should_auto_resume = True
    │   (USB 복구 시 녹화 자동 재개)
    │
    └─→ _schedule_recording_retry() [라인 1393]
            ├─→ 타이머 중복 확인
            │   (이미 실행 중이면 무시)
            │
            └─→ _recording_retry_timer 시작
                    ↓
                _retry_recording() [라인 1413]
                    ├─→ _recording_retry_count++ (최대 _max_recording_retry)
                    │
                    ├─→ if _validate_recording_path():
                    │       [저장소 경로 접근 가능 확인]
                    │       ├─→ _recording_branch_error = False
                    │       ├─→ start_recording()
                    │       │   ├─→ 성공: _recording_should_auto_resume = False
                    │       │   └─→ 실패: 재시도 타이머 재스케줄링
                    │       └─→ return
                    │
                    └─→ else:
                            저장소 여전히 접근 불가
                            → 다음 재시도 타이머 스케줄링
                            (interval: 6초, max attempts: 설정값)
```

---

## 4. DISK FULL 처리 흐름

```
ERROR 감지
    ↓
_classify_error() → ErrorType.DISK_FULL
    ↓
_handle_disk_full_error() → _handle_disk_full() [라인 1225]
    │
    ├─→ 녹화 중지
    │   stop_recording()
    │
    ├─→ StorageService 자동 정리
    │   ├─→ auto_cleanup(max_age_days=7, min_free_space_gb=2.0)
    │   └─→ deleted_count 로그
    │
    ├─→ sleep(1.0) [정리 완료 대기]
    │
    ├─→ get_free_space_gb() [여유 공간 재확인]
    │
    └─→ if free_gb >= 2.0:
            ├─→ _recording_should_auto_resume = True
            └─→ _schedule_recording_retry()
        else:
            └─→ _notify_recording_state_change(False) [UI 알림]
```

---

## 5. 녹화 상태 유지 및 재개 메커니즘

```
┌─────────────────────────────────────────────────────┐
│ 네트워크 연결 끊김 감지                              │
│ ErrorType.RTSP_NETWORK → _handle_rtsp_error()      │
└─────────────────────────────────────────────────────┘
                        ↓
        was_recording = self._is_recording
        (재연결 전에 현재 상태 저장)
                        ↓
            [파이프라인 정지]
            self.stop()
                        ↓
            if was_recording:
                _recording_should_auto_resume = True
                        ↓
        [재연결 시도]
        _schedule_reconnect() → 지수 백오프
                        ↓
        _reconnect() 성공
                        ↓
            self._is_playing = True
            파이프라인 시작됨
                        ↓
            if _recording_should_auto_resume:
                sleep(1.0)  [파이프라인 안정화 대기]
                start_recording()
                        ↓
                ├─→ success:
                │   _recording_should_auto_resume = False
                │   [녹화 자동 재개 완료]
                │
                └─→ failed:
                    _schedule_recording_retry()
                    [녹화 재시도 타이머 시작]
```

---

## 6. 파일 분할(Split) 처리

### 6.1 자동 파일 회전 (splitmuxsink)
```
splitmuxsink 설정
├─→ max-size-time: 파일 최대 지속 시간
├─→ format-location: 파일명 동적 생성 핸들러
└─→ async-finalize: FALSE (파일 강제 finalize)

파일 회전 발생
        ↓
format-location 신호
        ↓
_on_format_location() 콜백
        ↓
새 파일명 생성
├─→ 디렉토리: recordings/{camera_id}/{date}/
└─→ 파일명: {camera_id}_{timestamp}.mp4
```

### 6.2 네트워크 재연결 시 파일 분할
```
재연결 감지
        ↓
파이프라인 PLAYING 상태 재시작
        ↓
splitmuxsink 내부 buffer 플러시
        ↓
새로운 파일로 녹화 시작
        ↓
결과: 분할된 파일
  - {camera_id}_{old_timestamp}.mp4 [이전 파일]
  - {camera_id}_{new_timestamp}.mp4 [새 파일]
```

---

## 7. UI 동기화 메커니즘

### 7.1 연결 상태 콜백
```
_notify_connection_state_change(is_connected) [라인 1567]
        ↓
    for callback in self.connection_callbacks:
        callback(self.camera_id, is_connected)
        ↓
    [MainWindow._on_camera_connected / _on_camera_disconnected]
        ├─→ GridView channel 상태 업데이트
        ├─→ RecordingStatusItem 상태 업데이트
        └─→ PTZ Controller 재생성
```

### 7.2 녹화 상태 콜백
```
_notify_recording_state_change(is_recording) [라인 1260]
        ↓
    for callback in self.recording_callbacks:
        callback(self.camera_id, is_recording)
        ↓
    [MainWindow 콜백]
        ├─→ GridView channel recording indicator 업데이트
        ├─→ RecordingStatusItem recording button 상태 업데이트
        └─→ recording_started/recording_stopped 신호 발송
```

---

## 8. CameraStream 클래스의 재연결 로직

```
CameraStream.reconnect() [라인 157]
        ↓
    status = StreamStatus.RECONNECTING
        ↓
    disconnect()
        ├─→ 스토리지 에러 콜백 해제
        └─→ gst_pipeline.stop()
        ↓
    time.sleep(config.reconnect_delay)
        [설정된 지연 시간]
        ↓
    connect(enable_recording=enable_recording)
        ├─→ gst_pipeline 생성
        ├─→ gst_pipeline.start()
        ├─→ status = StreamStatus.CONNECTED
        └─→ 스토리지 에러 콜백 재등록
```

---

## 9. 에러 상황별 처리 요약 테이블

| 에러 타입 | 감지 위치 | 처리 방식 | 스트리밍 | 녹화 | 자동 재개 |
|----------|---------|---------|-------|------|---------|
| RTSP_NETWORK | source 엘리먼트 | 전체 재연결 | 중지 | 중지 | 자동 |
| STORAGE_DISCONNECTED | sink/splitmuxsink | 녹화만 중지 | 계속 | 중지 | 자동 |
| DISK_FULL | splitmuxsink | 자동 정리 후 재개 | 계속 | 중지 | 자동 |
| DECODER | decoder 엘리먼트 | 버퍼 플러시 | 계속 | 계속 | 해당 없음 |
| VIDEO_SINK | videosink 엘리먼트 | 스트리밍 중지 | 중지 | 계속 | 해당 없음 |

---

## 10. 최대 재시도 및 타임아웃 설정

### 10.1 네트워크 재연결
- 최대 재시도: `max_retries` (기본값 확인 필요)
- 지수 백오프: 5s, 10s, 20s, ..., 최대 60s
- 방지: 중복 타이머, 이미 연결된 상태 체크

### 10.2 녹화 재시도
- 재시도 간격: `_recording_retry_interval` (기본값 6초)
- 최대 재시도: `_max_recording_retry`
- 트리거: 스토리지 에러, 디스크 Full, 녹화 실패

---

## 11. 주요 플래그 및 상태 변수

```
self._is_playing                    : 파이프라인 실행 여부
self._is_recording                  : 녹화 진행 여부
self._recording_should_auto_resume  : 재연결 후 녹화 자동 재개 플래그
self._recording_branch_error        : 녹화 branch 에러 플래그
self._streaming_branch_error        : 스트리밍 branch 에러 플래그
self._is_streaming                  : 스트리밍 진행 여부
self.retry_count                    : 네트워크 재연결 시도 횟수
self._recording_retry_count         : 녹화 재시도 횟수
self.reconnect_timer                : 네트워크 재연결 타이머
self._recording_retry_timer         : 녹화 재시도 타이머
```

---

## 12. 중요 설계 특징

### 12.1 Unified Pipeline Architecture
- 단일 파이프라인: Decode → Tee → [Streaming | Recording]
- Valve 기반 제어: 실시간 모드 전환 가능
- CPU 효율성: 50% 감소

### 12.2 Branch 독립 제어
```
┌─────────────────────────────────────┐
│ Streaming Branch                    │
│ [streaming_valve] → video_sink      │
│ 오류 시: 중지만 진행                │
└─────────────────────────────────────┘
                  ↑
                RTSP Source ← Decode ← Tee
                  ↓
┌─────────────────────────────────────┐
│ Recording Branch                    │
│ [recording_valve] → splitmuxsink    │
│ 오류 시: 중지 후 자동 재개          │
└─────────────────────────────────────┘
```

### 12.3 스레드 안전성
- GLib MainLoop에서 stop() 호출 불가
- 비동기 처리를 위해 별도 스레드 사용
- 타이머: daemon=True로 설정

---

## 13. 로깅 및 디버깅

### 관련 로그 태그
```
[RTSP]          - RTSP 연결 문제
[RECONNECT]     - 네트워크 재연결 진행
[STORAGE]       - 저장소 에러
[RECORDING]     - 녹화 상태 변화
[DISK]          - 디스크 공간 문제
[DECODER]       - 디코딩 에러
[VIDEOSINK]     - 비디오 출력 에러
[BUFFERING]     - 네트워크 버퍼링
[CONNECTION SYNC] - 연결 상태 UI 동기화
[UI SYNC]       - 녹화 상태 UI 동기화
```

---

## 14. 알려진 제한사항 및 주의사항

1. **PyQt5/GStreamer 버전 호환성**
   - PyQt5 필수 (requirements.txt에서 수정)
   - GStreamer 1.0 필수

2. **저장소 재시도 메커니즘**
   - USB 재연결 감지: 경로 검증을 통한 폴링
   - 자동 재개: 최대 재시도 횟수 제한됨

3. **파일 분할 신뢰성**
   - 네트워크 재연결 시 파일이 자동으로 분할됨
   - splitmuxsink는 내부적으로 mp4mux/matroskamux 사용

4. **성능 고려사항**
   - 재연결 최대 대기: 60초
   - 녹화 재시도: 6초 간격
   - 파이프라인 안정화: 1초 대기

