# PTZ Zoom 키(V, B) keyPressEvent 발생 안 함 문제 분석

## 문제 상황

- PTZ zoom 키(V, B)를 누를 때 `keyReleaseEvent`만 발생하고 `keyPressEvent`가 발생하지 않음
- 로그에 "PTZ key released"만 나오고 "PTZ key pressed"가 없음
- 실제 zoom 기능이 작동하지 않음
- 다른 PTZ 키(Q, W, E, A, S, D, Z, X, C)는 정상 작동

## 조사 결과

### 1. 로그 분석 (2025-11-10)

```log
2025-11-10 13:38:10 | DEBUG | ui.main_window:_execute_ptz_action:1397 | PTZ action released: zoom_in -> ZOOMSTOP
2025-11-10 13:38:10 | DEBUG | ui.main_window:_execute_ptz_action:1447 | PTZ action executed: zoom_in (pressed=True, speed=5)
2025-11-10 13:38:10 | DEBUG | ui.main_window:_execute_ptz_action:1397 | PTZ action released: zoom_in -> ZOOMSTOP
```

**발견한 패턴:**
- `pressed=True`와 `released` 로그가 **번갈아가며** 나타남
- `pressed=True`가 실행되고 있다는 것은 `keyPressEvent`가 호출되고 있다는 의미
- 하지만 **사용자는 keyPressEvent가 발생하지 않는다고 보고**함
- 이는 키보드 autorepeat 또는 이벤트 처리 순서 문제일 수 있음

### 2. 코드 분석

#### 2.1 main_window.py keyPressEvent/keyReleaseEvent

**문제점 1: isAutoRepeat() 처리**

```python
# Line 1331-1336
def keyPressEvent(self, event):
    """키보드 누름 이벤트 처리 (메뉴 키 및 PTZ 제어)"""
    # 자동 반복 이벤트는 무시
    if event.isAutoRepeat():
        event.accept()  # ⚠️ 문제: accept()하고 return
        return
```

**문제점 2: event.text() 처리**

```python
# Line 1350-1356
key = event.text().upper() if event.text() else key_str.upper()

# 디버깅: 키 값 확인
if not key:
    logger.debug(f"keyPressEvent: empty key - event.text()='{event.text()}', key_str='{key_str}'")
```

- V, B 키의 경우 `event.text()`가 비어있을 수 있음
- 이 경우 `key_str`을 사용하지만, `_get_key_string()`은 특수 키만 처리
- 일반 문자 키는 `event.text()`를 반환 (line 1503)

**문제점 3: PTZ 키 매칭 실패 가능성**

```python
# Line 1358-1362
ptz_action = None
for action, config_key in self.ptz_keys.items():
    if config_key.upper() == key:  # ⚠️ key가 빈 문자열이면 매칭 실패
        ptz_action = action
        break
```

- `key`가 빈 문자열이면 매칭되지 않음
- PTZ 키 설정: `"zoom_in": "V"`, `"zoom_out": "B"`
- 대소문자 비교는 문제없음 (`.upper()` 사용)

#### 2.2 grid_view.py keyPressEvent

```python
# Line 481-504
def keyPressEvent(self, event):
    """Handle keyboard shortcuts"""
    key = event.key()

    # Number keys 1-9 for channel selection
    if Qt.Key_1 <= key <= Qt.Key_9:
        channel_index = key - Qt.Key_1
        if channel_index < len(self.channels):
            self.show_channel_fullscreen(channel_index)

    # ESC to exit fullscreen
    elif key == Qt.Key_Escape:
        if self.fullscreen_channel is not None:
            self.exit_fullscreen()

    # F for fullscreen toggle
    elif key == Qt.Key_F:
        self.toggle_fullscreen()

    # S for sequence toggle
    elif key == Qt.Key_S:
        self.toggle_sequence()

    super().keyPressEvent(event)  # ⚠️ 이벤트 전파
```

**분석:**
- V (Qt.Key_V = 86), B (Qt.Key_B = 66) 키는 grid_view에서 처리하지 않음
- `super().keyPressEvent(event)` 호출로 MainWindow로 전파되어야 함
- **하지만 S 키 (Qt.Key_S = 83)는 grid_view에서 가로채므로 PTZ stop 키와 충돌!**

#### 2.3 키보드 포커스 문제

**현재 상황:**
- MainWindow, GridView 모두 `setFocusPolicy()` 설정 없음
- `installEventFilter(self)`는 MainWindow에만 설정됨 (line 400)
- EventFilter는 **마우스 이벤트만** 처리 (line 410-418)

```python
# Line 410-418
def eventFilter(self, obj, event):
    """이벤트 필터: 마우스 활동 감지 (키보드는 제외)"""
    if self.isFullScreen():
        # 마우스 이동 또는 클릭만 감지 (키보드 이벤트는 제외)
        if event.type() in [QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease]:
            self._on_user_activity()

    return super().eventFilter(obj, event)
```

