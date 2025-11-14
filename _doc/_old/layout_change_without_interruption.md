# 레이아웃 변경 시 스트리밍/녹화 중단 없는 구현

## 개요
레이아웃 변경 시 기존에는 모든 ChannelWidget을 삭제하고 재생성하여 파이프라인이 재시작되었으나,
위젯을 재사용하는 방식으로 개선하여 스트리밍과 녹화가 중단 없이 계속되도록 수정함.

## 변경 날짜
2025-11-12

## 문제점
### 기존 구조의 문제
1. 레이아웃 변경 시 모든 ChannelWidget 삭제 → 재생성
2. 새 위젯 = 새 window handle = 파이프라인 재시작 필요
3. 300ms 이상의 스트리밍 중단 발생
4. 녹화 중인 파일이 일시적으로 중단됨

## 해결 방법

### 1. ChannelWidget 재사용 (grid_view.py)

#### 기존 방식
```python
def set_layout(self, rows, cols):
    # 모든 채널 삭제
    for channel in self.channels:
        channel.deleteLater()
    self.channels.clear()

    # 새 채널 생성
    for i in range(rows * cols):
        channel = ChannelWidget(...)
        self.channels.append(channel)
```

#### 개선된 방식
```python
def set_layout(self, rows, cols):
    needed_channels = rows * cols
    current_channels = len(self.channels)

    # 모든 채널을 grid에서만 제거 (위젯 유지)
    for channel in self.channels:
        self.grid_layout.removeWidget(channel)
        channel.hide()

    # 부족한 채널만 추가 생성
    if needed_channels > current_channels:
        for i in range(current_channels, needed_channels):
            channel = ChannelWidget(i, f"cam_{i}", f"Camera {i + 1}")
            self.channels.append(channel)

    # 필요한 채널만 재배치
    for i in range(needed_channels):
        channel = self.channels[i]
        channel.channel_index = i
        self.grid_layout.addWidget(channel, i // cols, i % cols)
        channel.show()
```

### 2. 파이프라인 유지 (main_window.py)

#### 기존 방식
```python
def _update_window_handles_after_layout_change(self):
    # 모든 스트림 정지
    for stream in connected_streams:
        stream.disconnect()

    # 300ms 후 재연결
    QTimer.singleShot(300, reconnect_streams)
```

#### 개선된 방식
```python
def _update_window_handles_after_layout_change(self):
    for i, camera in enumerate(cameras):
        channel = self.grid_view.get_channel(i)
        stream = self.camera_list.get_camera_stream(camera.camera_id)

        if stream and stream.is_connected():
            # 파이프라인 유지하면서 window handle만 업데이트
            new_window_handle = channel.get_window_handle()
            stream.gst_pipeline.video_sink.set_window_handle(int(new_window_handle))
```

## 장점

1. **무중단 스트리밍**
   - 레이아웃 변경 시에도 비디오 스트림 유지
   - 사용자 경험 향상

2. **녹화 연속성**
   - 녹화 중인 파일이 중단되지 않음
   - 파일 무결성 보장

3. **리소스 효율성**
   - 불필요한 위젯 생성/삭제 없음
   - 메모리 사용량 최적화
   - GStreamer 파이프라인 재생성 비용 절감

4. **빠른 레이아웃 전환**
   - 300ms 지연 없음
   - 즉각적인 UI 반응

## 구현 세부사항

### 위젯 풀 관리
- 최대 16개(4x4) 채널 위젯을 메모리에 유지
- 필요한 채널만 표시, 나머지는 숨김
- Window handle은 위젯이 숨겨져도 유효

### 예외 처리
- Window handle 업데이트 실패 시에만 파이프라인 재시작
- 대부분의 경우 handle 업데이트만으로 충분

## 테스트 방법

```bash
# 1. 카메라 연결 및 녹화 시작
python main.py --debug

# 2. 레이아웃 변경 테스트
# View 메뉴 > Layout > 2x2, 3x3, 4x4 전환

# 3. 확인 사항
# - 비디오 스트림 중단 없음
# - 녹화 파일 연속성
# - CPU/메모리 사용량 변화 없음
```

## 추가 개선 가능 사항

1. **Headless Pipeline 구조**
   - GStreamer 파이프라인과 UI 완전 분리
   - appsink + Qt 렌더링 방식

2. **Multi-Process 구조**
   - 스트리밍/녹화를 별도 프로세스에서 처리
   - SharedMemory로 프레임 공유

3. **오버레이 윈도우**
   - 투명 오버레이로 비디오 렌더링
   - 레이아웃과 독립적인 비디오 표시

## 관련 파일
- `ui/grid_view.py`: set_layout() 메서드
- `ui/main_window.py`: _update_window_handles_after_layout_change() 메서드
- `ui/video_widget.py`: StreamVideoWidget (window handle 관리)