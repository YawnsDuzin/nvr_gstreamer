# 녹화파일 자동정리 기능 구현 제안서

## 📊 현재 상태 분석

### ✅ 구현되어 있는 부분

#### 1. StorageService 클래스 (`core/services/storage_service.py`)
완전히 구현된 자동정리 기능을 가지고 있습니다:

- ✅ `auto_cleanup()`: 정책 기반 자동 정리
- ✅ `cleanup_old_recordings(days)`: 기간 기반 정리
- ✅ `cleanup_by_space(target_free_gb)`: 공간 기반 정리
- ✅ `get_storage_info()`: 스토리지 정보 조회
- ✅ `check_disk_space()`: 디스크 공간 확인

#### 2. 설정 가능한 임계값
```python
self.min_free_space_gb = 10              # 최소 여유 공간 (GB)
self.max_storage_days = 30               # 최대 보관 기간 (일)
self.cleanup_threshold_percent = 90      # 정리 시작 임계값 (%)
```

### ❌ 구현되지 않은 부분

1. **자동 실행 스케줄러**: StorageService는 생성만 되고 실제로 호출되지 않음
2. **설정 파일 연동**: IT_RNVR.json의 `retention_days`가 StorageService에 적용되지 않음
3. **UI 통합**: 사용자가 정리 상태를 확인하거나 수동 실행할 수 없음
4. **로깅 및 알림**: 정리 작업 결과를 사용자에게 알리지 않음

---

## 🎯 구현 제안

### 방안 1: 백그라운드 자동 실행 (권장)

주기적으로 자동 정리를 실행하는 방식입니다.

#### 설정 항목 추가 (IT_RNVR.json)
```json
{
  "recording": {
    "base_path": "./recordings",
    "file_format": "mp4",
    "rotation_minutes": 10,
    "retention_days": 30,
    "codec": "h264",
    "fragment_duration_ms": 1000,

    // ⬇️ 새로 추가할 항목들
    "auto_cleanup_enabled": true,
    "cleanup_interval_hours": 6,
    "cleanup_threshold_percent": 90,
    "min_free_space_gb": 10,
    "cleanup_on_startup": true
  }
}
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `auto_cleanup_enabled` | boolean | true | 자동 정리 활성화 |
| `cleanup_interval_hours` | number | 6 | 정리 실행 주기 (시간) |
| `cleanup_threshold_percent` | number | 90 | 디스크 사용률 임계값 (%) |
| `min_free_space_gb` | number | 10 | 최소 여유 공간 (GB) |
| `cleanup_on_startup` | boolean | true | 시작 시 정리 실행 |

#### 구현 방법

##### 1. StorageService 초기화 수정
```python
# storage_service.py
class StorageService:
    def __init__(self, recordings_path: str = None):
        # 설정 로드
        config_manager = ConfigManager.get_instance()
        recording_config = config_manager.get_recording_config()

        # 경로 설정
        if recordings_path is None:
            recordings_path = recording_config.get('base_path', './recordings')

        self.recordings_path = Path(recordings_path)
        self.recordings_path.mkdir(exist_ok=True)

        # 설정에서 임계값 로드
        self.auto_cleanup_enabled = recording_config.get('auto_cleanup_enabled', True)
        self.cleanup_interval_hours = recording_config.get('cleanup_interval_hours', 6)
        self.min_free_space_gb = recording_config.get('min_free_space_gb', 10)
        self.max_storage_days = recording_config.get('retention_days', 30)
        self.cleanup_threshold_percent = recording_config.get('cleanup_threshold_percent', 90)

        logger.info(f"Storage service initialized: path={self.recordings_path}, "
                   f"retention={self.max_storage_days}days, "
                   f"auto_cleanup={self.auto_cleanup_enabled}")
```

##### 2. MainWindow에 타이머 추가
```python
# main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 기존 코드 ...

        # 스토리지 서비스 초기화
        self.storage_service = StorageService()

        # 자동 정리 타이머 설정
        self._setup_cleanup_timer()

        # 시작 시 정리 실행
        if self.config_manager.get_recording_config().get('cleanup_on_startup', True):
            QTimer.singleShot(30000, self._run_auto_cleanup)  # 30초 후 실행

    def _setup_cleanup_timer(self):
        """자동 정리 타이머 설정"""
        recording_config = self.config_manager.get_recording_config()

        if not recording_config.get('auto_cleanup_enabled', True):
            logger.info("Auto cleanup disabled")
            return

        interval_hours = recording_config.get('cleanup_interval_hours', 6)
        interval_ms = interval_hours * 60 * 60 * 1000  # 시간 → 밀리초

        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self._run_auto_cleanup)
        self.cleanup_timer.start(interval_ms)

        logger.info(f"Auto cleanup timer started: interval={interval_hours}h")

    def _run_auto_cleanup(self):
        """자동 정리 실행"""
        try:
            logger.info("Starting auto cleanup...")
            deleted_count = self.storage_service.auto_cleanup()

            if deleted_count > 0:
                logger.success(f"Auto cleanup completed: {deleted_count} files deleted")
                # UI 알림 (선택 사항)
                # self.statusBar().showMessage(
                #     f"자동 정리 완료: {deleted_count}개 파일 삭제됨", 5000
                # )
            else:
                logger.info("Auto cleanup: no files to delete")

        except Exception as e:
            logger.error(f"Auto cleanup failed: {e}")
