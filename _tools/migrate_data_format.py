"""
기존 DB의 데이터 형식을 새 형식으로 변환
JSON 형식 → CSV 형식
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "IT_RNVR.db"

def migrate_streaming_data():
    """streaming 테이블의 JSON 형식 데이터를 CSV로 변환"""
    print("=" * 60)
    print("Streaming 데이터 형식 변환")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # 현재 데이터 조회
        cursor.execute("SELECT osd_font_color, decoder_preference FROM streaming")
        row = cursor.fetchone()

        if not row:
            print("[INFO] streaming 테이블에 데이터가 없습니다.")
            return

        osd_font_color, decoder_preference = row

        print(f"\n[현재 형식]")
        print(f"  osd_font_color: {osd_font_color}")
        print(f"  decoder_preference: {decoder_preference}")

        # JSON 형식이면 변환
        new_osd_color = osd_font_color
        new_decoder_pref = decoder_preference

        if osd_font_color and (osd_font_color.startswith('[') or osd_font_color.startswith('{')):
            # JSON 파싱
            color_list = json.loads(osd_font_color)
            new_osd_color = ",".join(str(x) for x in color_list)
            print(f"\n[변환] osd_font_color: {osd_font_color} → {new_osd_color}")

        if decoder_preference and (decoder_preference.startswith('[') or decoder_preference.startswith('{')):
            # JSON 파싱
            pref_list = json.loads(decoder_preference)
            new_decoder_pref = ",".join(pref_list)
            print(f"[변환] decoder_preference: {decoder_preference} → {new_decoder_pref}")

        # 업데이트
        cursor.execute("""
            UPDATE streaming
            SET osd_font_color = ?,
                decoder_preference = ?
        """, (new_osd_color, new_decoder_pref))

        conn.commit()

        print(f"\n[SUCCESS] 데이터 형식 변환 완료!")

    except Exception as e:
        print(f"\n[ERROR] 변환 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()

    finally:
        conn.close()

def migrate_cameras_video_transform():
    """cameras 테이블의 video_transform JSON을 개별 컬럼으로 변환"""
    print("\n" + "=" * 60)
    print("Cameras video_transform 데이터 변환")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # video_transform 컬럼이 있는지 확인
        cursor.execute("PRAGMA table_info(cameras)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'video_transform' in columns:
            print("\n[INFO] 기존 video_transform 컬럼에서 데이터 추출 중...")

            # 기존 데이터 조회
            cursor.execute("SELECT cameras_idx, video_transform FROM cameras WHERE video_transform IS NOT NULL")
            rows = cursor.fetchall()

            for cameras_idx, video_transform_json in rows:
                if video_transform_json and (video_transform_json.startswith('{') or video_transform_json.startswith('[')):
                    try:
                        vt = json.loads(video_transform_json)

                        enabled = vt.get('enabled', False)
                        flip = vt.get('flip', 'none')
                        rotation = vt.get('rotation', 0)

                        print(f"  [UPDATE] camera {cameras_idx}: enabled={enabled}, flip={flip}, rotation={rotation}")

                        cursor.execute("""
                            UPDATE cameras
                            SET video_transform_enabled = ?,
                                video_transform_flip = ?,
                                video_transform_rotation = ?
                            WHERE cameras_idx = ?
                        """, (1 if enabled else 0, flip, rotation, cameras_idx))

                    except json.JSONDecodeError:
                        print(f"  [SKIP] camera {cameras_idx}: JSON 파싱 실패")

            conn.commit()
            print(f"\n[SUCCESS] video_transform 데이터 변환 완료!")
        else:
            print("\n[INFO] video_transform 컬럼이 없습니다. (이미 변환됨)")

    except Exception as e:
        print(f"\n[ERROR] 변환 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()

    finally:
        conn.close()

if __name__ == "__main__":
    print(f"DB 경로: {DB_PATH}\n")

    # 백업
    backup_path = DB_PATH.with_suffix('.db.backup2')
    print(f"[BACKUP] {backup_path}")
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    print("[OK] 백업 완료\n")

    # 변환 실행
    migrate_streaming_data()
    migrate_cameras_video_transform()

    print("\n" + "=" * 60)
    print("모든 변환 완료!")
    print("=" * 60)
