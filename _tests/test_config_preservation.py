#!/usr/bin/env python3
"""
config.yaml 보존 테스트
main.py 실행 전후로 config.yaml의 cameras 설정이 유지되는지 확인
"""

import yaml
import sys
from pathlib import Path

def check_config():
    """config.yaml 확인"""
    config_file = Path("config.yaml")

    if not config_file.exists():
        print("❌ config.yaml 파일이 없습니다!")
        return False

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("\n" + "="*60)
    print("config.yaml 상태 확인")
    print("="*60)

    # App 설정 확인
    if 'app' in config:
        print(f"\n✓ App 설정:")
        print(f"  - default_layout: {config['app'].get('default_layout')}")
        print(f"  - recording_path: {config['app'].get('recording_path')}")
    else:
        print("\n❌ App 설정이 없습니다!")

    # Cameras 설정 확인
    if 'cameras' in config:
        cameras = config['cameras']
        if cameras and len(cameras) > 0:
            print(f"\n✓ Cameras 설정: {len(cameras)}개")
            for i, cam in enumerate(cameras):
                print(f"\n  카메라 #{i+1}:")
                print(f"    - camera_id: {cam.get('camera_id')}")
                print(f"    - name: {cam.get('name')}")
                print(f"    - enabled: {cam.get('enabled')}")
                print(f"    - recording_enabled: {cam.get('recording_enabled')}")
                print(f"    - rtsp_url: {cam.get('rtsp_url')[:50]}..." if cam.get('rtsp_url') else "    - rtsp_url: None")
            return True
        else:
            print(f"\n❌ Cameras가 비어있습니다! cameras: {cameras}")
            return False
    else:
        print("\n❌ Cameras 설정이 없습니다!")
        return False

if __name__ == "__main__":
    success = check_config()

    if success:
        print("\n" + "="*60)
        print("✓ config.yaml이 정상적으로 구성되어 있습니다!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ config.yaml에 문제가 있습니다!")
        print("="*60)
        sys.exit(1)
