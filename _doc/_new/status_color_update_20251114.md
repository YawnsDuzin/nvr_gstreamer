# 카메라 및 녹화 상태 표시 색상 변경 (2025-11-14)

## 📋 개요

카메라 연결 및 녹화 상태를 더 직관적으로 파악할 수 있도록 상태 표시 색상 체계를 개선했습니다.

## 🎨 새로운 색상 체계

### 카메라 연결 상태 (CameraStatus)

| 상태 | 아이콘 | 색상 | Hex Code | 설명 |
|------|--------|------|----------|------|
| **CONNECTED** | 🟢 | 녹색 | #00ff00 | 정상 연결 및 스트리밍 중 |
| **STREAMING** | 🟢 | 녹색 | #00ff00 | 정상 연결 및 스트리밍 중 |
| **CONNECTING** | 🟡 | 노란색 | #ffff00 | 연결 시도 중 |
| **RECONNECTING** | 🔵 | 파란색 | #0099ff | 재연결 시도 중 |
| **ERROR** | 🔴 | 빨간색 | #ff0000 | 연결 실패 또는 오류 |
| **DISCONNECTED** | ⚪ | 흰색 | #ffffff | 연결 안됨 (대기중) |

### 녹화 상태 (RecordingStatus)

| 상태 | 아이콘 | 색상 | Hex Code | 설명 |
|------|--------|------|----------|------|
| **RECORDING** | 🔴 | 빨간색 | #ff0000 | 녹화 중 |
| **PREPARING** | 🟡 | 노란색 | #ffff00 | 녹화 준비 중 |
| **STOPPING** | 🟡 | 노란색 | #ffff00 | 녹화 중지 중 |
| **PAUSED** | 🔵 | 파란색 | #0099ff | 녹화 일시 정지 |
| **ERROR** | 🟠 | 주황색 | #ff9900 | 녹화 오류 |
| **IDLE** | ⚪ | 흰색 | #ffffff | 녹화 대기 중 |

## 🔧 변경 파일

### 1. core/enums.py
- `CameraStatus.get_status_color()` 정적 메서드 추가
- `RecordingStatus.get_status_color()` 정적 메서드 추가

```python
@staticmethod
def get_status_color(status: 'CameraStatus'):
    """
    상태에 따른 색상 반환

    Returns:
        tuple: (icon, color_hex, color_name)
    """
    color_map = {
        CameraStatus.CONNECTED: ("🟢", "#00ff00", "green"),
        CameraStatus.STREAMING: ("🟢", "#00ff00", "green"),
        CameraStatus.CONNECTING: ("🟡", "#ffff00", "yellow"),
        CameraStatus.ERROR: ("🔴", "#ff0000", "red"),
        CameraStatus.RECONNECTING: ("🔵", "#0099ff", "blue"),
        CameraStatus.DISCONNECTED: ("⚪", "#ffffff", "white"),
    }
    return color_map.get(status, ("⚪", "#ffffff", "white"))
```

### 2. ui/camera_list_widget.py
- `CameraListItem.update_display()` 메서드 개선
- 카메라 스트림 상태에 따라 동적으로 색상 표시
- CameraStatus enum을 활용한 색상 적용

**변경 전:**
```python
# 고정된 3가지 상태만 표시 (비활성화, 연결됨, 대기중)
if self.camera_stream and self.camera_stream.is_connected():
    status_icon = "🟢"
    color = QColor(0, 255, 0)
```

**변경 후:**
```python
# 다양한 연결 상태 표시 (연결 중, 재연결 중, 오류 등)
if stream_status == CameraStatus.CONNECTING:
    status_icon, color_hex, _ = CameraStatus.get_status_color(CameraStatus.CONNECTING)
    status_text = "연결 중"
    color = QColor(color_hex)
elif stream_status == CameraStatus.RECONNECTING:
    status_icon, color_hex, _ = CameraStatus.get_status_color(CameraStatus.RECONNECTING)
    status_text = "재연결 중"
    color = QColor(color_hex)
```

### 3. ui/recording_control_widget.py
- `RecordingStatusItem.update_display()` 메서드 개선
- 녹화 상태뿐만 아니라 연결 상태도 함께 표시
- RecordingStatus 및 CameraStatus enum 활용

**주요 개선:**
- 녹화 대기 중일 때 연결 상태 반영 (연결됨=녹색, 연결안됨=흰색)
- 녹화 중일 때 빨간색으로 명확히 표시

