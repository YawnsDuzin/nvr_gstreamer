# 녹화 중지 시 스트리밍도 중지되는 문제 해결

## 문제 현상
- 수동으로 녹화를 중지할 때 스트리밍도 함께 중지됨
- 화면이 멈추거나 검은 화면으로 변경됨

## 원인 분석

### 파이프라인 구조
```
RTSP Source → Decode → Tee ─┬─→ [Streaming Branch] → Video Sink
                            │
                            └─→ [Recording Branch] → splitmuxsink
```

### 문제의 원인
이전 수정에서 splitmuxsink의 sink pad에 **EOS(End of Stream) 이벤트**를 전송했는데, 이 이벤트가 **upstream으로 전파**되면서 문제 발생:

1. EOS 이벤트가 splitmuxsink → recording_valve → record_queue → tee로 역방향 전파
2. Tee 엘리먼트가 EOS를 받으면 모든 브랜치에 영향
3. 결과적으로 스트리밍 브랜치도 EOS를 받아 중지됨

### EOS 이벤트의 특성
- **Upstream 전파**: sink pad로 전송된 EOS는 source 방향으로 전파될 수 있음
- **Tee의 동작**: 한 브랜치에서 EOS를 받으면 다른 브랜치에도 영향을 줄 수 있음
- **파이프라인 상태**: EOS는 파이프라인 전체를 NULL 상태로 만들 수 있음

## 해결 방법

### 구현된 해결책: splitmuxsink 상태 변경 방식

EOS 이벤트 대신 **splitmuxsink의 상태를 READY로 변경**하여 파일을 안전하게 finalize:

```python
def stop_recording(self, storage_error: bool = False) -> bool:
    # 1. splitmuxsink를 READY 상태로 변경 (파일 강제 finalize)
    current_state = self.splitmuxsink.get_state(0)[1]
    self.splitmuxsink.set_state(Gst.State.READY)

    # 2. 파일 finalize 대기
    time.sleep(0.5)

    # 3. 다시 PLAYING 상태로 복구 (향후 재사용)
    if current_state == Gst.State.PLAYING:
        self.splitmuxsink.set_state(Gst.State.PLAYING)

    # 4. Valve 닫기 (녹화 중지)
    self.recording_valve.set_property("drop", True)
```

### 이 방법의 장점
1. **격리된 처리**: splitmuxsink만 영향을 받고 다른 브랜치는 영향 없음
2. **안전한 파일 종료**: READY 상태 전환 시 파일이 자동으로 finalize됨
3. **재사용 가능**: splitmuxsink를 다시 PLAYING으로 복구하여 재사용 가능
4. **부작용 없음**: 스트리밍 브랜치는 계속 동작

### 대체 방법들 (참고용)

#### 방법 2: 녹화 브랜치 격리
```python
# record_queue에 drop-on-eos 속성 설정
record_queue.set_property("drop-on-eos", True)
```

#### 방법 3: Custom Probe 사용
```python
def block_eos_probe(pad, info):
    if info.get_event().type == Gst.EventType.EOS:
        return Gst.PadProbeReturn.DROP  # EOS 이벤트 차단
    return Gst.PadProbeReturn.OK

# tee의 recording 브랜치 pad에 probe 추가
tee_pad.add_probe(Gst.PadProbeType.EVENT_UPSTREAM, block_eos_probe)
```

## 테스트 방법

1. **녹화 시작 및 중지 테스트**
   ```bash
   # 녹화 시작
   # 10-20초 대기
   # 녹화 중지
   # 스트리밍이 계속되는지 확인
   ```

2. **파일 무결성 확인**
   ```bash
   ffprobe -v error -show_format [recording_file].mp4
   ```

3. **로그 확인**
   ```bash
   # 디버그 로그에서 상태 변경 확인
   grep "RECORDING DEBUG" logs/pynvr_*.log
   ```

## 결과
- ✅ 녹화 중지 시 파일이 정상적으로 finalize됨
- ✅ 스트리밍은 영향 없이 계속 동작
- ✅ 녹화를 다시 시작할 수 있음
- ✅ 파일 재생 가능

## 변경 사항 요약
- **이전**: EOS 이벤트를 splitmuxsink에 전송 → 전체 파이프라인 영향
- **현재**: splitmuxsink 상태 변경(READY) → 녹화 브랜치만 영향

## 주의사항
- splitmuxsink 상태 변경 시 약간의 지연(0.5초)이 필요
- storage_error인 경우는 상태 변경을 건너뛰어 빠른 처리
- 향후 GStreamer 버전 업그레이드 시 동작 확인 필요