- EventFilter가 키보드 이벤트를 필터링하지는 않음
- 하지만 자식 위젯(GridView)이 포커스를 가지면 MainWindow는 키 이벤트를 받지 못함

### 3. 의심되는 원인

#### 원인 1: 키보드 포커스가 GridView에 있음

- 사용자가 화면을 클릭하면 GridView 또는 ChannelWidget이 포커스를 가짐
- GridView는 V, B 키를 처리하지 않고 `super().keyPressEvent(event)` 호출
- 하지만 **QWidget의 기본 동작**으로 인해 이벤트가 부모(MainWindow)로 전파되지 않을 수 있음

#### 원인 2: event.text() 반환값이 비어있음

- 특정 상황에서 V, B 키의 `event.text()`가 비어있을 수 있음
- 이 경우 `_get_key_string()`은 특수 키만 처리하므로 빈 문자열 반환
- PTZ 키 매칭 실패로 이어짐

#### 원인 3: S 키 충돌 (PTZ stop vs Grid sequence)

- GridView의 keyPressEvent에서 S 키(Qt.Key_S)를 sequence toggle로 처리
- PTZ 설정에서도 S 키가 "stop"으로 할당됨
- **GridView가 S 키를 먼저 처리하므로 PTZ stop이 작동하지 않을 수 있음**

## 해결 방안

### 방안 1: MainWindow에 명시적으로 키보드 포커스 유지

```python
# main_window.py _setup_ui() 메서드에 추가
def _setup_ui(self):
    # ... 기존 코드 ...

    # MainWindow가 키보드 포커스를 받도록 설정
    self.setFocusPolicy(Qt.StrongFocus)

    # Grid view가 포커스를 가지지 않도록 설정
    self.grid_view.setFocusPolicy(Qt.NoFocus)
```

**장점:**
- MainWindow가 항상 키 이벤트를 받음
- PTZ 키가 정상 작동

**단점:**
- GridView의 키보드 단축키(1-9, F, S, ESC)가 작동하지 않을 수 있음

### 방안 2: MainWindow에서 eventFilter로 모든 키 이벤트 가로채기

```python
# main_window.py eventFilter 수정
def eventFilter(self, obj, event):
    """이벤트 필터: 마우스 활동 및 키보드 이벤트 감지"""
    # 전체화면 모드일 때만 마우스 감지
    if self.isFullScreen():
        if event.type() in [QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease]:
            self._on_user_activity()

    # 모든 키보드 이벤트를 MainWindow에서 처리
    if event.type() == QEvent.KeyPress:
        return self.keyPressEvent(event)
    elif event.type() == QEvent.KeyRelease:
        return self.keyReleaseEvent(event)

    return super().eventFilter(obj, event)
```

**장점:**
- 모든 키 이벤트를 MainWindow에서 처리
- GridView 키보드 단축키와 PTZ 키 모두 MainWindow에서 관리

**단점:**
- GridView의 keyPressEvent가 호출되지 않음
- 기존 GridView 단축키 로직을 MainWindow로 이동해야 함

### 방안 3: GridView에서 PTZ 키를 명시적으로 무시하고 전파

```python
# grid_view.py keyPressEvent 수정
def keyPressEvent(self, event):
    """Handle keyboard shortcuts"""
    key = event.key()

    # PTZ 키는 무시하고 부모로 전파 (MainWindow가 처리하도록)
    ptz_keys = [Qt.Key_Q, Qt.Key_W, Qt.Key_E, Qt.Key_A, Qt.Key_S, Qt.Key_D,
                Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V, Qt.Key_B, Qt.Key_R, Qt.Key_T]

    if key in ptz_keys:
        event.ignore()  # 이벤트를 부모로 전파
        return

    # Number keys 1-9 for channel selection
    if Qt.Key_1 <= key <= Qt.Key_9:
        channel_index = key - Qt.Key_1
        if channel_index < len(self.channels):
            self.show_channel_fullscreen(channel_index)

    # ESC to exit fullscreen
    elif key == Qt.Key_Escape:
        if self.fullscreen_channel is not None:
            self.exit_fullscreen()

    # F for fullscreen toggle
    elif key == Qt.Key_F:
        self.toggle_fullscreen()

    # S for sequence toggle - PTZ stop과 충돌하므로 제거 고려
    # elif key == Qt.Key_S:
    #     self.toggle_sequence()

    else:
        super().keyPressEvent(event)
```

**장점:**
- GridView 기능 유지
- PTZ 키를 명시적으로 부모(MainWindow)로 전파
- S 키 충돌 해결 가능

**단점:**
- PTZ 키 목록을 하드코딩해야 함
- 설정 변경 시 코드 수정 필요

### 방안 4: event.text() 대신 event.key()를 사용

