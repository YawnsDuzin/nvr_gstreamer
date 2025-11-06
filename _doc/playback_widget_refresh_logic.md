# PlaybackWidget 새로고침 자동시작 처리 로직

## 개요
PlaybackWidget의 녹화 파일 목록 새로고침이 프로그램 시작 시 자동으로 실행되는 로직을 정리한 문서입니다.

## 현재 상태
- **자동 새로고침 비활성화됨** (주석 처리)
- 수동 새로고침만 가능한 상태

## 코드 구조

### 1. PlaybackWidget 초기화 (`ui/playback_widget.py`)

```python
class PlaybackWidget(ThemedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.playback_manager = PlaybackManager()
        self.scan_thread = None  # 스캔 스레드
        self.init_ui()
        self.setup_connections()

        # 초기 스캔 및 카메라 목록 초기화
        # QTimer.singleShot(100, self._initial_scan)  # ← 주석 처리됨 (라인 606)
```

**핵심 포인트:**
- 라인 606에서 `_initial_scan` 호출이 주석 처리되어 자동 시작 비활성화
- `QTimer.singleShot(100, ...)`: 100ms 후 한 번만 실행하는 타이머

### 2. 초기 스캔 메서드 (`_initial_scan`)

```python
def _initial_scan(self):
    """초기 스캔 (카메라 목록 초기화)"""
    # 전체 파일 스캔 (필터 없음) - 동기 방식 (카메라 목록 구성용)
    self.playback_manager.scan_recordings(
        camera_id=None,
        start_date=None,
        end_date=None
    )

    # 카메라 목록 업데이트
    files = self.playback_manager.recording_files
    camera_ids = [f.camera_id for f in files]
    self.file_list.update_camera_list(camera_ids)

    # 필터 적용하여 재스캔 (비동기)
    self.scan_recordings()
```

**동작 순서:**
1. 전체 파일을 동기 방식으로 스캔
2. 카메라 목록 구성
3. 필터를 적용한 비동기 스캔 시작

### 3. 실제 새로고침 트리거 경로

#### 경로 1: Playback Dock 열릴 때
```python
# ui/main_window.py (라인 1138-1143)
def _toggle_playback_dock(self, checked: bool):
    """Toggle playback dock visibility"""
    self.playback_dock.setVisible(checked)
    if checked:
        # 재생 독이 열릴 때 녹화 파일 스캔
        self.playback_widget.scan_recordings()
```

#### 경로 2: 재생 모드 열기
```python
# ui/main_window.py (라인 1169-1186)
def _open_playback_mode(self):
    """재생 모드 열기"""
    self.playback_dock.show()
    self.camera_list._disconnect_all()  # 카메라 연결 해제
    self.playback_widget.scan_recordings()  # 녹화 파일 스캔
```

#### 경로 3: F5 키 단축키
```python
# ui/main_window.py (라인 1217-1221)
def _refresh_recordings(self):
    """녹화 파일 목록 새로고침"""
    if self.playback_widget:
        self.playback_widget.scan_recordings()
```

#### 경로 4: 새로고침 버튼 클릭
```python
# ui/playback_widget.py (라인 386-387, 583-589)
self.refresh_button = QPushButton("새로고침")
self.refresh_button.clicked.connect(self.refresh_list)

def refresh_list(self):
    """목록 새로고침"""
    parent_widget = self.parent()
    while parent_widget is not None:
        if isinstance(parent_widget, PlaybackWidget):
            parent_widget.scan_recordings()
```

### 4. Dock 초기 상태 설정

```python
# ui/main_window.py (_load_dock_state 메서드)
def _load_dock_state(self):
    dock_state = self.config_manager.ui_config.dock_state
    playback_visible = dock_state.get("playback_visible", False)  # 기본값: False
    self.playback_dock.setVisible(playback_visible)
```

**중요:**
- Playback dock의 기본 가시성은 `False`
- 프로그램 시작 시 숨겨진 상태

## 새로고침 실행 시나리오

### 시나리오 1: 프로그램 시작 시 (현재)
1. PlaybackWidget 생성됨
2. `_initial_scan` 호출 안 됨 (주석 처리)
3. Playback dock 숨겨진 상태 (기본값)
4. **결과: 자동 새로고침 없음**

### 시나리오 2: 사용자가 Playback Dock 열 때
1. View 메뉴 → Playback 선택
2. `_toggle_playback_dock(True)` 호출
3. `scan_recordings()` 실행
4. **결과: 첫 새로고침 실행**

### 시나리오 3: F5 키 또는 새로고침 버튼
1. 사용자가 F5 키 누름 또는 버튼 클릭
2. `scan_recordings()` 실행
3. **결과: 수동 새로고침**

## scan_recordings 메서드 동작

```python
def scan_recordings(self):
    """녹화 파일 스캔 (필터 적용) - 비동기"""
    # 이미 스캔 중이면 무시
    if self.scan_thread and self.scan_thread.isRunning():
        return

    # UI에서 필터 조건 가져오기
    camera_id = self.file_list.camera_combo.currentText()
    start_date = self.file_list.start_date.date().toPyDate()
    end_date = self.file_list.end_date.date().toPyDate()

    # 비동기 스캔 스레드 시작
    self.scan_thread = RecordingScanThread(...)
    self.scan_thread.start()
```

**특징:**
- 비동기 처리 (별도 스레드)
- 중복 실행 방지
- UI 필터 조건 적용

## 자동 시작 활성화 방법

### 방법 1: 초기 스캔 주석 해제
```python
# ui/playback_widget.py 라인 606
QTimer.singleShot(100, self._initial_scan)  # 주석 해제
```

### 방법 2: Dock 기본 가시성 변경
```json
// IT_RNVR.json
{
  "ui": {
    "dock_state": {
      "playback_visible": true  // false → true
    }
  }
}
```

### 방법 3: 프로그램 시작 시 강제 스캔
```python
# ui/main_window.py __init__ 메서드 끝
if self.config_manager.ui_config.auto_scan_on_start:
    QTimer.singleShot(500, lambda: self.playback_widget.scan_recordings())
```

## 성능 고려사항

### 현재 방식의 장점
- 프로그램 시작이 빠름
- 불필요한 디스크 I/O 없음
- 사용자가 필요할 때만 스캔

### 자동 시작의 단점
- 프로그램 시작 지연
- 녹화 파일이 많을 경우 초기 부하
- 메모리 사용량 증가

## 권장사항

1. **현재 방식 유지**: 대부분의 경우 현재 방식이 효율적
2. **선택적 자동 시작**: 설정에서 옵션으로 제공
3. **지연 자동 시작**: 프로그램 시작 5-10초 후 백그라운드 스캔

## 참고 코드 위치

- `ui/playback_widget.py`:
  - 라인 606: 초기 스캔 호출 (주석 처리)
  - 라인 645-658: _initial_scan 메서드
  - 라인 660-700: scan_recordings 메서드
  - 라인 386-387: 새로고침 버튼

- `ui/main_window.py`:
  - 라인 1143: Dock 열릴 때 스캔
  - 라인 1186: 재생 모드 시 스캔
  - 라인 1220: F5 새로고침
  - 라인 1264-1282: Dock 상태 로드