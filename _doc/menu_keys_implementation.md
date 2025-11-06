# Menu Keys (단축키) 구현 문서

## 개요
IT_RNVR.json의 `menu_keys` 섹션에 정의된 단축키들이 실제로 프로그램에서 동작하도록 구현하였습니다.
특히 F12 키를 누르면 프로그램이 종료되도록 `program_exit` 기능을 구현했습니다.

## 문제점
- IT_RNVR.json에 `"program_exit": "F12"` 설정이 있었지만 실제로 작동하지 않음
- main_window.py의 keyPressEvent가 PTZ 키만 처리하고 menu_keys는 처리하지 않음

## 수정 내용

### 1. main_window.py 초기화 부분 수정
```python
# 메뉴 키 설정 변수 추가
self.menu_keys = {}  # 메뉴 단축키 설정

# 초기화 시 menu_keys 로드 함수 호출 추가
self._load_menu_keys()  # 메뉴 키 설정 로드
```

### 2. _load_menu_keys 메서드 추가
```python
def _load_menu_keys(self):
    """메뉴 키 설정 로드"""
    self.menu_keys = self.config_manager.config.get("menu_keys", {})
    logger.info(f"Menu keys loaded: {len(self.menu_keys)} keys")
```

### 3. keyPressEvent 메서드 수정
- 기존: PTZ 키만 처리
- 변경: menu_keys 먼저 확인하고 처리
- F1-F12, Esc 등 특수 키 처리 추가

### 4. _get_key_string 메서드 추가
키 이벤트를 문자열로 변환하는 헬퍼 메서드:
- F1-F12 키를 "F1", "F2", ... "F12" 문자열로 변환
- Esc, Enter, Tab 등 특수 키 매핑
- 일반 문자는 그대로 반환

### 5. _execute_menu_action 메서드 추가
menu_keys에 정의된 액션 실행:
- `program_exit`: 프로그램 종료 (self.close())
- `camera_connect`: 현재 카메라 연결
- `camera_stop`: 현재 카메라 중지
- `camera_connect_all`: 모든 카메라 연결
- `camera_stop_all`: 모든 카메라 중지
- `record_start`: 녹화 시작
- `record_stop`: 녹화 중지
- `screen_hide`: 전체화면 모드 나가기
- `menu_open`: 전체화면 토글 (F11)

## 지원되는 단축키 목록

| 액션 | 기본 키 | 기능 |
|------|---------|------|
| program_exit | F12 | 프로그램 종료 |
| camera_connect | F1 | 현재 카메라 연결 |
| camera_stop | F2 | 현재 카메라 중지 |
| camera_connect_all | F3 | 모든 카메라 연결 |
| camera_stop_all | F4 | 모든 카메라 중지 |
| prev_config | F5 | 이전 설정 (미구현) |
| next_config | F6 | 다음 설정 (미구현) |
| record_start | F7 | 녹화 시작 |
| record_stop | F8 | 녹화 중지 |
| screen_rotate | F9 | 화면 회전 (미구현) |
| screen_flip | F10 | 화면 뒤집기 (미구현) |
| menu_open | F11 | 전체화면 토글 |
| screen_hide | Esc | 전체화면 나가기 |

## 테스트 방법

1. 프로그램 실행
2. F12 키 누르기 → 프로그램이 종료되어야 함
3. 로그 확인:
   ```
   INFO | Menu keys loaded: 14 keys
   DEBUG | Program exit key: F12
   DEBUG | Menu key detected: program_exit = F12
   INFO | Executing menu action: program_exit
   INFO | Program exit requested via hotkey
   INFO | Shutting down application...
   ```

## 참고 사항

- 단축키는 IT_RNVR.json의 `menu_keys` 섹션에서 변경 가능
- Settings Dialog의 Hot Keys 탭에서도 변경 가능
- PTZ 키와 menu_keys가 충돌하지 않도록 주의 필요
- 일부 액션(prev_group, next_group, screen_rotate, screen_flip)은 아직 미구현

## 코드 변경 위치
- `/media/itlog/NVR_MAIN/nvr_gstreamer/ui/main_window.py`
  - 라인 75: menu_keys 변수 추가
  - 라인 82: _load_menu_keys() 호출 추가
  - 라인 835-842: _load_menu_keys 메서드 추가
  - 라인 1307-1339: keyPressEvent 수정
  - 라인 1432-1535: _get_key_string, _execute_menu_action 메서드 추가