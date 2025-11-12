# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based Network Video Recorder (NVR) system using GStreamer for video processing and PyQt5 for GUI. Features real-time RTSP streaming, continuous recording with automatic file rotation, and playback functionality. Optimized for embedded devices (Raspberry Pi) through unified pipeline architecture that reduces CPU usage by ~50%.

## Quick Start

### Initial Setup Check
```bash
# 1. Verify configuration
python _tests/test_config_loading.py

# 2. Test single camera (headless mode for Windows development)
python _tests/run_single_camera.py --headless --debug

# 3. Run main application
python main.py --debug
```

### Common Development Tasks
```bash
# Test recording functionality
python _tests/test_recording_stop.py

# Monitor memory usage
python _tests/memory_monitor.py

# Test pipeline mode switching
python _tests/test_valve_mode_switch.py

# Verify configuration persistence
python _tests/test_config_preservation.py
```

## Active Development

### Current Focus (2025-11)
- **Recording File Finalization Issue**
  - Problem: 수동 녹화 종료 시 생성된 파일이 재생되지 않음
  - Cause: MP4 moov atom이 제대로 기록되지 않음
  - Solution in progress: splitmuxsink 상태 변경 방식으로 파일 강제 finalize
  - Related files: `_doc/manual_recording_stop_playback_issue.md`, `_doc/recording_stop_affecting_streaming_fix.md`

- **Playback Widget Performance**
  - Problem: "스캔 중..." 상태에서 멈춤 현상
  - Solution: 파일 스캔 로직 최적화 및 비동기 처리 개선
  - Related files: `_doc/playback_scan_stuck_issue_fix.md`

### Recent Fixes (2025-11)
- **PTZ Zoom Key Event Fix** (2025-11-12): Fixed keyPress event not reaching MainWindow by installing eventFilter on QApplication
  - Problem: GridView and child widgets intercepted key events before MainWindow
  - Solution: Installed eventFilter on QApplication instance to capture all keyboard events
  - Related files: `ui/main_window.py`, `ui/grid_view.py`, `_doc/ptz_zoom_keypress_issue_analysis_20251112.md`
- **Raspberry Pi X Window Fix** (2025-11-05): Window handle validation to prevent BadWindow errors
- **Video Transform Case Fix** (2025-11-05): Case-insensitive handling for flip settings
- **Performance Settings Tab** (2025-11-05): System monitoring configuration UI
- **Async Delete Dialog** (2025-11-05): Multi-threaded file deletion with progress
- **Configuration Path Migration** (2025-11-04): Recording path moved to storage section
- **Backup Functionality** (2025-11-03): File backup with MD5 verification

## Commands

### Environment Setup

#### Windows
```bash
# Install GStreamer (download from https://gstreamer.freedesktop.org/download/)
# Add GStreamer bin directory to PATH

# Install Python dependencies
pip install -r requirements.txt

# Note: Change PyQt6 to PyQt5 in requirements.txt before installing
```

#### Linux/Raspberry Pi
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gi python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0

# For Raspberry Pi hardware acceleration
# Older models (Pi 3 and earlier)
sudo apt-get install -y gstreamer1.0-omx-generic

# Newer models (Pi 4 and later)
sudo apt-get install -y libv4l-0 v4l-utils

# Install Python dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Main application with GUI
python main.py
python main.py --debug  # With debug logging
python main.py --config custom_config.json  # Custom configuration

# Single camera launcher (in _tests/)
python _tests/run_single_camera.py
python _tests/run_single_camera.py --debug
python _tests/run_single_camera.py --recording  # Auto-start recording
python _tests/run_single_camera.py --headless  # No GUI, recording only

# GStreamer debugging
GST_DEBUG=3 python main.py
GST_DEBUG_DUMP_DOT_DIR=/tmp python main.py  # Generates pipeline graphs

# Run with mock GStreamer (Windows without GStreamer)
python _tests/test_main_with_mock.py
```

### Testing
```bash
# Configuration tests
python _tests/test_config_loading.py         # Verify configuration loading
python _tests/test_config_preservation.py    # Test config save/load cycle
python _tests/test_simple_config.py          # Simple config validation

# Pipeline and recording tests
python _tests/test_valve_mode_switch.py      # Test streaming/recording mode switching
python _tests/test_recording_stop.py         # Test recording stop without affecting streaming

