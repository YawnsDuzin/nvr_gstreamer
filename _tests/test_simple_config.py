#!/usr/bin/env python3
"""
Simple Config Loading Test
Tests basic camera configuration loading without any UI or GStreamer dependencies
"""

import sys
import os
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Set up basic logging
import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def test_simple_config():
    """Test simple config loading"""

    print("=" * 60)
    print("Simple Config Loading Test")
    print("=" * 60)

    # Test 1: Check current directory
    print("\n--- Current Directory ---")
    print(f"Current dir: {os.getcwd()}")
    print(f"Script dir: {current_dir}")

    # Test 2: Check if config.yaml exists
    print("\n--- Config File Check ---")
    config_file = Path("config.yaml")
    print(f"config.yaml exists (relative): {config_file.exists()}")
    print(f"config.yaml absolute path: {config_file.absolute()}")

    config_file_abs = current_dir / "config.yaml"
    print(f"config.yaml exists (absolute): {config_file_abs.exists()}")

    # Test 3: Read config.yaml directly
    if config_file.exists():
        print("\n--- Config File Content ---")
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content[:500])  # Print first 500 chars

        # Parse YAML
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        print("\n--- Parsed Config ---")
        print(f"Has 'app' section: {'app' in data}")
        print(f"Has 'cameras' section: {'cameras' in data}")

        if 'cameras' in data:
            print(f"Number of cameras: {len(data['cameras'])}")
            for i, cam in enumerate(data['cameras']):
                print(f"Camera {i+1}: {cam.get('camera_id', 'N/A')} - {cam.get('name', 'N/A')} - enabled: {cam.get('enabled', False)}")
    else:
        print("ERROR: config.yaml not found!")

    # Test 4: Import and test ConfigManager
    print("\n--- ConfigManager Test ---")
    try:
        from core.config import ConfigManager
        print("ConfigManager imported successfully")

        # Create ConfigManager instance
        config_manager = ConfigManager()
        print(f"ConfigManager created")
        print(f"Number of cameras loaded: {len(config_manager.cameras)}")
        print(f"Cameras: {config_manager.cameras}")

        # Get enabled cameras
        enabled = config_manager.get_enabled_cameras()
        print(f"Enabled cameras: {len(enabled)}")
        for cam in enabled:
            print(f"  - {cam.camera_id}: {cam.name}")

    except Exception as e:
        print(f"ERROR importing/using ConfigManager: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_simple_config()