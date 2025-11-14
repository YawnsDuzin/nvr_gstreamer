# JSON → SQLite DB 마이그레이션 완료 문서

작성일: 2025-11-11
작성자: Claude Code

## 📋 개요

IT_RNVR 프로젝트의 설정 관리 시스템을 JSON 파일 기반에서 SQLite 데이터베이스 기반으로 완전히 전환했습니다.

## 🎯 마이그레이션 목적

- **데이터 정합성**: 트랜잭션을 통한 원자성 보장
- **쿼리 기능**: SQL을 통한 복잡한 조회 가능
- **확장성**: 새 설정 항목 추가 용이
- **설정 변경 추적**: 데이터베이스 이력 관리 가능

## 🗄️ DB 스키마

### 테이블 구조 (11개 테이블)

1. **app**: 애플리케이션 기본 정보
2. **ui**: UI 설정 (테마, 창 상태, 도크 표시 상태)
3. **streaming**: 스트리밍 설정 (디코더, 버퍼, OSD 등)
4. **cameras**: 카메라 설정 (RTSP URL, PTZ, video_transform 등)
5. **recording**: 녹화 설정 (포맷, 회전, 코덱)
6. **storage**: 저장소 관리 설정 (경로, 자동 정리)
7. **backup**: 백업 설정 (경로, 검증)
8. **menu_keys**: 메뉴 단축키
9. **ptz_keys**: PTZ 제어 단축키
10. **logging**: 로깅 설정 (콘솔, 파일, JSON 로그)
11. **performance**: 성능 모니터링 설정

### 주요 스키마 변경사항

#### cameras 테이블 추가 필드
```sql
display_order INTEGER NOT NULL DEFAULT 0,  -- 카메라 순서 유지
video_transform_enabled BOOLEAN NOT NULL DEFAULT 0,
video_transform_flip TEXT DEFAULT 'none',
video_transform_rotation INTEGER DEFAULT 0
```

#### streaming 테이블 추가 필드
```sql
keepalive_timeout INTEGER NOT NULL DEFAULT 5,
connection_timeout INTEGER NOT NULL DEFAULT 10
```

## 📁 생성된 파일

### 신규 파일

1. **core/db_schema.sql**: SQLite 스키마 정의
2. **core/db_manager.py**: DB 접근 및 관리 클래스 (1,563줄)
   - DBManager 클래스
   - CRUD 메서드 (get_*, save_*)
   - 데이터 타입 변환 유틸리티
   - JSON → DB 자동 마이그레이션

3. **_tests/test_db_config.py**: DB ConfigManager 테스트 스크립트
   - JSON → DB 마이그레이션 테스트
   - DB 읽기/쓰기 테스트
   - Video transform 필드 테스트
   - UI 설정 저장/로드 테스트

4. **_doc/db_migration_complete.md**: 본 문서

### 수정된 파일

1. **core/config.py**:
   - JSON 관련 코드 완전 제거
   - DB 기반으로 전환
   - DBManager 사용
   - 기존 인터페이스 유지 (하위 호환성)

2. **main.py**:
   - `--config` 옵션 → `--db` 옵션으로 변경
   - `config_file` → `db_path` 파라미터 변경

## 🔄 자동 마이그레이션 동작 방식

### ConfigManager 초기화 시

```python
# JSON 파일이 있고 DB가 비어있으면 자동 마이그레이션
json_path = Path("IT_RNVR.json")
if json_path.exists() and self._is_db_empty():
    logger.info("JSON 파일 감지, DB로 자동 마이그레이션 시작...")
    self.db_manager.migrate_from_json(str(json_path))
    logger.info("마이그레이션 완료")
```

### 마이그레이션 절차

1. JSON 파일 읽기
2. 각 섹션별 데이터 변환
3. 트랜잭션 시작
4. DB에 삽입 (INSERT/UPDATE)
5. 커밋
6. JSON 파일 백업 (IT_RNVR.json → IT_RNVR.json.backup)