# Performance and memory tests
python _tests/memory_monitor.py              # Monitor for memory leaks

# Direct camera connection test (replace rtsp://... with actual URL)
python -c "from camera.streaming import CameraStream; from core.models import Camera; cam = Camera(camera_id='cam_01', name='Test', rtsp_url='rtsp://...'); cs = CameraStream(cam); cs.connect(); input('Press Enter...')"
```

## Architecture

### Core Innovation: Unified Pipeline Pattern
The system's key feature is a **unified pipeline architecture** that reduces CPU usage by ~50% on embedded systems:

```
RTSP Source → Decode → Tee ─┬─→ Streaming Branch (Display)
                            │   controlled by: streaming_valve
                            │
                            └─→ Recording Branch (splitmuxsink - Auto File Split)
                                controlled by: recording_valve
```

Instead of separate pipelines for streaming and recording (which duplicates decoding), a single `tee` element splits the decoded stream. Recording and streaming are controlled dynamically using `valve` elements, enabling runtime mode switching without pipeline recreation.

**Recording uses splitmuxsink** for automatic file splitting based on time duration, eliminating the need for manual file rotation.

### Key Components

1. **Core Business Logic** (`core/`) - Refactored (2025-10-28)
   - `models.py`: Domain entities (Camera, Recording, StreamStatus, StorageInfo, SystemStatus)
     - PTZ camera support (ptz_type, ptz_port, ptz_channel fields)
   - `enums.py`: System-wide enums (CameraStatus, RecordingStatus, PipelineMode)
   - `exceptions.py`: Custom exception classes
   - `config.py`: JSON configuration handler with **Singleton pattern** (see Configuration System section)
   - `storage.py`: Storage management with automatic cleanup and backup functionality
   - `system_monitor.py`: Resource monitoring and system health checks

2. **Camera Management** (`camera/`) - Consolidated (2025-10-28)
   - `gst_pipeline.py`: Unified streaming+recording pipeline with valve control
     - Video transform support (flip, rotation)
     - Window handle validation for Raspberry Pi X Window compatibility
   - `streaming.py`: Individual camera stream handler with auto-reconnection
   - `playback.py`: Playback management and control
   - `gst_utils.py`: Platform-specific GStreamer utilities
   - `ptz_controller.py`: PTZ camera control (HIK, ONVIF)
   - Adaptive decoder selection: avdec_h264, omxh264dec (RPi 3), v4l2h264dec (RPi 4+)
   - **splitmuxsink** handles automatic file splitting based on `max-size-time`
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{timestamp}.mp4`
   - format-location signal handler dynamically generates file names

3. **UI Components** (`ui/`)
   - `main_window.py`: Main window with dockable widgets
   - `grid_view.py`: Camera view display (currently 1x1 layout)
   - `playback_widget.py`: Playback controls and file browser
   - `video_widget.py`: Video display with window handle management
   - `camera_list_widget.py`: Camera list management
   - `recording_control_widget.py`: Recording control interface
   - `backup_dialog.py`: Recording file backup with MD5 verification
   - `delete_dialog.py`: Async delete dialog with progress tracking
   - `camera_dialog.py`: Camera configuration dialog with PTZ support
   - `settings_dialog.py`: Unified settings dialog with multiple tabs
   - `log_viewer_dialog.py`: Real-time log viewer
   - **Settings Tabs** (`ui/settings/`):
     - Basic, Cameras, Streaming, Recording, Storage, Backup
     - Performance (CPU/memory/temperature monitoring thresholds)
     - Logging (comprehensive logging configuration)
     - Hot Keys, PTZ Keys
   - **Theme System** (`ui/theme/`): Centralized theme management
   - **Note**: Uses PyQt5 (NOT PyQt6 despite requirements.txt)

**Important**: README.md shows outdated project structure. This structure above is current.

### Pipeline Modes
Three operating modes controlled via `PipelineMode` enum:
- `STREAMING_ONLY`: Only display video
- `RECORDING_ONLY`: Only save to file
- `BOTH`: Simultaneous streaming and recording

Mode switching happens at runtime using valve elements without service interruption.

