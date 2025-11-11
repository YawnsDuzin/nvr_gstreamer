# DB 스키마 업데이트 가이드

작성일: 2025-11-11

## 📋 개요

기존 IT_RNVR.db의 스키마를 업데이트하여 새로운 기능을 지원합니다.
- 자동 마이그레이션 제거 (수동 스키마 업데이트 방식)
- 누락된 컬럼 추가 (display_order, video_transform, keepalive_timeout 등)

## 🔄 업데이트 절차

### 1. 스키마 업데이트

기존 DB에 누락된 컬럼을 추가합니다.

```bash
python _tools/update_db_schema.py
```

**추가되는 컬럼:**

#### cameras 테이블
- `display_order` (INTEGER): 카메라 표시 순서
- `video_transform_enabled` (BOOLEAN): 영상 변환 활성화
- `video_transform_flip` (TEXT): 영상 뒤집기 (none/horizontal/vertical/both)
- `video_transform_rotation` (INTEGER): 영상 회전 (0/90/180/270)

#### streaming 테이블
- `keepalive_timeout` (INTEGER): keepalive 타임아웃 (초)
- `connection_timeout` (INTEGER): 연결 타임아웃 (초)

#### app 테이블
- `schema_version` (INTEGER): 스키마 버전 번호

### 2. 데이터 형식 변환

기존 JSON 형식으로 저장된 데이터를 CSV 형식으로 변환합니다.

```bash
python _tools/migrate_data_format.py
```

**변환 내용:**
- `osd_font_color`: `[255, 255, 255]` → `255,255,255`
- `decoder_preference`: `["avdec_h264", "omxh264dec"]` → `avdec_h264,omxh264dec`

## 📝 주요 변경사항

### ConfigManager 변경

**제거된 기능:**
- JSON 파일 자동 마이그레이션 제거
- `_is_db_empty()` 메서드 제거

**변경 전:**
```python
# JSON 파일이 있고 DB가 비어있으면 자동 마이그레이션
json_path = Path("IT_RNVR.json")
if json_path.exists() and self._is_db_empty():
    logger.info("JSON 파일 감지, DB로 자동 마이그레이션 시작...")
    self.db_manager.migrate_from_json(str(json_path))
```

**변경 후:**
```python
# DB에서 설정 로드 (자동 마이그레이션 제거)
self.load_config()
```

## 🛠️ 도구 스크립트

### 1. update_db_schema.py

기존 DB의 스키마를 업데이트합니다.

**위치:** `_tools/update_db_schema.py`

**기능:**
- 기존 DB 백업 (IT_RNVR.db.backup)
- ALTER TABLE로 컬럼 추가
- 인덱스 생성
- 스키마 검증

### 2. migrate_data_format.py

데이터 형식을 변환합니다.

**위치:** `_tools/migrate_data_format.py`

**기능:**
- 기존 DB 백업 (IT_RNVR.db.backup2)
- JSON 형식 → CSV 형식 변환
- video_transform JSON → 개별 컬럼 변환 (있는 경우)

## 🔍 검증

### 테스트 스크립트

```bash
# 간단한 ConfigManager 테스트
python test_config_simple.py
```

**예상 출력:**
```
[1] ConfigManager 초기화...
[OK] ConfigManager 초기화 성공

[2] 앱 정보:
  - 이름: IT_RNVR
  - 버전: 1.0.0

[3] 카메라 정보:
  - 총 1대
    * cam_01: Main Camera
      - RTSP: rtsp://...
      - Enabled: True
      - Video Transform: {'enabled': False, 'flip': 'none', 'rotation': 0}

[5] Streaming 정보:
  - OSD 폰트 색상: [255, 255, 255]
  - 디코더 우선순위: ['avdec_h264', 'omxh264dec', 'v4l2h264dec']
  - keepalive_timeout: 5
  - connection_timeout: 10000

[SUCCESS] 모든 테스트 통과!
```

### 수동 검증

```bash
# cameras 테이블 확인
sqlite3 IT_RNVR.db "PRAGMA table_info(cameras)"

# 데이터 확인
sqlite3 IT_RNVR.db "SELECT camera_id, display_order, video_transform_flip FROM cameras"

# streaming 데이터 확인
sqlite3 IT_RNVR.db "SELECT osd_font_color, decoder_preference FROM streaming"
```

## 🔙 롤백 방법

문제 발생 시 백업에서 복원:

```bash
# 스키마 업데이트 롤백
rm IT_RNVR.db
mv IT_RNVR.db.backup IT_RNVR.db

# 데이터 형식 변환 롤백
rm IT_RNVR.db
mv IT_RNVR.db.backup2 IT_RNVR.db
```

## 📊 업데이트 전후 비교

### 변경 전
```sql
-- cameras 테이블 (14개 컬럼)
CREATE TABLE cameras (
    cameras_idx INTEGER PRIMARY KEY,
    camera_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,
    enabled BOOLEAN NOT NULL,
    username TEXT,
    password TEXT,
    use_hardware_decode BOOLEAN NOT NULL,
    streaming_enabled_start BOOLEAN NOT NULL,
    recording_enabled_start BOOLEAN NOT NULL,
    motion_detection BOOLEAN NOT NULL,
    ptz_type TEXT,
    ptz_port TEXT,
    ptz_channel TEXT
);
```

### 변경 후
```sql
-- cameras 테이블 (18개 컬럼)
CREATE TABLE cameras (
    cameras_idx INTEGER PRIMARY KEY,
    camera_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rtsp_url TEXT NOT NULL,
    enabled BOOLEAN NOT NULL,
    username TEXT,
    password TEXT,
    use_hardware_decode BOOLEAN NOT NULL,
    streaming_enabled_start BOOLEAN NOT NULL,
    recording_enabled_start BOOLEAN NOT NULL,
    motion_detection BOOLEAN NOT NULL,
    ptz_type TEXT,
    ptz_port TEXT,
    ptz_channel TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,          -- 추가
    video_transform_enabled BOOLEAN NOT NULL DEFAULT 0, -- 추가
    video_transform_flip TEXT DEFAULT 'none',           -- 추가
    video_transform_rotation INTEGER DEFAULT 0          -- 추가
);

-- 인덱스 추가
CREATE INDEX idx_cameras_display_order ON cameras(display_order);
```

## ⚠️ 주의사항

1. **백업 필수**: 스크립트 실행 전 수동 백업 권장
   ```bash
   cp IT_RNVR.db IT_RNVR.db.manual_backup
   ```

2. **순서 중요**: 스키마 업데이트 → 데이터 형식 변환 순서로 실행

3. **검증 필수**: 업데이트 후 반드시 테스트 실행하여 확인

4. **자동 마이그레이션 제거**: ConfigManager는 더 이상 JSON에서 자동 마이그레이션하지 않음

## 📚 관련 파일

- [core/db_schema.sql](../core/db_schema.sql): 전체 스키마 정의
- [core/db_manager.py](../core/db_manager.py): DB 관리 클래스
- [core/config.py](../core/config.py): ConfigManager (자동 마이그레이션 제거됨)
- [_tools/update_db_schema.py](../_tools/update_db_schema.py): 스키마 업데이트 스크립트
- [_tools/migrate_data_format.py](../_tools/migrate_data_format.py): 데이터 형식 변환 스크립트