## 📊 데이터 타입 변환

### 배열 필드
```python
# JSON
"osd_font_color": [255, 255, 255]
"decoder_preference": ["avdec_h264", "omxh264dec"]

# DB (CSV 문자열)
osd_font_color="255,255,255"
decoder_preference="avdec_h264,omxh264dec,v4l2h264dec"

# 다시 Python (자동 변환)
osd_font_color=[255, 255, 255]  # int 리스트
decoder_preference=["avdec_h264", "omxh264dec", "v4l2h264dec"]  # str 리스트
```

### Nested Dict 필드

#### window_state
```python
# JSON
"window_state": {"x": 0, "y": 0, "width": 1920, "height": 1080}

# DB (flat)
window_state_x=0
window_state_y=0
window_state_width=1920
window_state_height=1080

# 다시 Python (자동 변환)
"window_state": {"x": 0, "y": 0, "width": 1920, "height": 1080}
```

#### video_transform
```python
# JSON
"video_transform": {"enabled": True, "flip": "vertical", "rotation": 90}

# DB (flat)
video_transform_enabled=1
video_transform_flip="vertical"
video_transform_rotation=90

# 다시 Python (자동 변환)
"video_transform": {"enabled": True, "flip": "vertical", "rotation": 90}
```

## 💻 사용법

### 기본 사용
```bash
# 기본 DB 파일 사용 (IT_RNVR.db)
python main.py

# 커스텀 DB 파일 사용
python main.py --db custom_config.db

# 디버그 모드
python main.py --debug
```

### Python 코드에서 사용
```python
from core.config import ConfigManager

# Singleton 인스턴스 가져오기
config = ConfigManager.get_instance()

# 또는 DB 경로 지정
config = ConfigManager.get_instance(db_path="custom.db")

# 설정 읽기 (기존과 동일)
cameras = config.get_enabled_cameras()
storage_config = config.config.get("storage", {})
recording_path = storage_config.get("recording_path")

# 설정 쓰기 (기존과 동일)
config.save_config()
config.save_ui_config()
```

## 🧪 테스트

### 테스트 실행
```bash
# DB 설정 관리 테스트
python _tests/test_db_config.py
```

### 예상 출력
```
✓ PASS: JSON → DB 마이그레이션
✓ PASS: DB 읽기/쓰기
✓ PASS: Video Transform
✓ PASS: UI 설정
모든 테스트 통과!
```

## 🔧 Rollback 방법

문제 발생 시 다음 방법으로 롤백 가능:

```bash
# 1. DB 파일 삭제
rm IT_RNVR.db

# 2. 백업된 JSON 파일 복원
mv IT_RNVR.json.backup IT_RNVR.json

# 3. 프로그램 재실행 (자동 재마이그레이션)
python main.py
```

## ⚙️ 기술 세부사항

### DBManager 주요 메서드

#### 읽기 메서드
- `get_app_config()` → dict
- `get_ui_config()` → dict (nested 구조로 변환)
- `get_streaming_config()` → dict (배열 필드 변환)
- `get_cameras()` → list[dict] (display_order 정렬)
- `get_recording_config()` → dict
- `get_storage_config()` → dict
- `get_backup_config()` → dict
- `get_menu_keys()` → dict
- `get_ptz_keys()` → dict
- `get_logging_config()` → dict (nested 구조로 변환)
- `get_performance_config()` → dict

#### 쓰기 메서드
- `save_app_config(data)` → UPDATE/INSERT
- `save_ui_config(data)` → UPDATE/INSERT (flat으로 변환)
- `save_cameras(cameras)` → DELETE + INSERT (전체 교체)
- `save_streaming_config(data)` → UPDATE/INSERT
- 기타 save_* 메서드들...