```python
# main_window.py keyPressEvent 수정
def keyPressEvent(self, event):
    """키보드 누름 이벤트 처리 (메뉴 키 및 PTZ 제어)"""
    if event.isAutoRepeat():
        event.ignore()  # accept() 대신 ignore()
        return

    key_str = self._get_key_string(event)

    # menu_keys 처리
    for action, config_key in self.menu_keys.items():
        if config_key.upper() == key_str.upper():
            if self._execute_menu_action(action):
                event.accept()
                return

    # PTZ 키 처리 - event.text() 대신 _get_key_string() 사용
    key = key_str.upper()

    if not key:
        logger.debug(f"keyPressEvent: empty key - key_str='{key_str}'")
        event.ignore()
        return

    # PTZ 키 액션 찾기
    ptz_action = None
    for action, config_key in self.ptz_keys.items():
        if config_key.upper() == key:
            ptz_action = action
            break

    if ptz_action:
        logger.debug(f"PTZ key pressed: {ptz_action} (key='{key}')")
        self._execute_ptz_action(ptz_action, pressed=True)
        event.accept()
    else:
        event.ignore()  # 처리하지 않은 키는 ignore
```

그리고 `_get_key_string()` 수정:

```python
def _get_key_string(self, event):
    """키 이벤트를 문자열로 변환"""
    key = event.key()

    # F1-F12 키 처리
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"F{key - Qt.Key_F1 + 1}"

    # 특수 키 매핑
    special_keys = {
        Qt.Key_Escape: "Esc",
        Qt.Key_Return: "Enter",
        Qt.Key_Enter: "Enter",
        Qt.Key_Tab: "Tab",
        Qt.Key_Backspace: "Backspace",
        Qt.Key_Delete: "Delete",
        Qt.Key_Home: "Home",
        Qt.Key_End: "End",
        Qt.Key_PageUp: "PageUp",
        Qt.Key_PageDown: "PageDown",
        Qt.Key_Up: "Up",
        Qt.Key_Down: "Down",
        Qt.Key_Left: "Left",
        Qt.Key_Right: "Right",
        Qt.Key_Space: "Space"
    }

    if key in special_keys:
        return special_keys[key]

    # 일반 문자 키 - A-Z, 0-9 등
    # event.text()가 비어있을 수 있으므로 key 코드에서 직접 변환
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key)  # 대문자 반환 (Qt.Key_A = 65 = 'A')

    # 일반 문자 키 (event.text() 사용)
    return event.text()
```

**장점:**
- `event.text()`가 비어있는 문제 해결
- Qt.Key_V, Qt.Key_B를 직접 문자로 변환
- 더 안정적인 키 처리

**단점:**
- 코드가 약간 복잡해짐

## 권장 해결 방법

**단계별 접근:**

1. **먼저 방안 4 적용** - event.key()를 사용한 안정적인 키 처리
2. **방안 3 일부 적용** - GridView에서 S 키 충돌 제거 (sequence toggle을 다른 키로 변경)
3. **필요 시 방안 1 적용** - MainWindow에 StrongFocus 설정

## 추가 디버깅 방법

### 로그 추가

```python
# main_window.py keyPressEvent에 추가
def keyPressEvent(self, event):
    # 모든 키 이벤트 로깅
    logger.debug(f"keyPressEvent: key={event.key()}, text='{event.text()}', "
                f"autoRepeat={event.isAutoRepeat()}, modifiers={event.modifiers()}")

    # ... 기존 코드 ...
```

### 포커스 확인

```python
# main_window.py에 타이머 추가로 현재 포커스 위젯 확인
def _debug_focus(self):
    focused = QApplication.focusWidget()
    if focused:
        logger.debug(f"Current focus: {focused.__class__.__name__}")
    else:
        logger.debug("No widget has focus")

# _setup_ui()에서 디버그 타이머 시작
debug_timer = QTimer(self)
debug_timer.timeout.connect(self._debug_focus)
debug_timer.start(5000)  # 5초마다 확인
```

## 결론

PTZ zoom 키(V, B)의 keyPressEvent가 발생하지 않는 문제는 다음과 같은 복합적 원인으로 추정됩니다:

1. **키보드 포커스가 GridView에 있어서** MainWindow의 keyPressEvent가 호출되지 않음
2. **event.text()가 비어있어서** PTZ 키 매칭에 실패함
3. **GridView의 S 키 처리**로 인한 PTZ stop 키 충돌

**권장 해결책:**
- 방안 4 (event.key() 사용) + 방안 3 (S 키 충돌 제거) 조합 적용
- 필요 시 방안 1 (포커스 정책) 추가

## 관련 파일

- `/media/itlog/NVR_BACKUP/nvr_gstreamer/ui/main_window.py`
  - Line 1331-1369: keyPressEvent
  - Line 1371-1398: keyReleaseEvent
  - Line 1469-1503: _get_key_string
  - Line 1400-1467: _execute_ptz_action

- `/media/itlog/NVR_BACKUP/nvr_gstreamer/ui/grid_view.py`
  - Line 481-504: keyPressEvent (S 키 충돌)

- `/media/itlog/NVR_BACKUP/nvr_gstreamer/IT_RNVR - 복사본.json`
  - Line 130-144: ptz_keys 설정
  - `"zoom_in": "V"`, `"zoom_out": "B"`, `"stop": "S"`
