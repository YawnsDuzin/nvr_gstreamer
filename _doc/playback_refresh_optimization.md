# Playback 새로고침 최적화

## 개요
PlaybackWidget의 불필요한 자동 새로고침을 제거하여 사용자 경험과 성능을 개선했습니다.

## 변경 전 문제점
- Playback Dock을 열 때마다 자동 새로고침
- 재생 모드 진입 시 자동 새로고침
- 필터(카메라, 날짜) 변경 시마다 즉시 새로고침
- 사용자 의도와 무관한 반복적인 파일 스캔
- 많은 파일이 있을 경우 UI 블로킹

## 변경 사항

### 1. 자동 새로고침 제거된 항목

#### ❌ Playback Dock 열 때 (제거)
```python
# ui/main_window.py 라인 1138-1141
def _toggle_playback_dock(self, checked: bool):
    self.playback_dock.setVisible(checked)
    # self.playback_widget.scan_recordings()  # 제거
```

#### ❌ 재생 모드 진입 시 (제거)
```python
# ui/main_window.py 라인 1183-1184
def _open_playback_mode(self):
    # ...
    # self.playback_widget.scan_recordings()  # 제거
```

#### ❌ 카메라 선택 변경 시 (제거)
```python
# ui/playback_widget.py 라인 333-334
self.camera_combo = QComboBox()
# self.camera_combo.currentTextChanged.connect(self.refresh_list)  # 제거
```

#### ❌ 시작 날짜 변경 시 (제거)
```python
# ui/playback_widget.py 라인 348-349
self.start_date = QDateEdit()
# self.start_date.dateChanged.connect(self.refresh_list)  # 제거
```

#### ❌ 종료 날짜 변경 시 (제거)
```python
# ui/playback_widget.py 라인 363-364
self.end_date = QDateEdit()
# self.end_date.dateChanged.connect(self.refresh_list)  # 제거
```

### 2. 유지되는 새로고침 트리거

#### ✅ 프로그램 시작 시 (유지)
- 초기 카메라 목록 로드는 유지
- 설정 파일에서 빠르게 로드 (파일 스캔 없음)

#### ✅ F5 키 단축키 (유지)
- 사용자의 명시적 새로고침 요청
- 전체 파일 재스캔

#### ✅ "새로고침" 버튼 (유지)
- 사용자의 명시적 새로고침 요청
- 필터 적용하여 파일 스캔

#### ✅ 파일 삭제 완료 후 (유지)
- 목록 일관성 유지를 위해 필요
- 삭제된 파일을 목록에서 제거

## 사용 방법 변경

### 이전 사용 패턴
1. Playback Dock 열기 → 자동으로 파일 스캔
2. 카메라 선택 → 즉시 필터링
3. 날짜 변경 → 즉시 필터링

### 새로운 사용 패턴
1. Playback Dock 열기
2. 원하는 필터 설정 (카메라, 날짜)
3. **"새로고침" 버튼 클릭** 또는 **F5 키**
4. 필터가 적용된 결과 확인

## 장점

### 1. 성능 개선
- 불필요한 파일 시스템 스캔 감소
- UI 응답성 향상
- CPU 및 디스크 I/O 절약

### 2. 사용자 경험
- 의도하지 않은 대기 시간 제거
- 필터 설정 중 UI 블로킹 없음
- 사용자가 원할 때만 새로고침

### 3. 제어권
- 사용자가 새로고침 시점 결정
- 여러 필터를 설정한 후 한 번에 적용
- 불필요한 중간 스캔 방지

## 성능 비교

### 시나리오: 1000개 파일, 3개 필터 변경

#### 이전 (자동 새로고침)
```
1. Dock 열기        : 3초 (스캔)
2. 카메라 선택      : 3초 (스캔)
3. 시작 날짜 변경   : 3초 (스캔)
4. 종료 날짜 변경   : 3초 (스캔)
총 소요 시간       : 12초
```

#### 이후 (수동 새로고침)
```
1. Dock 열기        : 즉시
2. 카메라 선택      : 즉시
3. 시작 날짜 변경   : 즉시
4. 종료 날짜 변경   : 즉시
5. 새로고침 버튼    : 3초 (스캔)
총 소요 시간       : 3초
```

**개선율: 75% 시간 절약**

## 테스트 시나리오

### 시나리오 1: 필터 설정 후 새로고침
1. Playback Dock 열기 (자동 스캔 없음 ✓)
2. 카메라 선택 변경 (자동 스캔 없음 ✓)
3. 날짜 범위 설정 (자동 스캔 없음 ✓)
4. "새로고침" 버튼 클릭
5. 필터된 결과 확인

### 시나리오 2: F5 키 사용
1. 필터 설정
2. F5 키 누름
3. 새로고침 실행 확인

### 시나리오 3: 파일 삭제
1. 파일 선택
2. 삭제 버튼 클릭
3. 삭제 완료 후 자동 새로고침 확인

## 롤백 방법

필요시 자동 새로고침을 복원하려면:

```python
# 1. Dock 열 때 자동 새로고침 복원
# ui/main_window.py 라인 1141
if checked:
    self.playback_widget.scan_recordings()

# 2. 필터 변경 시 자동 새로고침 복원
# ui/playback_widget.py
self.camera_combo.currentTextChanged.connect(self.refresh_list)
self.start_date.dateChanged.connect(self.refresh_list)
self.end_date.dateChanged.connect(self.refresh_list)
```

## 주의사항

1. **필터 적용**: 필터를 변경한 후 반드시 "새로고침" 버튼을 클릭해야 적용됨
2. **초기 로드**: 프로그램 시작 시 한 번은 수동 새로고침 필요
3. **사용자 교육**: 새로운 사용 패턴에 대한 안내 필요

## 관련 파일
- `/media/itlog/NVR_MAIN/nvr_gstreamer/ui/main_window.py`
- `/media/itlog/NVR_MAIN/nvr_gstreamer/ui/playback_widget.py`

## 변경 이력
- 2024-11-06: 자동 새로고침 제거
  - Playback Dock 열기 시 자동 스캔 제거
  - 재생 모드 진입 시 자동 스캔 제거
  - 필터 변경 시 자동 스캔 제거
  - 사용자 수동 제어 방식으로 전환