# 수동 녹화 종료 시 파일 재생 문제 분석 및 해결 방안

## 문제 현상
- 수동으로 녹화를 종료할 때 생성된 파일이 재생되지 않음
- splitmuxsink에 의해 자동 분할 완료된 파일만 정상 재생됨

## 원인 분석

### 1. 현재 녹화 종료 처리 방식
```python
def stop_recording(self, storage_error: bool = False) -> bool:
    # 1. Valve 닫기 (녹화 데이터 흐름 차단)
    self.recording_valve.set_property("drop", True)

    # 2. split-now 신호 발생 시도
    self.splitmuxsink.emit("split-now")

    # 3. 대기 시간
    time.sleep(0.5)  # 파일 완료 대기
```

### 2. 문제점 식별

#### 2.1 MP4 파일 구조 문제
- **MP4 포맷의 특성**: MP4는 파일 끝에 moov atom(메타데이터)이 필요
- **현재 설정**: `streamable=true`로 설정되어 있음
  ```python
  muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=true")
  ```
- **streamable=true의 영향**:
  - moov atom을 파일 앞쪽에 배치하여 스트리밍 가능하게 함
  - 하지만 파일이 제대로 닫히지 않으면 moov atom이 불완전할 수 있음

#### 2.2 split-now 신호의 한계
- `split-now` 신호는 현재 GOP(Group of Pictures)가 끝난 후 파일을 분할
- 키프레임이 오기 전까지 대기할 수 있음
- valve를 먼저 닫으면 새로운 데이터가 들어오지 않아 split-now가 제대로 동작하지 않을 수 있음

#### 2.3 EOS(End of Stream) 처리 부재
- 현재 코드는 split-now 실패 시 EOS를 보내지만, 이미 valve가 닫힌 상태
- splitmuxsink가 정상적으로 파일을 마무리하지 못함

### 3. 자동 분할된 파일이 정상 재생되는 이유
- `max-size-time` 속성에 의해 자동 분할될 때는:
  1. 키프레임 경계에서 자연스럽게 분할
  2. 새 파일이 시작되면서 이전 파일이 자동으로 finalize됨
  3. moov atom이 올바르게 기록됨

## 해결 방안

### 방안 1: EOS 이벤트를 먼저 전송 (권장)
```python
def stop_recording(self, storage_error: bool = False) -> bool:
    if not self._is_recording:
        return False

    try:
        logger.info(f"Stopping recording for {self.camera_name}...")

        # 1. splitmuxsink에 EOS 신호 전송 (valve를 닫기 전에)
        if self.splitmuxsink and not storage_error:
            # splitmuxsink의 sink pad에 EOS 전송
            pad = self.splitmuxsink.get_static_pad("video")
            if not pad:
                pad = self.splitmuxsink.get_static_pad("sink")

            if pad:
                pad.send_event(Gst.Event.new_eos())
                logger.debug("[RECORDING DEBUG] Sent EOS event to splitmuxsink")

                # EOS 처리 대기 (파일 finalize)
                time.sleep(1.0)  # 충분한 시간 대기

        # 2. Valve 닫기 (녹화 중지)
        if self.recording_valve:
            self.recording_valve.set_property("drop", True)
            logger.debug("[RECORDING DEBUG] Recording valve closed")

        # 3. 상태 업데이트
        self._is_recording = False
        # ... 나머지 코드
```

### 방안 2: async-finalize 속성 사용
```python
def _create_recording_branch(self):
    # splitmuxsink 생성 및 설정
    self.splitmuxsink = Gst.ElementFactory.make("splitmuxsink", "splitmuxsink")

    # async-finalize 활성화 (파일 finalize를 비동기로 처리)
    self.splitmuxsink.set_property("async-finalize", True)
    self.splitmuxsink.set_property("async-handling", True)

    # muxer-properties 수정 (streamable 제거)
    if self.file_format == 'mp4':
        # streamable=false로 변경하여 완전한 moov atom 보장
        muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=false")
        self.splitmuxsink.set_property("muxer-properties", muxer_props)
```

### 방안 3: 강제 파일 finalize (Force Key Unit)
```python
def stop_recording(self, storage_error: bool = False) -> bool:
    if not self._is_recording:
        return False

    try:
        logger.info(f"Stopping recording for {self.camera_name}...")

        # 1. 강제 키프레임 요청
        if self.splitmuxsink and not storage_error:
            # Force Key Unit 이벤트 전송
            event = GstVideo.video_event_new_downstream_force_key_unit(
                Gst.CLOCK_TIME_NONE,  # timestamp
                Gst.CLOCK_TIME_NONE,  # stream_time
                Gst.CLOCK_TIME_NONE,  # running_time
                True,                 # all_headers
                0                     # count
            )

            pad = self.splitmuxsink.get_static_pad("sink")
            if pad:
                pad.send_event(event)
                logger.debug("[RECORDING DEBUG] Sent force-key-unit event")
                time.sleep(0.5)  # 키프레임 생성 대기

            # 2. split-now 신호 발생
            self.splitmuxsink.emit("split-now")
            time.sleep(1.0)  # 파일 완료 대기

        # 3. Valve 닫기
        if self.recording_valve:
            self.recording_valve.set_property("drop", True)
```

### 방안 4: splitmuxsink 대신 마지막 파일 수동 finalize
```python
def stop_recording(self, storage_error: bool = False) -> bool:
    if not self._is_recording:
        return False

    try:
        # 1. 현재 녹화 파일 경로 저장
        last_file = self.current_recording_file

        # 2. Valve만 닫기 (간단하게)
        if self.recording_valve:
            self.recording_valve.set_property("drop", True)

        # 3. splitmuxsink를 READY 상태로 변경 (파일 강제 닫기)
        if self.splitmuxsink:
            self.splitmuxsink.set_state(Gst.State.READY)
            time.sleep(0.5)
            self.splitmuxsink.set_state(Gst.State.PLAYING)

        # 4. 필요시 파일 복구 (qtmux recovery)
        if last_file and os.path.exists(last_file):
            # ffmpeg를 사용한 파일 복구 (선택적)
            recovery_cmd = f"ffmpeg -i {last_file} -c copy -movflags +faststart {last_file}.fixed.mp4"
            # subprocess.run(recovery_cmd, shell=True)
```

## 권장 해결책

**방안 1 (EOS 우선 전송)**을 우선 적용하는 것을 권장합니다:

1. **구현이 간단**: 기존 코드 수정 최소화
2. **GStreamer 표준 방식**: EOS는 파일을 정상적으로 닫는 표준 방법
3. **부작용 최소**: 다른 기능에 영향 없음

추가로 **방안 2의 streamable=false** 설정도 고려할 수 있습니다:
- 파일 완성도가 더 높아짐
- 단, 스트리밍 재생은 불가능해짐 (전체 파일 다운로드 필요)

## 테스트 방법

1. 녹화 시작
2. 10-20초 후 수동으로 녹화 중지
3. 생성된 파일을 VLC, ffplay 등으로 재생 테스트
4. ffprobe로 파일 무결성 확인:
   ```bash
   ffprobe -v error -show_format recording_file.mp4
   ```

## 디버깅 팁

GStreamer 디버깅 활성화:
```bash
GST_DEBUG=splitmuxsink:5,mp4mux:5 python main.py
```

파일 메타데이터 확인:
```bash
# MP4 atom 구조 확인
mp4info recording_file.mp4

# 파일 복구 시도
ffmpeg -i broken_file.mp4 -c copy -movflags +faststart fixed_file.mp4
```