#!/usr/bin/env python3
"""
Test main.py with mock GStreamer
Tests camera configuration loading in main application
"""

import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import mock_gi first to avoid real gi import
import mock_gi

# Now import main application modules
from PyQt5.QtWidgets import QApplication
from loguru import logger

def test_main_with_mock():
    """Test main application with mock GStreamer"""

    # Setup logging
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")

    logger.info("=" * 60)
    logger.info("Testing Main Application with Mock GStreamer")
    logger.info("=" * 60)

    # Create Qt application
    app = QApplication(sys.argv)

    try:
        # Import MainWindow after mock_gi is loaded
        from ui.main_window import MainWindow

        # Create main window
        logger.info("\n--- Creating MainWindow ---")
        window = MainWindow()

        # Check if config was loaded
        logger.info(f"\nMainWindow config_manager cameras: {window.config_manager.cameras}")
        logger.info(f"MainWindow enabled cameras: {window.config_manager.get_enabled_cameras()}")

        # Check grid_view
        if window.grid_view:
            logger.info(f"GridView channels: {len(window.grid_view.channels)}")
        else:
            logger.warning("No GridView found!")

        # Check camera_list
        if window.camera_list:
            logger.info(f"CameraList items: {len(window.camera_list.camera_items)}")
            for camera_id, item in window.camera_list.camera_items.items():
                logger.info(f"  - {camera_id}: {item.camera_config.name}")
        else:
            logger.warning("No CameraList found!")

        logger.info("\n--- Test Complete - Window Created Successfully ---")

    except Exception as e:
        logger.error(f"Failed to create MainWindow: {e}")
        import traceback
        traceback.print_exc()

    logger.info("\n" + "=" * 60)
    logger.info("Test Complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    test_main_with_mock()