### 4. ui/video_widget.py (StreamVideoWidget)
- `set_connected()` 메서드 개선: 연결/연결해제 상태 색상 적용
- `set_error()` 메서드 개선: 오류 상태 빨간색으로 표시
- `set_recording()` 메서드 개선: 녹화 중/중지 상태 색상 적용
- 초기 상태 표시 색상 변경 (흰색으로 통일)

**변경 전:**
```python
# 하드코딩된 색상 값 사용
self.streaming_status_label.setStyleSheet("color: #44ff44;")
self.recording_status_label.setStyleSheet("color: #ff0000;")
```

**변경 후:**
```python
# Enum에서 색상 가져오기
from core.enums import CameraStatus, RecordingStatus

icon, color_hex, _ = CameraStatus.get_status_color(CameraStatus.CONNECTED)
self.streaming_status_label.setText(f"{icon} Connected")
self.streaming_status_label.setStyleSheet(f"color: {color_hex};")
```

## 📌 적용 위치

### 1. Camera List Widget (좌측 패널)
- 카메라 목록에서 각 카메라의 연결 상태 표시
- 상태: 비활성화, 연결 중, 연결됨, 재연결 중, 오류, 대기중

### 2. Recording Control Widget (우측 패널)
- 녹화 상태 목록에서 각 카메라의 녹화 상태 표시
- 상태: 비활성화, 녹화중, 대기중 (연결됨/연결안됨 구분)

### 3. Video Widget (Grid View)
- 각 비디오 채널 상단에 스트리밍 및 녹화 상태 표시
- 스트리밍 상태: Connected (녹색), Disconnected (흰색), Error (빨간색)
- 녹화 상태: Rec (빨간색), Stop (흰색)

## 🎯 사용자 경험 개선

### 이전 문제점
1. 연결 시도 중과 연결 실패를 구분하기 어려움
2. 재연결 시도 중 상태가 명확하지 않음
3. 색상이 직관적이지 않음 (예: 빨간색이 연결 안됨을 의미)

### 개선 효과
1. **한눈에 파악 가능**: 색상만으로도 현재 상태를 즉시 이해
2. **일관성**: 모든 UI에서 동일한 색상 체계 사용
3. **확장성**: Enum 기반으로 색상 관리하여 유지보수 용이

## 💡 사용 예시

### 카메라 연결 시나리오
1. 카메라 연결 시작 → 🟡 노란색 (연결 중)
2. 연결 성공 → 🟢 녹색 (연결됨)
3. 네트워크 끊김 → 🔵 파란색 (재연결 중)
4. 재연결 실패 → 🔴 빨간색 (오류)

### 녹화 시나리오
1. 녹화 시작 대기 → ⚪ 흰색 (대기중)
2. 녹화 시작 → 🔴 빨간색 (녹화중)
3. 녹화 중지 → ⚪ 흰색 (대기중)

## 🔍 기술적 세부사항

### Enum 기반 색상 관리
- 중앙 집중식 색상 관리로 일관성 유지
- 색상 변경 시 한 곳만 수정하면 전체 UI에 반영
- 타입 안전성 보장 (type hints 활용)

### QColor 객체 사용
- Hex 색상 코드를 QColor 객체로 변환하여 사용
- PyQt5의 색상 시스템과 통합

### 동적 상태 반영
- CameraStream의 status 속성을 활용하여 실시간 상태 반영
- 타이머 기반 주기적 업데이트 (2초 간격)

## 📝 향후 개선 가능성

1. **애니메이션 효과**: 상태 전환 시 부드러운 색상 전환 효과
2. **사운드 알림**: 오류 상태 시 소리 알림 옵션
3. **상태 히스토리**: 상태 변경 이력 로깅 및 표시
4. **커스터마이징**: 사용자가 색상 체계를 변경할 수 있는 설정 추가

## ✅ 테스트 항목

- [ ] 카메라 연결 시 색상 변경 확인 (흰색 → 노란색 → 녹색)
- [ ] 네트워크 끊김 시 재연결 색상 확인 (파란색)
- [ ] 연결 실패 시 오류 색상 확인 (빨간색)
- [ ] 녹화 시작/중지 시 색상 변경 확인 (흰색 ↔ 빨간색)
- [ ] 모든 UI 위치에서 색상 일관성 확인
- [ ] 테마 변경 시 색상 가시성 확인

## 🔗 관련 파일

- `core/enums.py` - 색상 정의 및 Enum
- `ui/camera_list_widget.py` - 카메라 목록 상태 표시
- `ui/recording_control_widget.py` - 녹화 상태 표시
- `ui/video_widget.py` - 비디오 위젯 상태 표시
