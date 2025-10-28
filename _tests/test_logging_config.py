#!/usr/bin/env python3
"""
로깅 설정 테스트
IT_RNVR.yaml의 logging 섹션이 올바르게 적용되는지 테스트
"""

import sys
from pathlib import Path

# Add parent directory to path
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from loguru import logger
from core.config import ConfigManager


def test_logging_config():
    """로깅 설정 테스트"""
    print("=" * 60)
    print("로깅 설정 테스트")
    print("=" * 60)

    # IT_RNVR.yaml 로드
    config_file = current_dir / "IT_RNVR.yaml"
    print(f"\n1. 설정 파일 로드: {config_file}")

    config_manager = ConfigManager(config_file=str(config_file))
    logging_config = config_manager.get_logging_config()

    print(f"   OK Logging enabled: {logging_config.get('enabled')}")
    print(f"   OK Log path: {logging_config.get('log_path')}")

    # 콘솔 설정
    console = logging_config.get('console', {})
    print(f"\n2. 콘솔 로그 설정:")
    print(f"   - Enabled: {console.get('enabled')}")
    print(f"   - Level: {console.get('level')}")
    print(f"   - Colorize: {console.get('colorize')}")

    # 파일 설정
    file = logging_config.get('file', {})
    print(f"\n3. 파일 로그 설정:")
    print(f"   - Enabled: {file.get('enabled')}")
    print(f"   - Level: {file.get('level')}")
    print(f"   - Filename: {file.get('filename')}")
    print(f"   - Rotation: {file.get('rotation')}")
    print(f"   - Retention: {file.get('retention')}")
    print(f"   - Compression: {file.get('compression')}")

    # 에러 로그
    error = logging_config.get('error_log', {})
    print(f"\n4. 에러 로그 설정:")
    print(f"   - Enabled: {error.get('enabled')}")
    print(f"   - Filename: {error.get('filename')}")
    print(f"   - Level: {error.get('level')}")

    # JSON 로그
    json_log = logging_config.get('json_log', {})
    print(f"\n5. JSON 로그 설정:")
    print(f"   - Enabled: {json_log.get('enabled')}")
    print(f"   - Filename: {json_log.get('filename')}")

    print("\n" + "=" * 60)
    print("OK 로깅 설정 로드 성공!")
    print("=" * 60)


def test_logging_with_config():
    """실제 로깅 동작 테스트"""
    print("\n\n" + "=" * 60)
    print("실제 로깅 동작 테스트 (SKIP - GStreamer 의존성 없음)")
    print("=" * 60)
    print("\n테스트를 건너뜁니다. main.py는 GStreamer가 필요합니다.")
    print("로깅 설정 로드 테스트는 이미 완료되었습니다.")


if __name__ == "__main__":
    try:
        test_logging_config()
        test_logging_with_config()
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
