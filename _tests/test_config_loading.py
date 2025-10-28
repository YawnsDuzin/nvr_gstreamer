#!/usr/bin/env python3
"""
Config Loading Test Script
Tests camera configuration loading
"""

import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from core.config import ConfigManager
from loguru import logger

def test_config_loading():
    """Test camera configuration loading"""

    # Remove default handler and add console handler with DEBUG level
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")

    logger.info("=" * 60)
    logger.info("Starting Config Loading Test")
    logger.info("=" * 60)

    # Check if config.yaml exists
    config_file = Path("config.yaml")
    if not config_file.exists():
        logger.error(f"Config file not found: {config_file.absolute()}")
        return

    logger.info(f"Config file found: {config_file.absolute()}")

    # Read raw content
    logger.info("\n--- Raw config.yaml content ---")
    with open(config_file, 'r') as f:
        content = f.read()
        logger.info(content)

    logger.info("\n--- Loading config through ConfigManager ---")

    # Create config manager
    config_manager = ConfigManager()

    logger.info("\n--- ConfigManager state after loading ---")
    logger.info(f"Total cameras loaded: {len(config_manager.cameras)}")
    logger.info(f"Cameras list: {config_manager.cameras}")

    if config_manager.cameras:
        logger.info("\n--- Camera Details ---")
        for i, cam in enumerate(config_manager.cameras):
            logger.info(f"Camera {i+1}:")
            logger.info(f"  - camera_id: {cam.camera_id}")
            logger.info(f"  - name: {cam.name}")
            logger.info(f"  - rtsp_url: {cam.rtsp_url}")
            logger.info(f"  - enabled: {cam.enabled}")
            logger.info(f"  - username: {cam.username}")
            logger.info(f"  - password: {cam.password}")
            logger.info(f"  - use_hardware_decode: {cam.use_hardware_decode}")
            logger.info(f"  - recording_enabled: {cam.recording_enabled}")
            logger.info(f"  - motion_detection: {cam.motion_detection}")
    else:
        logger.error("No cameras were loaded!")

    logger.info("\n--- Testing get_enabled_cameras() ---")
    enabled_cameras = config_manager.get_enabled_cameras()
    logger.info(f"Enabled cameras count: {len(enabled_cameras)}")

    if enabled_cameras:
        for cam in enabled_cameras:
            logger.info(f"Enabled camera: {cam.camera_id} - {cam.name}")
    else:
        logger.warning("No enabled cameras found!")

    logger.info("\n--- Testing get_all_cameras() ---")
    all_cameras = config_manager.get_all_cameras()
    logger.info(f"All cameras count: {len(all_cameras)}")

    logger.info("\n" + "=" * 60)
    logger.info("Config Loading Test Complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    test_config_loading()