#### 유틸리티 메서드
- `_serialize_list(data, dtype)` → CSV 문자열 변환
- `_deserialize_list(data, dtype)` → 리스트 변환
- `_flatten_window_state(dict)` → flat dict
- `_unflatten_window_state(dict)` → nested dict
- `_flatten_video_transform(dict)` → flat dict
- `_unflatten_video_transform(dict)` → nested dict
- `_flatten_logging_config(dict)` → flat dict
- `_unflatten_logging_config(dict)` → nested dict

#### 마이그레이션 메서드
- `migrate_from_json(json_path)` → JSON 파일을 읽어 DB로 마이그레이션

### 트랜잭션 관리
```python
# 마이그레이션 시 트랜잭션 사용
conn.execute("BEGIN TRANSACTION")
try:
    # ... 데이터 삽입 ...
    conn.commit()
except:
    conn.rollback()
    raise
```

### 멀티스레드 안전성
```python
# threading.Lock 사용
self.lock = threading.Lock()
self.conn = sqlite3.connect(db_path, check_same_thread=False)

with self.lock:
    cursor = self.conn.execute(...)
```

## 📌 주의사항

### 1. 기존 JSON 파일
- 첫 실행 시 자동으로 DB로 마이그레이션
- 원본 JSON은 `.backup` 파일로 백업됨
- 이후에는 DB만 사용 (JSON 무시)

### 2. 설정 변경
- 모든 설정 변경은 DB에 즉시 반영
- `save_config()` 호출 시 DB에 저장
- JSON 파일은 더 이상 업데이트되지 않음

### 3. 데이터베이스 파일
- 기본 위치: 프로젝트 루트 (`IT_RNVR.db`)
- SQLite3 형식
- 수동 편집 가능 (sqlite3 CLI 사용)

### 4. 호환성
- 기존 코드와 100% 호환
- `ConfigManager.get_instance()` API 동일
- `config.config.get()` 패턴 그대로 사용 가능

## 📈 성능 비교

### JSON vs DB

| 항목 | JSON | DB |
|------|------|-----|
| 읽기 속도 | 빠름 | 빠름 (캐시 사용) |
| 쓰기 속도 | 빠름 | 약간 느림 (트랜잭션) |
| 데이터 정합성 | 낮음 | 높음 (ACID) |
| 복잡한 쿼리 | 불가능 | 가능 (SQL) |
| 동시 접근 | 어려움 | 가능 (Lock) |
| 사람이 읽기 | 쉬움 | 어려움 |
| 파일 크기 | 작음 | 약간 큼 |

## 🔮 향후 확장 가능성

### 설정 변경 이력 추적 (선택사항)
```sql
CREATE TABLE config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    action TEXT NOT NULL,  -- INSERT, UPDATE, DELETE
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changes TEXT NOT NULL  -- JSON 형식
);
```

### 비밀번호 암호화 (선택사항)
```python
from cryptography.fernet import Fernet

# camera.password 필드 암호화
encrypted_password = fernet.encrypt(password.encode())
```

### 스키마 버전 관리
```sql
-- app 테이블에 schema_version 추가 (이미 포함됨)
schema_version INTEGER DEFAULT 1
```

## ✅ 완료 항목

- [x] DB 스키마 설계 및 SQL 파일 생성
- [x] DBManager 클래스 구현
- [x] 데이터 타입 변환 유틸리티
- [x] DB 읽기/쓰기 메서드
- [x] JSON → DB 자동 마이그레이션
- [x] ConfigManager DB 전환
- [x] main.py 수정
- [x] 테스트 스크립트 작성
- [x] 문서화

## 📚 참고 자료

- [sqlite3 Python 문서](https://docs.python.org/3/library/sqlite3.html)
- [SQLite Data Types](https://www.sqlite.org/datatype3.html)
- 프로젝트 내 관련 문서:
  - `core/db_schema.sql`: 스키마 정의
  - `core/db_manager.py`: DBManager 구현
  - `core/config.py`: ConfigManager 구현
  - `_tests/test_db_config.py`: 테스트 코드
