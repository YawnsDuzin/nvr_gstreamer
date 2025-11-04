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
from ui.main_window import MainWindow
from core.config import ConfigManager

# Note: QVector<int> 메타타입 경고는 PyQt5에서 자동 처리되므로 무시 가능

def setup_logging(debug: bool = False, config_file: str = None):
    """
    Setup logging configuration from YAML file

    Args:
        debug: Enable debug logging (overrides config)
        config_file: Path to configuration file
    """
    # Remove default logger
    logger.remove()

    # Load configuration (singleton)
    try:
        config_manager = ConfigManager.get_instance(config_file=config_file)
        logging_config = config_manager.get_logging_config()
    except Exception as e:
        print(f"Warning: Failed to load logging config: {e}. Using defaults.")
        logging_config = {}

    # Check if logging is enabled
    if not logging_config.get('enabled', True):
        logger.info("Logging disabled by configuration")
        return

    # Get log directory
    log_path = Path(logging_config.get('log_path', './logs'))
    log_path.mkdir(exist_ok=True)

    # Console logging
    console_config = logging_config.get('console', {})
    if console_config.get('enabled', True):
        console_level = "DEBUG" if debug else console_config.get('level', 'INFO')
        console_format = console_config.get(
            'format',
            '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>'
        )
        colorize = console_config.get('colorize', True)

        logger.add(
            sys.stdout,
            format=console_format,
            level=console_level,
            colorize=colorize
        )

    # File logging
    file_config = logging_config.get('file', {})
    if file_config.get('enabled', True):
        file_level = "DEBUG" if debug else file_config.get('level', 'DEBUG')
        file_name = file_config.get('filename', 'pynvr_{time:YYYY-MM-DD}.log')
        file_format = file_config.get(
            'format',
            '{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}'
        )
        rotation = file_config.get('rotation', '1 day')
        retention = file_config.get('retention', '7 days')
        compression = file_config.get('compression', None)

        logger.add(
            log_path / file_name,
            format=file_format,
            level=file_level,
            rotation=rotation,
            retention=retention,
            compression=compression
        )

    # Error log (separate file for errors)
    error_config = logging_config.get('error_log', {})
    if error_config.get('enabled', False):
        error_file = error_config.get('filename', 'pynvr_errors_{time:YYYY-MM-DD}.log')
        error_level = error_config.get('level', 'ERROR')
        error_rotation = error_config.get('rotation', '10 MB')
        error_retention = error_config.get('retention', '30 days')

        logger.add(
            log_path / error_file,
            format=file_format,
            level=error_level,
            rotation=error_rotation,
            retention=error_retention
        )

    # JSON log (structured logging)
    json_config = logging_config.get('json_log', {})
    if json_config.get('enabled', False):
        json_file = json_config.get('filename', 'pynvr_{time:YYYY-MM-DD}.json')
        serialize = json_config.get('serialize', True)

        logger.add(
            log_path / json_file,
            format="{message}",
            level="DEBUG",
            serialize=serialize,
            rotation="1 day",
            retention="7 days"
        )

    logger.info("Logging initialized from configuration")


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

    # Setup logging (uses config file if specified)
    setup_logging(debug=args.debug, config_file=args.config)
    logger.info("Starting PyNVR application...")

    # Check dependencies
    if not check_dependencies():
        logger.error("Missing required dependencies. Exiting...")
        sys.exit(1)

    # Get configuration singleton instance (already initialized in setup_logging)
    config_manager = ConfigManager.get_instance()
    app_display_name = f"{config_manager.app_config.app_name}/{config_manager.app_config.version}"

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName(app_display_name)
    app.setOrganizationName(config_manager.app_config.app_name)

    # Enable high DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Apply theme before creating main window
    from ui.theme import ThemeManager
    theme_manager = ThemeManager()

    # Get theme from configuration
    ui_config = config_manager.ui_config
    theme = ui_config.theme if ui_config.theme in ['dark', 'light'] else 'dark'

    # Set initial theme and apply to application
    theme_manager.set_theme(theme, force_update=True)
    stylesheet = theme_manager.get_application_stylesheet()
    app.setStyleSheet(stylesheet)
    logger.info(f"Applied {theme} theme to application at startup")

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