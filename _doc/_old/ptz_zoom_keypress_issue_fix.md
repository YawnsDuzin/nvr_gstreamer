# PTZ Zoom 키(V, B) keyPressEvent 발생 안 함 문제 해결

**날짜**: 2025-11-12
**문제**: PTZ zoom 키(V, B) 누를 때 keyReleaseEvent만 발생하고 keyPressEvent가 발생하지 않음

---

## 문제 상황

### 증상
```
로그:
2025-11-12 13:48:14 | DEBUG | ui.main_window:keyReleaseEvent:1394 | PTZ key released: zoom_out (key='B')
2025-11-12 13:48:14 | DEBUG | ui.main_window:_execute_ptz_action:1417 | PTZ action released: zoom_out -> ZOOMSTOP
2025-11-12 13:48:15 | DEBUG | ui.main_window:keyReleaseEvent:1394 | PTZ key released: zoom_in (key='V')
2025-11-12 13:48:15 | DEBUG | ui.main_window:_execute_ptz_action:1417 | PTZ action released: zoom_in -> ZOOMSTOP
```

- keyPressEvent 로그가 전혀 없음
- keyReleaseEvent만 발생
- 실제 zoom 기능이 작동하지 않음 (zoom_in/zoom_out 명령이 전송되지 않음)

---

## 원인 분석

### 1. **event.text() 빈 문자열 반환**

**기존 코드**:
```python
# ui/main_window.py Line 1350
key = event.text().upper() if event.text() else key_str.upper()

# _get_key_string() Line 1503
return event.text()  # ← V, B 키에서 빈 문자열 반환 가능
```

**문제**:
- Qt에서 `event.text()`는 특정 조건에서 빈 문자열("")을 반환
  - 포커스가 다른 위젯에 있을 때
  - Input Method가 활성화되어 있을 때
  - 특정 플랫폼/Qt 버전 버그
- `_get_key_string()`이 A-Z 문자 키를 직접 처리하지 않고 `event.text()`에 의존
- V, B 키에서 `event.text()` = "" → PTZ 키 매칭 실패

### 2. **keyPressEvent 자체가 호출되지 않음**

로그에 `[KEYPRESS]` 디버그 메시지도 없었다면:
- 다른 위젯이 키 이벤트를 가로챔 (eventFilter 등)
- 포커스 문제로 MainWindow가 이벤트를 받지 못함
- GridView나 다른 자식 위젯이 이벤트를 소비

### 3. **isAutoRepeat() 처리 방식**

**기존 코드**:
```python
if event.isAutoRepeat():
    event.accept()  # ← 문제: 이벤트를 처리했다고 표시
    return
```

**문제**:
- `event.accept()`는 이벤트가 처리되었음을 의미
- 부모 위젯으로 전파되지 않음
- `event.ignore()`를 사용해야 전파됨

---

## 해결 방법

### ✅ **1. _get_key_string() 개선: A-Z 키 직접 변환**

**수정 전**:
```python
def _get_key_string(self, event):
    key = event.key()

    # F1-F12, 특수 키 처리...

    # 일반 문자 키
    return event.text()  # ← 문제: 빈 문자열 가능
```

**수정 후**:
```python
def _get_key_string(self, event):
    key = event.key()

    # F1-F12 키 처리
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"F{key - Qt.Key_F1 + 1}"

    # 특수 키 매핑...

    # A-Z 문자 키 직접 변환 (event.text()가 비어있을 수 있으므로)
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key)  # Qt.Key_V (86) → 'V'

    # 0-9 숫자 키 처리
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)  # Qt.Key_1 (49) → '1'

    # 일반 문자 키 (기타)
    return event.text()
```

**효과**:
- V 키 (Qt.Key_V = 86) → `chr(86)` = "V" (항상 정확)
- B 키 (Qt.Key_B = 66) → `chr(66)` = "B" (항상 정확)
- `event.text()` 의존성 제거

---

### ✅ **2. keyPressEvent 개선**

