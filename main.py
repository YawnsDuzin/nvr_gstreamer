#!/usr/bin/env python3
"""
PyNVR - Network Video Recorder
Main application entry point
"""

import sys
import os
import argparse
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "ui"))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from loguru import logger
# from ui.main_window import MainWindow  # Basic version
from ui.main_window_enhanced import EnhancedMainWindow as MainWindow  # Enhanced 4-channel version


def setup_logging(debug: bool = False):
    """
    Setup logging configuration

    Args:
        debug: Enable debug logging
    """
    # Remove default logger
    logger.remove()

    # Console logging
    log_level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # File logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "pynvr_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="1 day",
        retention="7 days"
    )

    logger.info("Logging initialized")


def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        logger.info("GStreamer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize GStreamer: {e}")
        logger.error("Please install GStreamer and PyGObject")
        logger.error("On Raspberry Pi: sudo apt-get install python3-gst-1.0 gstreamer1.0-tools")
        return False

    return True


def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PyNVR - Network Video Recorder")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger.info("Starting PyNVR application...")

    # Check dependencies
    if not check_dependencies():
        logger.error("Missing required dependencies. Exiting...")
        sys.exit(1)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PyNVR")
    app.setOrganizationName("PyNVR")

    # Enable high DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create and show main window
    try:
        window = MainWindow()
        window.show()

        logger.success("PyNVR application started successfully")

        # Run application
        sys.exit(app.exec_())

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()