### Design Patterns
- **Singleton Pattern**: ConfigManager (see Configuration System section for usage)
- **Service Pattern**: StorageService for business logic separation
- **Domain Model Pattern**: Core models for Camera, Recording, StreamStatus entities
- **State Pattern**: RecordingStatus, PlaybackState, PipelineMode enums for state tracking
- **Observer Pattern**: GStreamer bus messages, Qt signals/slots for event handling
- **Tee + Valve Pattern**: Unified pipeline for resource-efficient streaming and recording
- **Callback Pattern**: Recording state change callbacks for UI synchronization
- **Worker Thread Pattern**: Async operations (backup, delete) with progress tracking

## Important Notes

### Configuration System (Updated: 2025-11)
**CRITICAL**: Configuration management migrated to SQLite database:
- **Format**: SQLite database (IT_RNVR.db) - migrated from JSON for better data integrity
- **Singleton Pattern**: ConfigManager uses singleton pattern - always use `ConfigManager.get_instance()`
- **Auto-save**: UI state (window geometry, dock visibility) saved automatically on exit
- **Database Tables**:
  - `app_config`: System-wide settings (log level, retention)
  - `cameras`: Camera list with RTSP URLs, credentials, PTZ settings, video transform
  - `recording_config`: Recording settings (file format, rotation minutes, codec, fragment duration)
  - `storage_config`: Storage management settings (recording_path, auto cleanup, max days, min space)
  - `ui_config`: UI state (window geometry, dock visibility)
  - `backup_config`: Backup settings (destination path, verification, delete after backup)
  - `performance_config`: System monitoring thresholds (CPU, memory, temperature)
  - `logging_config`: Comprehensive logging configuration (console, file, error, JSON logs)
  - `menu_keys`: Menu keyboard shortcuts (F1-F12, special keys)
  - `ptz_keys`: PTZ control keyboard shortcuts (zoom, pan, tilt)
- **Recording Path Migration** (2025-11-04):
  - Recording path moved from `recording.base_path` to `storage.recording_path`
  - All code now uses `storage_config.get('recording_path')` pattern
  - Settings UI: Recording path control moved from Recording tab to Storage tab
- **Usage**:
  ```python
  # Correct - get singleton instance
  config = ConfigManager.get_instance()

  # Access recording path (IMPORTANT: use storage section)
  storage_config = config.config.get('storage', {})
  recording_path = storage_config.get('recording_path', './recordings')

  # Update UI state
  config.update_ui_window_state(x, y, width, height)
  config.save_ui_config()  # Updates only 'ui' section in JSON

  # Access configuration sections
  cameras = config.config.get("cameras", [])
  backup_path = config.config.get("backup", {}).get("destination_path", "")
  ```

### Core Module Usage (Updated: 2025-10-28)
Business logic in core module:
- **ConfigManager**: Singleton pattern configuration handler
- **StorageService**: Automatic file cleanup based on age/space
- **SystemMonitor**: CPU, memory, temperature monitoring with alert thresholds
- **Usage**:
  ```python
  from core import ConfigManager, StorageService, SystemMonitor

  # Get config instance (singleton)
  config = ConfigManager.get_instance()

  # Initialize storage service
  storage_service = StorageService()

  # Auto cleanup old recordings
  storage_service.auto_cleanup()

  # System monitoring
  monitor = SystemMonitor()
  status = monitor.get_system_status()
  ```

### PyQt Version Mismatch
**CRITICAL**: There's a PyQt version mismatch:
- requirements.txt specifies PyQt6
- All code uses PyQt5
When modifying dependencies, ensure PyQt5 is used throughout.

### GStreamer Pipelines
Different pipeline configurations based on platform:
- Hardware acceleration: `omxh264dec` (older RPi) or `v4l2h264dec` (newer RPi)
- Software decoding: `avdec_h264` when hardware acceleration unavailable
- Recording optimization: Uses `h264parse → splitmuxsink` for automatic file splitting
  - splitmuxsink internally uses mp4mux/matroskamux based on file format
  - Automatic file rotation based on `max-size-time` property
- Video transform: `videoflip` and `videorotate` elements for flip/rotation

### Performance Optimization
System optimized for Raspberry Pi:
- Unified pipeline avoids duplicate decoding (~50% CPU reduction)
- Queue elements for buffering
- Hardware acceleration support
- Adaptive decoder selection
- Fragment-based MP4 muxing for reduced I/O
- System monitoring with configurable alert thresholds

