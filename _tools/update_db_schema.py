"""
기존 IT_RNVR.db 스키마 업데이트 스크립트
누락된 컬럼들을 ALTER TABLE로 추가
"""

import sqlite3
import sys
from pathlib import Path

# DB 파일 경로
DB_PATH = Path(__file__).parent.parent / "IT_RNVR.db"

def check_column_exists(cursor, table_name, column_name):
    """컬럼이 존재하는지 확인"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def update_schema():
    """DB 스키마 업데이트"""
    print("=" * 60)
    print("IT_RNVR.db 스키마 업데이트")
    print("=" * 60)
    print(f"DB 경로: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        print(f"[ERROR] DB 파일이 없습니다: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 백업
        backup_path = DB_PATH.with_suffix('.db.backup')
        print(f"[BACKUP] DB 백업 중: {backup_path}")
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print("[OK] 백업 완료")
        print()

        # cameras 테이블 업데이트
        print("[UPDATE] cameras 테이블 업데이트")
        print("-" * 60)

        updates = [
            ("display_order", "INTEGER NOT NULL DEFAULT 0"),
            ("video_transform_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
            ("video_transform_flip", "TEXT DEFAULT 'none'"),
            ("video_transform_rotation", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_def in updates:
            if check_column_exists(cursor, "cameras", col_name):
                print(f"  [SKIP] {col_name}: 이미 존재")
            else:
                sql = f"ALTER TABLE cameras ADD COLUMN {col_name} {col_def}"
                cursor.execute(sql)
                print(f"  [ADD] {col_name}: 추가됨")

        # streaming 테이블 업데이트
        print()
        print("[UPDATE] streaming 테이블 업데이트")
        print("-" * 60)

        streaming_updates = [
            ("keepalive_timeout", "INTEGER NOT NULL DEFAULT 5"),
            ("connection_timeout", "INTEGER NOT NULL DEFAULT 10"),
        ]

        for col_name, col_def in streaming_updates:
            if check_column_exists(cursor, "streaming", col_name):
                print(f"  [SKIP] {col_name}: 이미 존재")
            else:
                sql = f"ALTER TABLE streaming ADD COLUMN {col_name} {col_def}"
                cursor.execute(sql)
                print(f"  [ADD] {col_name}: 추가됨")

        # app 테이블에 schema_version 추가 (선택사항)
        print()
        print("[UPDATE] app 테이블 업데이트")
        print("-" * 60)

        if check_column_exists(cursor, "app", "schema_version"):
            print(f"  [SKIP] schema_version: 이미 존재")
        else:
            sql = "ALTER TABLE app ADD COLUMN schema_version INTEGER DEFAULT 1"
            cursor.execute(sql)
            print(f"  [ADD] schema_version: 추가됨")

        # 인덱스 추가
        print()
        print("[UPDATE] 인덱스 추가")
        print("-" * 60)

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cameras_display_order ON cameras(display_order)")
            print("  [ADD] idx_cameras_display_order: 추가됨")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("  [SKIP] idx_cameras_display_order: 이미 존재")
            else:
                raise

        # 커밋
        conn.commit()
        print()
        print("=" * 60)
        print("[SUCCESS] 스키마 업데이트 완료!")
        print("=" * 60)

        # 업데이트된 스키마 확인
        print()
        print("[INFO] cameras 테이블 최종 스키마:")
        print("-" * 60)
        cursor.execute("PRAGMA table_info(cameras)")
        for row in cursor.fetchall():
            print(f"  {row[1]}: {row[2]}")

        conn.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] 스키마 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()

        # 롤백
        if 'backup_path' in locals() and backup_path.exists():
            print(f"\n[WARNING] 백업에서 복원하시겠습니까? (백업 파일: {backup_path})")
            print("   수동으로 복원: mv IT_RNVR.db.backup IT_RNVR.db")

        return False

if __name__ == "__main__":
    success = update_schema()
    sys.exit(0 if success else 1)