```

---

### 방안 2: UI 통합 (추가 기능)

사용자가 수동으로 제어할 수 있는 UI를 추가합니다.

#### RecordingControlWidget에 정리 기능 추가

```python
# recording_control_widget.py
class RecordingControlWidget(QWidget):
    def __init__(self):
        # ... 기존 코드 ...

        # 스토리지 관리 섹션 추가
        self._create_storage_section()

    def _create_storage_section(self):
        """스토리지 관리 섹션 생성"""
        storage_group = QGroupBox("스토리지 관리")
        layout = QVBoxLayout()

        # 스토리지 정보 표시
        self.storage_info_label = QLabel()
        self._update_storage_info()
        layout.addWidget(self.storage_info_label)

        # 수동 정리 버튼
        cleanup_layout = QHBoxLayout()

        self.cleanup_old_btn = QPushButton("오래된 파일 정리")
        self.cleanup_old_btn.clicked.connect(self._manual_cleanup_old)
        cleanup_layout.addWidget(self.cleanup_old_btn)

        self.cleanup_space_btn = QPushButton("공간 확보")
        self.cleanup_space_btn.clicked.connect(self._manual_cleanup_space)
        cleanup_layout.addWidget(self.cleanup_space_btn)

        layout.addLayout(cleanup_layout)

        storage_group.setLayout(layout)
        self.main_layout.addWidget(storage_group)

    def _update_storage_info(self):
        """스토리지 정보 업데이트"""
        try:
            from core.services import StorageService
            storage_service = StorageService()
            info = storage_service.get_storage_info()

            text = (
                f"총 녹화: {info.recordings_count}개 파일 "
                f"({info.recordings_size / (1024**3):.2f} GB)\n"
                f"디스크 사용률: {info.usage_percent:.1f}% "
                f"({info.free_space / (1024**3):.1f} GB 남음)"
            )

            if info.oldest_recording:
                age_days = (datetime.now() - info.oldest_recording).days
                text += f"\n가장 오래된 파일: {age_days}일 전"

            self.storage_info_label.setText(text)

        except Exception as e:
            self.storage_info_label.setText(f"스토리지 정보 로드 실패: {e}")

    def _manual_cleanup_old(self):
        """수동 정리: 오래된 파일"""
        from PyQt5.QtWidgets import QInputDialog

        days, ok = QInputDialog.getInt(
            self, "오래된 파일 정리",
            "삭제할 파일의 보관 기간 (일):",
            30, 1, 365, 1
        )

        if ok:
            reply = QMessageBox.question(
                self, "확인",
                f"{days}일 이전 파일을 모두 삭제하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    from core.services import StorageService
                    storage_service = StorageService()
                    deleted = storage_service.cleanup_old_recordings(days=days, force=True)

                    QMessageBox.information(
                        self, "정리 완료",
                        f"{deleted}개 파일이 삭제되었습니다."
                    )
                    self._update_storage_info()

                except Exception as e:
                    QMessageBox.critical(
                        self, "오류",
                        f"파일 정리 실패: {e}"
                    )

    def _manual_cleanup_space(self):
        """수동 정리: 공간 확보"""
        from PyQt5.QtWidgets import QInputDialog

        gb, ok = QInputDialog.getDouble(
            self, "공간 확보",
            "확보할 여유 공간 (GB):",
            20.0, 1.0, 1000.0, 1
        )

        if ok:
            reply = QMessageBox.question(
                self, "확인",
                f"오래된 파일부터 삭제하여 {gb}GB를 확보하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    from core.services import StorageService
                    storage_service = StorageService()
                    deleted = storage_service.cleanup_by_space(target_free_gb=gb)

                    QMessageBox.information(
                        self, "정리 완료",
                        f"{deleted}개 파일이 삭제되었습니다."
                    )
                    self._update_storage_info()

                except Exception as e:
                    QMessageBox.critical(
                        self, "오류",
                        f"공간 확보 실패: {e}"
                    )
```

---

### 방안 3: 녹화 시작 전 자동 체크 (최소 구현)

녹화를 시작할 때마다 공간을 확인하고 필요 시 정리합니다.

```python
# gst_pipeline.py
class UnifiedPipeline:
    def start_recording(self) -> bool:
        """녹화 시작 (공간 체크 포함)"""
        # 디스크 공간 체크
        try:
            from core.services import StorageService
            storage_service = StorageService()
            free_gb, is_sufficient = storage_service.check_disk_space()

            if not is_sufficient:
                logger.warning(f"Low disk space ({free_gb:.1f}GB), running cleanup...")
                deleted = storage_service.auto_cleanup()
                logger.info(f"Cleanup deleted {deleted} files")

                # 재확인
                free_gb, is_sufficient = storage_service.check_disk_space()
                if not is_sufficient:
                    logger.error(f"Still low disk space after cleanup ({free_gb:.1f}GB)")
                    return False

        except Exception as e:
            logger.warning(f"Disk space check failed: {e}")

        # ... 기존 녹화 시작 코드 ...
```

---

## 🎯 권장 구현 순서

### Phase 1: 기본 자동 정리 (필수)
1. ✅ IT_RNVR.json에 설정 항목 추가
2. ✅ StorageService 설정 로드 기능 추가
3. ✅ MainWindow에 자동 정리 타이머 추가
4. ✅ 시작 시 정리 기능 추가

**예상 작업 시간**: 30분
**난이도**: ⭐⭐

### Phase 2: UI 통합 (선택)
1. ✅ RecordingControlWidget에 스토리지 섹션 추가
2. ✅ 수동 정리 버튼 추가
3. ✅ 스토리지 정보 실시간 업데이트

**예상 작업 시간**: 1시간
**난이도**: ⭐⭐⭐

### Phase 3: 고급 기능 (선택)
1. ✅ 정리 작업 진행률 표시
2. ✅ 정리 로그 보기
3. ✅ 카메라별 개별 정리
4. ✅ 정리 스케줄 설정 UI

**예상 작업 시간**: 2시간
**난이도**: ⭐⭐⭐⭐

---

## 📋 설정 예시

### 최소 설정 (기본값 사용)
```json
{
  "recording": {
    "retention_days": 30
  }
}
```

### 권장 설정 (자동 정리 활성화)
```json
{
  "recording": {
    "base_path": "./recordings",
    "retention_days": 30,
    "auto_cleanup_enabled": true,
    "cleanup_interval_hours": 6,
    "cleanup_threshold_percent": 85,
    "min_free_space_gb": 20,
    "cleanup_on_startup": true
  }
}
```

### 고급 설정 (수동 제어)
```json
{
  "recording": {
    "retention_days": 60,
    "auto_cleanup_enabled": false,
    "cleanup_threshold_percent": 95,
    "min_free_space_gb": 50
  }
}
```

---

## ⚠️ 주의사항

1. **삭제는 복구 불가**: 자동 정리로 삭제된 파일은 복구할 수 없습니다
2. **충분한 여유 공간 확보**: `min_free_space_gb`를 넉넉하게 설정하세요
3. **정리 주기 조정**: 카메라 수와 녹화 설정에 따라 `cleanup_interval_hours` 조정 필요
4. **첫 실행 주의**: `cleanup_on_startup`이 활성화되면 시작 시 바로 정리됨

---

## 🧪 테스트 시나리오

### 시나리오 1: 기간 기반 정리
```python
# 30일 이상 된 파일 정리
storage_service = StorageService()
deleted = storage_service.cleanup_old_recordings(days=30)
print(f"Deleted {deleted} files")
```

### 시나리오 2: 공간 기반 정리
```python
# 20GB 여유 공간 확보
storage_service = StorageService()
deleted = storage_service.cleanup_by_space(target_free_gb=20)
print(f"Deleted {deleted} files")
```

### 시나리오 3: 자동 정리 (정책 기반)
```python
# 디스크 90% 사용 or 30일 경과 파일 정리
storage_service = StorageService()
deleted = storage_service.auto_cleanup()
print(f"Auto cleanup: {deleted} files deleted")
```

---

## 📊 예상 효과

- ✅ 디스크 공간 자동 관리
- ✅ 녹화 중단 방지 (공간 부족 예방)
- ✅ 수동 관리 부담 감소
- ✅ 시스템 안정성 향상

---

## 📌 결론

**권장사항**: **Phase 1 (기본 자동 정리)** 부터 구현하세요.

StorageService는 이미 완벽하게 구현되어 있으므로, 설정 연동과 타이머만 추가하면 바로 동작합니다. 30분 이내에 구현 가능하며, 시스템 안정성이 크게 향상됩니다.

Phase 2, 3는 사용자 편의성을 위한 선택 사항입니다.