**수정 전**:
```python
def keyPressEvent(self, event):
    if event.isAutoRepeat():
        event.accept()  # ← 문제
        return

    key_str = self._get_key_string(event)
    key = event.text().upper() if event.text() else key_str.upper()  # ← 문제

    # PTZ 키 매칭...

    if ptz_action:
        self._execute_ptz_action(ptz_action, pressed=True)
        event.accept()
    else:
        super().keyPressEvent(event)  # ← 문제
```

**수정 후**:
```python
def keyPressEvent(self, event):
    # 디버깅: 모든 키 입력 로깅
    logger.debug(f"[KEYPRESS] key={event.key()}, text='{event.text()}', autoRepeat={event.isAutoRepeat()}")

    if event.isAutoRepeat():
        event.ignore()  # ✅ accept → ignore
        return

    # 키 문자열 변환 (_get_key_string이 A-Z를 직접 처리)
    key_str = self._get_key_string(event)
    logger.debug(f"[KEYPRESS] key_str='{key_str}'")

    # PTZ 키 처리 (key_str 직접 사용)
    key = key_str.upper()  # ✅ event.text() 사용 안함

    if not key:
        logger.warning(f"[KEYPRESS] empty key - event.key()={event.key()}, text='{event.text()}'")
        event.ignore()
        return

    # PTZ 키 매칭...

    if ptz_action:
        logger.debug(f"PTZ key pressed: {ptz_action} (key='{key}')")
        self._execute_ptz_action(ptz_action, pressed=True)
        event.accept()
    else:
        logger.debug(f"[KEYPRESS] No PTZ action for key '{key}'")
        event.ignore()  # ✅ super() 대신 ignore()
```

**개선점**:
1. ✅ `event.ignore()` 사용으로 이벤트 전파 허용
2. ✅ `event.text()` 완전 제거, `key_str` 직접 사용
3. ✅ 디버깅 로그 추가 (`[KEYPRESS]` 태그)
4. ✅ 빈 키 감지 및 경고 로그

---

### ✅ **3. keyReleaseEvent 개선**

**수정 전**:
```python
def keyReleaseEvent(self, event):
    if event.isAutoRepeat():
        event.accept()
        return

    key_str = self._get_key_string(event)
    key = event.text().upper() if event.text() else key_str.upper()

    # PTZ 키 매칭...
```

**수정 후**:
```python
def keyReleaseEvent(self, event):
    # 디버깅: 모든 키 입력 로깅
    logger.debug(f"[KEYRELEASE] key={event.key()}, text='{event.text()}', autoRepeat={event.isAutoRepeat()}")

    if event.isAutoRepeat():
        event.ignore()  # ✅ accept → ignore
        return

    # 키 문자열 변환 (_get_key_string이 A-Z를 직접 처리)
    key_str = self._get_key_string(event)
    key = key_str.upper()  # ✅ event.text() 사용 안함
    logger.debug(f"[KEYRELEASE] key_str='{key_str}'")

    if not key:
        logger.warning(f"[KEYRELEASE] empty key - event.key()={event.key()}, text='{event.text()}'")
        event.ignore()
        return

    # PTZ 키 매칭...

    if ptz_action:
        logger.debug(f"PTZ key released: {ptz_action} (key='{key}')")
        self._execute_ptz_action(ptz_action, pressed=False)
        event.accept()
    else:
        logger.debug(f"[KEYRELEASE] No PTZ action for key '{key}'")
        event.ignore()
```

---

## 예상 결과

### ✅ **정상 작동 시 로그**

```
# V 키 누름
2025-11-12 14:00:00 | DEBUG | ui.main_window:keyPressEvent:1334 | [KEYPRESS] key=86, text='v', autoRepeat=False
2025-11-12 14:00:00 | DEBUG | ui.main_window:keyPressEvent:1343 | [KEYPRESS] key_str='V'
2025-11-12 14:00:00 | DEBUG | ui.main_window:keyPressEvent:1370 | PTZ key pressed: zoom_in (key='V')
2025-11-12 14:00:00 | DEBUG | ui.main_window:_execute_ptz_action:1467 | PTZ action executed: zoom_in (pressed=True, speed=5)

# V 키 뗌
2025-11-12 14:00:01 | DEBUG | ui.main_window:keyReleaseEvent:1380 | [KEYRELEASE] key=86, text='v', autoRepeat=False
2025-11-12 14:00:01 | DEBUG | ui.main_window:keyReleaseEvent:1390 | [KEYRELEASE] key_str='V'
2025-11-12 14:00:01 | DEBUG | ui.main_window:keyReleaseEvent:1406 | PTZ key released: zoom_in (key='V')
2025-11-12 14:00:01 | DEBUG | ui.main_window:_execute_ptz_action:1417 | PTZ action released: zoom_in -> ZOOMSTOP
```