### Window Handle Management
Critical for ensuring proper video display:
1. Window handles must be assigned after widget creation
2. 500ms delay required for handle reassignment
3. Platform-specific handling for Windows/Linux
4. **Raspberry Pi X Window Fix** (2025-11-05): Validates window handle before setting to prevent BadWindow errors

### Keyboard Event Handling
**CRITICAL**: PTZ and menu keyboard shortcuts implementation:
- **Event Filter on QApplication**: MainWindow installs eventFilter on QApplication instance to capture all keyboard events
  - Without this, child widgets (GridView, VideoWidget) intercept events before MainWindow
  - `app.installEventFilter(self)` in `_setup_fullscreen_ui()` method
- **PTZ Control**:
  - Requires camera selection first (camera list or video widget click)
  - PTZ Controller created when camera is selected
  - Key mappings stored in `ptz_keys` database table (V=zoom_in, B=zoom_out, etc.)
- **Menu Keys**: F1-F12 and special keys for menu actions, stored in `menu_keys` table
- Related files: `ui/main_window.py` (eventFilter, keyPressEvent, keyReleaseEvent)

## Development Workflow

When modifying the codebase:
1. Test changes with individual test scripts in `_tests/` before integration
2. Use `--debug` flag for verbose logging
3. Check GStreamer pipeline graphs using `GST_DEBUG_DUMP_DOT_DIR=/tmp`
4. For UI changes, test with main.py
5. For recording changes, verify file rotation and directory structure
6. For pipeline changes, test valve-based mode switching
7. Run memory monitor to check for leaks: `python _tests/memory_monitor.py`
8. Test configuration preservation with `python _tests/test_config_preservation.py`

## Documentation

Detailed technical documentation is available in `_doc/`:
- `gst_pipeline_architecture.md`: Pipeline architecture and valve control patterns
- `gstreamer_exception_handling_patterns.md`: Error handling patterns and best practices
- `gstreamer_bus_message_patterns.md`: GStreamer bus message handling
- `unified_pipeline_branch_control.md`: Branch control mechanism using valves
- `camera_disconnect_error_analysis.md`: Network disconnection error recovery
- `20251029_startup_flow.md`: Application startup sequence and initialization
- `settings_dialog_implementation_plan.md`: Settings dialog architecture
- `ptz_zoom_keypress_issue_analysis_20251112.md`: PTZ keyboard event handling fix (2025-11-12)
- `db_migration_complete.md`: JSON to SQLite database migration documentation

## Known Issues & Solutions

### Active Issues (Under Investigation)

#### Manual Recording Stop File Playback Issue
```python
# Problem: 수동 녹화 종료 시 생성된 파일이 재생되지 않음
# Cause: MP4 moov atom이 제대로 finalize되지 않음
# Current approach: splitmuxsink 상태 변경 방식으로 파일 강제 finalize
# Related docs: _doc/manual_recording_stop_playback_issue.md

# Temporary workaround:
# - Use automatic file rotation (splitmuxsink max-size-time)
# - Wait for automatic split before stopping recording
```

#### Recording Stop Affects Streaming
```python
# Problem: 녹화 중지 시 스트리밍도 함께 중지되는 현상
# Cause: EOS 이벤트가 upstream으로 전파
# Solution applied: splitmuxsink READY state 변경 방식
# Related docs: _doc/recording_stop_affecting_streaming_fix.md
```

### Resolved Issues

#### Video Not Displaying
```python
# Problem: Window handles not properly assigned
# Solution: Check window handle assignment in main_window.py
# Verify 500ms delay is present for handle assignment
```

#### Raspberry Pi X Window Error (Fixed: 2025-11-05)
```python
# Problem: "BadWindow (invalid Window parameter)" error on Raspberry Pi
# Solution: Window handle validation added in gst_pipeline.py
# Video output disabled if handle is invalid (headless mode)
# Recording continues to function properly
```

#### Video Transform Not Working (Fixed: 2025-11-05)
```python
# Problem: Video flip/rotation settings not applied
# Solution: Case sensitivity issue resolved
# Fixed with .lower() normalization in cameras_settings_tab.py and gst_pipeline.py
```

