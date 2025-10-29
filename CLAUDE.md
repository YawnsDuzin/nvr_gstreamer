# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based Network Video Recorder (NVR) system using GStreamer for video processing and PyQt5 for GUI. Features real-time RTSP streaming, continuous recording with automatic file rotation, and playback functionality. Optimized for embedded devices (Raspberry Pi) through unified pipeline architecture that reduces CPU usage by ~50%.

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

# Single camera launcher (in tests/)
python tests/run_single_camera.py
python tests/run_single_camera.py --debug
python tests/run_single_camera.py --recording  # Auto-start recording
python tests/run_single_camera.py --headless  # No GUI, recording only

# GStreamer debugging
GST_DEBUG=3 python main.py
GST_DEBUG_DUMP_DOT_DIR=/tmp python main.py  # Generates pipeline graphs

# Run with mock GStreamer (Windows without GStreamer)
python tests/test_main_with_mock.py
```

### Testing
```bash
# Configuration tests
python tests/test_config_loading.py
python tests/test_config_preservation.py
python tests/test_simple_config.py

# Pipeline tests (in reference/)
python reference/test_stream.py rtsp://admin:password@192.168.0.131:554/stream
python reference/test_unified_pipeline.py --mode streaming --rtsp rtsp://...
python reference/test_unified_pipeline.py --mode recording --rtsp rtsp://...
python reference/test_unified_pipeline.py --mode both --rtsp rtsp://...
python tests/test_valve_mode_switch.py

# Component tests
python reference/test_recording.py
python reference/test_playback.py --mode ui

# Memory monitoring
python tests/memory_monitor.py

# Direct camera connection test
python -c "from streaming.camera_stream import CameraStream; cs = CameraStream('cam_01', 'rtsp://...'); cs.connect(); input('Press Enter...')"
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
   - `models.py`: Domain entities (Camera, Recording, StreamStatus, StorageInfo)
   - `enums.py`: System-wide enums (CameraStatus, RecordingStatus, PipelineMode)
   - `exceptions.py`: Custom exception classes
   - `config.py`: **Singleton pattern** JSON configuration handler
   - `storage.py`: Storage management, file cleanup
   - ConfigManager uses singleton pattern - single instance shared across entire application

2. **Streaming & Recording** (`streaming/`) - Consolidated (2025-10-28)
   - `gst_pipeline.py`: Unified streaming+recording pipeline with valve control
   - `camera_stream.py`: Individual camera stream handler with auto-reconnection
   - `recording.py`: Recording management with splitmuxsink
   - `playback.py`: Playback management and control
   - Adaptive decoder selection: avdec_h264, omxh264dec (RPi 3), v4l2h264dec (RPi 4+)
   - **splitmuxsink** handles automatic file splitting based on `max-size-time`
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{timestamp}_00000.mp4`
   - format-location signal handler dynamically generates file names

3. **UI Components** (`ui/`)
   - `main_window.py`: Main window with dockable widgets
   - `grid_view.py`: Camera view display (currently 1x1 layout)
   - `playback_widget.py`: Playback controls and file browser
   - `video_widget.py`: Video display with window handle management
   - `camera_list_widget.py`: Camera list management
   - `recording_control_widget.py`: Recording control interface
   - **Note**: Uses PyQt5 (NOT PyQt6 despite requirements.txt)

4. **Utilities** (`utils/`)
   - `gstreamer_utils.py`: Platform-specific GStreamer helpers
   - `system_monitor.py`: Resource monitoring threads
   - Video sink selection based on platform (Windows/Linux/RPi)

### Pipeline Modes
Three operating modes controlled via `PipelineMode` enum:
- `STREAMING_ONLY`: Only display video
- `RECORDING_ONLY`: Only save to file
- `BOTH`: Simultaneous streaming and recording

Mode switching happens at runtime using valve elements without service interruption.

### Design Patterns
- **Singleton Pattern**: ConfigManager ensures single instance across entire application
- **Service Pattern**: CameraService, StorageService for business logic separation
- **Domain Model Pattern**: Core models for Camera, Recording, StreamStatus entities
- **Manager Pattern**: RecordingManager, PlaybackManager for lifecycle management
- **State Pattern**: RecordingStatus, PlaybackState, PipelineMode enums for state tracking
- **Observer Pattern**: GStreamer bus messages, Qt signals/slots for event handling
- **Tee + Valve Pattern**: Unified pipeline for resource-efficient streaming and recording

## Important Notes

### Configuration System (Updated: 2025-10)
**CRITICAL**: Configuration management has been updated:
- **Format**: JSON (IT_RNVR.json) - migrated from YAML for easier partial updates
- **Singleton Pattern**: ConfigManager uses singleton pattern - always use `ConfigManager.get_instance()`
- **Auto-save**: UI state (window geometry, dock visibility) saved automatically on exit
- **Usage**:
  ```python
  # Correct - get singleton instance
  config = ConfigManager.get_instance()

  # Update UI state
  config.update_ui_window_state(x, y, width, height)
  config.save_ui_config()  # Updates only 'ui' section in JSON
  ```

### Core Module Usage (Updated: 2025-10-28)
Business logic in core module:
- **ConfigManager**: Singleton pattern configuration handler
- **StorageService**: Automatic file cleanup based on age/space
- **Usage**:
  ```python
  from core import ConfigManager, StorageService

  # Get config instance (singleton)
  config = ConfigManager.get_instance()

  # Initialize storage service
  storage_service = StorageService()

  # Auto cleanup old recordings
  storage_service.auto_cleanup()
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

