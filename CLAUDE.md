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
                            └─→ Recording Branch (File Storage)
                                controlled by: recording_valve
```

Instead of separate pipelines for streaming and recording (which duplicates decoding), a single `tee` element splits the decoded stream. Recording and streaming are controlled dynamically using `valve` elements, enabling runtime mode switching without pipeline recreation.

### Key Components

1. **Core Business Logic** (`core/`) - NEW (2025-10)
   - `models.py`: Domain entities (Camera, Recording, StreamStatus, StorageInfo)
   - `enums.py`: System-wide enums (CameraStatus, RecordingStatus, PipelineMode)
   - `exceptions.py`: Custom exception classes
   - `services/camera_service.py`: Camera business logic, auto-recording
   - `services/storage_service.py`: Storage management, file cleanup

2. **Pipeline Management** (`streaming/`)
   - `gst_pipeline.py`: Unified streaming+recording pipeline with valve control (formerly unified_pipeline.py)
   - `camera_stream.py`: Individual camera stream handler with auto-reconnection
   - Adaptive decoder selection: avdec_h264, omxh264dec (RPi 3), v4l2h264dec (RPi 4+)
   - **Note**: PipelineManager removed in refactor - UnifiedPipeline used directly

3. **Recording System** (`recording/`)
   - `recording_manager.py`: Continuous recording with automatic file rotation
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{date}_{time}.mp4`
   - Rotation intervals: 5/10/30/60 minutes (configurable)

4. **Playback System** (`playback/`)
   - `playback_manager.py`: Recording file management and playback control
   - `PlaybackPipeline`: GStreamer-based video file playback
   - Timeline navigation with seek, speed control (0.5x-4x)

5. **UI Components** (`ui/`)
   - `main_window.py`: Main window with dockable widgets, uses CameraService
   - `grid_view.py`: Camera view display (currently 1x1 layout)
   - `playback_widget.py`: Playback controls and file browser
   - `video_widget.py`: Video display with window handle management
   - **Note**: Uses PyQt5 (NOT PyQt6 despite requirements.txt)

6. **Configuration** (`config/`)
   - `config_manager.py`: **Singleton pattern** JSON configuration handler
   - `IT_RNVR.json`: All application settings (app, ui, cameras, recording, logging, etc.)
   - UI state (window position, dock visibility) auto-saved on exit to JSON
   - ConfigManager uses singleton pattern - single instance shared across entire application

7. **Utilities** (`utils/`)
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

### Core Module Usage (Added: 2025-10)
**NEW**: Business logic separated into core module:
- **CameraService**: Handles auto-recording logic based on `recording_enabled` config
- **StorageService**: Automatic file cleanup based on age/space
- **Usage**:
  ```python
  from core.services import CameraService, StorageService

  # Initialize services
  camera_service = CameraService(config_manager)
  storage_service = StorageService()

  # Connect camera with auto-recording
  camera_service.connect_camera(camera_id, stream_object)

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
- Recording optimization: Bypasses decoding using `h264parse → mp4mux`

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

#### Recording Files 0MB
```python
# Problem: Missing h264parse in recording branch
# Solution: Ensure recording branch has:
# record_queue → recording_valve → h264parse → mp4mux → filesink
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
- **Core module added** with domain models and business services
- **PipelineManager removed** - UnifiedPipeline used directly
- **File renamed**: `unified_pipeline.py` → `pipeline.py` → `gst_pipeline.py`
- **Auto-recording logic** moved to CameraService
- **Storage management** added with automatic cleanup
- Configuration system migrated from YAML to JSON
- UI state auto-save functionality added

### Platform Support
- **Primary**: Raspberry Pi (3, 4, Zero 2W)
- **Secondary**: Linux (Ubuntu 20.04+, Debian 11+)
- **Experimental**: Windows (requires GStreamer or mock)

## Korean Language Requirement
답변 및 설명은 한글로 작성한다. (All responses and explanations should be in Korean)
내용 요약 및 문서화 파일은 ./doc 폴더에 생성한다.