#### Recording Files 0MB or Not Created
```python
# Problem: splitmuxsink location not set or valve closed
# Solution: Ensure recording branch has:
# record_queue → recording_valve → h264parse → splitmuxsink
# Check format-location signal handler is properly connected
# Verify valve is open when recording starts
```

#### Recording Not Starting Automatically
```json
// Check IT_RNVR.json
{
  "cameras": [{
    "recording_enabled_start": true  // Must be true for auto-recording on startup
  }]
}
```

#### Backup Issues
```json
// Problem: Backup path not accessible or insufficient space
// Solution: Check backup section in IT_RNVR.json
{
  "backup": {
    "destination_path": "E:/backup",     // Verify path exists
    "verification": true,                // MD5 hash verification
    "delete_after_backup": false        // Delete source after successful backup
  }
}
```

### Performance Issues

#### High CPU Usage
```bash
# Problem: Using separate pipelines for streaming and recording
# Solution: Ensure unified pipeline (gst_pipeline.py) is used
# Check valve states with get_status() method
# Configure performance monitoring thresholds in settings
```

#### Memory Leaks
```bash
# Monitor memory usage
python _tests/memory_monitor.py

# Common leak sources:
# - Unreleased GStreamer pipelines
# - Qt widget cleanup issues
# - Circular references in signal/slot connections
```

### Error Handling Patterns

#### Pipeline Error Recovery
```python
# In camera/gst_pipeline.py (GstPipeline class)
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        # Log error, attempt reconnection, update UI state
```

#### Stream Reconnection
```python
# In camera/streaming.py (CameraStream class)
# Auto-reconnection with exponential backoff
# Status tracking: DISCONNECTED → CONNECTING → CONNECTED → ERROR → RECONNECTING
```

## Current Status

### Working Features
- Real-time RTSP streaming with low latency
- Continuous recording with automatic file rotation via splitmuxsink
- Auto-recording on camera connection (when `recording_enabled_start: true`)
- Recording file backup with MD5 verification and progress tracking
- Async file deletion with progress dialog
- Network disconnection detection and automatic reconnection
- File split on network reconnection (new recording file created)
- Playback system with timeline navigation and speed control
- Dockable UI widgets (Camera List, Recording Control, Playback)
- JSON-based configuration with singleton pattern
- UI state persistence (window geometry, dock visibility)
- PTZ camera control support (HIK, ONVIF compatible)
- Video transform (flip, rotation) with case-insensitive configuration
- Hardware acceleration support (RPi OMX/V4L2)
- Runtime pipeline mode switching via valves
- Memory-efficient unified pipeline architecture
- Automatic storage cleanup based on age and disk space
- System resource monitoring with configurable alert thresholds
- Comprehensive logging system with multiple output formats
- Real-time log viewer dialog
- Theme system with centralized management

### Known Limitations
- PyQt5/PyQt6 dependency mismatch in requirements.txt (code uses PyQt5)
- GStreamer required on Windows (use mock_gi for testing without it)
- Credentials stored in cleartext in IT_RNVR.json
- Manual recording stop may produce unplayable files (see Active Issues)

### Platform Support
- **Primary**: Raspberry Pi (3, 4, Zero 2W)
- **Secondary**: Linux (Ubuntu 20.04+, Debian 11+)
- **Experimental**: Windows (requires GStreamer or mock)

## Korean Language and Git Requirements
- 답변 및 설명은 한글로 작성한다. (All responses and explanations should be in Korean)
- 내용 요약 및 문서화 파일은 ./_doc 폴더에 생성한다.
- 테스트코드는 별도 요청이 없으면 따로 생성하지 않는다.
- 현재 개발은 windows pc에서 진행하고, 테스트는 별도의 linux 환경에서 진행중이라, 현재 pc에서는 프로그램 실행 안됨.
- **Git 작업**: 별도로 요청하지 않으면 커밋하지 않음
- **Commit 메시지 형식**:
  ```
  type: 제목 (한글)

  변경 내용 상세 설명 (한글)

  🤖 Generated with [Claude Code](https://claude.com/claude-code)

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
  - type: feat, fix, refactor, docs, test, chore 등
  - 제목과 내용은 한글로 작성
  - 코드 예시나 파일명은 원문 유지