### Performance Optimization
System optimized for Raspberry Pi:
- Unified pipeline avoids duplicate decoding (~50% CPU reduction)
- Queue elements for buffering
- Hardware acceleration support
- Adaptive decoder selection
- Fragment-based MP4 muxing for reduced I/O

### Window Handle Management
Critical for ensuring proper video display:
1. Window handles must be assigned after widget creation
2. 500ms delay required for handle reassignment
3. Platform-specific handling for Windows/Linux

## Development Workflow

When modifying the codebase:
1. Test changes with individual test scripts in `reference/` before integration
2. Use `--debug` flag for verbose logging
3. Check GStreamer pipeline graphs using `GST_DEBUG_DUMP_DOT_DIR=/tmp`
4. For UI changes, test with main.py
5. For recording changes, verify file rotation and directory structure
6. For pipeline changes, test valve-based mode switching
7. Run memory monitor to check for leaks: `python tests/memory_monitor.py`
8. Test configuration preservation with `python tests/test_config_preservation.py`

## Troubleshooting

### Common Issues and Solutions

#### Video Not Displaying
```python
# Problem: Window handles not properly assigned
# Solution: Check window handle assignment in main_window.py
# Verify 500ms delay is present for handle assignment
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
    "recording_enabled": true  // Must be true for auto-recording
  }]
}
```

#### High CPU Usage
```bash
# Problem: Using separate pipelines for streaming and recording
# Solution: Ensure gst_pipeline.py (UnifiedPipeline) is used
# Check valve states with get_status() method
```

#### Memory Leaks
```bash
# Monitor memory usage
python tests/memory_monitor.py

# Common leak sources:
# - Unreleased GStreamer pipelines
# - Qt widget cleanup issues
# - Circular references in signal/slot connections
```

### Error Handling Patterns

#### Pipeline Error Recovery
```python
# In gst_pipeline.py
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        # Log error, attempt reconnection, update UI state
```

#### Stream Reconnection
```python
# In camera_stream.py
# Auto-reconnection with exponential backoff
# Status tracking: DISCONNECTED → CONNECTING → CONNECTED → ERROR → RECONNECTING
```

## Current Status

### Working Features
- Real-time RTSP streaming with low latency
- Continuous recording with automatic file rotation
- Auto-recording on camera connection (when `recording_enabled: true`)
- Playback system with timeline navigation and speed control
- Dockable UI widgets (Camera List, Recording Control, Playback)
- JSON-based configuration with singleton pattern
- UI state persistence (window geometry, dock visibility)
- Auto-reconnection on network failure
- Hardware acceleration support (RPi OMX/V4L2)
- Runtime pipeline mode switching via valves
- Memory-efficient unified pipeline architecture
- Core services for business logic (CameraService, StorageService)

### Known Issues
- PyQt5/PyQt6 dependency mismatch in requirements.txt (code uses PyQt5)
- GStreamer required on Windows (use mock_gi for testing without it)
- Credentials stored in cleartext in IT_RNVR.json

### Recent Updates (2025-10)
- **Auto-recording UI sync fixed** (2025-10-29)
  - Removed automatic recording start from `GstPipeline.start()`
  - Recording now always starts via explicit `start_recording()` call
  - Unified flow: manual and auto-recording use identical code path
  - Valve control: All modes start with `recording_valve` closed
  - Callbacks registered before recording starts, ensuring UI sync
  - Files: `camera/gst_pipeline.py` (valve logic), `ui/main_window.py` (callback flow)
- **Project structure refactored** (2025-10-28)
  - Folder count reduced from 15 to 8 (47% reduction)
  - `config/` → `core/config.py`
  - `core/services/storage_service.py` → `core/storage.py`
  - `playback/` → `streaming/playback.py`
  - `recording/` → `streaming/recording.py`
  - Removed empty folders: config/, playback/, recording/, core/services/
- **Recording system changed to splitmuxsink** (2025-10-28)
  - Automatic file splitting based on time duration
  - format-location signal handler for dynamic file naming
  - Eliminates manual file rotation logic
- **Core module added** with domain models and business services
- **PipelineManager removed** - UnifiedPipeline used directly
- **File renamed**: `unified_pipeline.py` → `pipeline.py` → `gst_pipeline.py`
- Configuration system migrated from YAML to JSON
- UI state auto-save functionality added
- **Deprecated folders removed**: gstreamer/, services/, _tests/, _doc/

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