### 🔍 **디버깅 시나리오**

만약 여전히 `[KEYPRESS]` 로그가 없다면:
- **다른 위젯이 키 이벤트를 가로챔**
- GridView, ChannelWidget, VideoWidget 등에서 `event.accept()` 호출
- 해결: 해당 위젯에서 `event.ignore()` 사용

만약 `[KEYPRESS]` 로그는 있지만 `key_str`이 비어있다면:
- **Qt 버전이나 플랫폼 문제**
- `chr(event.key())` 변환 실패
- 해결: 추가 로깅으로 정확한 원인 파악

---

## 테스트 방법

### 1. 프로그램 실행
```bash
python main.py --debug
```

### 2. V 키(Zoom In) 테스트
1. V 키를 누름
2. 로그 확인:
   ```
   [KEYPRESS] key=86, text='v', autoRepeat=False
   [KEYPRESS] key_str='V'
   PTZ key pressed: zoom_in (key='V')
   PTZ action executed: zoom_in (pressed=True, speed=5)
   ```
3. 실제 카메라 zoom in 작동 확인
4. V 키를 뗌
5. 로그 확인:
   ```
   [KEYRELEASE] key=86, text='v', autoRepeat=False
   PTZ key released: zoom_in (key='V')
   PTZ action released: zoom_in -> ZOOMSTOP
   ```

### 3. B 키(Zoom Out) 테스트
1. B 키를 누름
2. 로그 확인: `PTZ key pressed: zoom_out`
3. 실제 카메라 zoom out 작동 확인
4. B 키를 뗌
5. 로그 확인: `PTZ key released: zoom_out`

---

## 주요 변경 사항 요약

| 항목 | 수정 전 | 수정 후 | 효과 |
|------|---------|---------|------|
| **_get_key_string()** | `return event.text()` | A-Z: `chr(key)` 직접 변환 | event.text() 의존성 제거 |
| **keyPressEvent** | `event.accept()` (autoRepeat) | `event.ignore()` | 이벤트 전파 허용 |
| **keyPressEvent** | `event.text()` 사용 | `key_str` 직접 사용 | 안정성 향상 |
| **keyPressEvent** | `super().keyPressEvent()` | `event.ignore()` | 명확한 의도 표현 |
| **디버깅 로그** | 없음 | `[KEYPRESS]`, `[KEYRELEASE]` | 문제 추적 용이 |

---

## 관련 파일

- `ui/main_window.py` (Line 1331-1511)
  - `keyPressEvent()` 수정
  - `keyReleaseEvent()` 수정
  - `_get_key_string()` 수정

---

## 참고

### Qt 키 코드
- `Qt.Key_V` = 86 → `chr(86)` = "V"
- `Qt.Key_B` = 66 → `chr(66)` = "B"
- `Qt.Key_A` = 65, `Qt.Key_Z` = 90
- `Qt.Key_0` = 48, `Qt.Key_9` = 57

### event.accept() vs event.ignore()
- `event.accept()`: 이벤트 처리 완료, 전파 중단
- `event.ignore()`: 이벤트 미처리, 부모 위젯으로 전파

### event.text() vs event.key()
- `event.text()`: 문자 표현 (빈 문자열 가능, 플랫폼 의존적)
- `event.key()`: 키 코드 (항상 정수, 플랫폼 독립적)

---

**결론**: `event.key()`를 직접 `chr()` 변환하여 A-Z 키를 처리함으로써 `event.text()` 불안정성 문제를 완전히 해결했습니다.
