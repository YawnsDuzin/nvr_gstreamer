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
python main.py --config custom_config.yaml  # Custom configuration

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
python reference/test_valve_mode_switch.py

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

1. **Pipeline Management** (`streaming/`)
   - `pipeline_manager.py`: Core GStreamer pipeline lifecycle management
   - `unified_pipeline.py`: Unified streaming+recording pipeline with valve control (main innovation)
   - `camera_stream.py`: Individual camera stream handler with auto-reconnection
   - Adaptive decoder selection: avdec_h264, omxh264dec (RPi 3), v4l2h264dec (RPi 4+)

2. **Recording System** (`recording/`)
   - `recording_manager.py`: Continuous recording with automatic file rotation
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{date}_{time}.mp4`
   - Rotation intervals: 5/10/30/60 minutes (configurable)

3. **Playback System** (`playback/`)
   - `playback_manager.py`: Recording file management and playback control
   - `PlaybackPipeline`: GStreamer-based video file playback
   - Timeline navigation with seek, speed control (0.5x-4x)

4. **UI Components** (`ui/`)
   - `main_window_enhanced.py`: Main window with dockable widgets
   - `grid_view.py`: Camera view display (currently 1x1 layout)
   - `playback_widget.py`: Playback controls and file browser
   - `video_widget.py`: Video display with window handle management
   - **Note**: Uses PyQt5 (NOT PyQt6 despite requirements.txt)

5. **Configuration** (`config/`)
   - `config_manager.py`: YAML/JSON configuration handling
   - `config.yaml`: Camera settings and application configuration
   - Configuration preservation during runtime (no auto-save on exit)

6. **Utilities** (`utils/`)
   - `gstreamer_utils.py`: Platform-specific GStreamer helpers
   - Video sink selection based on platform (Windows/Linux/RPi)

### Pipeline Modes
Three operating modes controlled via `PipelineMode` enum:
- `STREAMING_ONLY`: Only display video
- `RECORDING_ONLY`: Only save to file
- `BOTH`: Simultaneous streaming and recording

Mode switching happens at runtime using valve elements without service interruption.

### Design Patterns
- **Manager Pattern**: PipelineManager, RecordingManager, PlaybackManager for lifecycle management
- **State Pattern**: RecordingStatus, PlaybackState, PipelineMode enums for state tracking
- **Observer Pattern**: GStreamer bus messages, Qt signals/slots for event handling
- **Dataclass Pattern**: Configuration objects (AppConfig, CameraConfigData) for structured data
- **Tee + Valve Pattern**: Unified pipeline for resource-efficient streaming and recording

## Important Notes

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

### File Recording Strategy
- Continuous recording with automatic rotation
- Date-based directory structure
- Multiple format support (MP4, MKV, AVI)
- Disk space monitoring and management

### Window Handle Management
Critical for ensuring proper video display:
1. Window handles must be assigned after widget creation
2. 500ms delay required for handle reassignment
3. Platform-specific handling for Windows/Linux

### Current System Mode
The system supports both single and multi-camera operation:
- Default configuration: Single camera (cam_01)
- Expandable to multiple cameras via configuration
- UI adapts based on camera count

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
# Solution: Check window handle assignment in main_window_enhanced.py
# Verify 500ms delay is present for handle assignment
# In single camera mode, only one channel (index 0) needs handle assignment
```

#### High CPU Usage
```python
# Problem: Using separate pipelines for streaming and recording
# Solution: Ensure unified_pipeline.py is used instead of separate pipelines
# Check valve states with get_status() method
```

#### Recording Files Not Created
```bash
# Check directory permissions
ls -la recordings/

# Verify disk space
df -h

# Check GStreamer debug output
GST_DEBUG=3 python main.py
```

#### Camera Connection Failures
```bash
# Problem: Network issues or incorrect RTSP URL
# Solution: Test RTSP URL directly
gst-launch-1.0 rtspsrc location=rtsp://admin:password@192.168.0.131:554/stream ! decodebin ! autovideosink

# Check auto-reconnection settings in config.yaml
# max_reconnect_attempts: 5
# reconnect_delay: 5
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
# In pipeline_manager.py
def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.ERROR:
        # Log error
        # Attempt reconnection
        # Update UI state
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
- Playback system with timeline navigation and speed control
- Dockable UI widgets (Camera List, Recording Control, Playback)
- Configuration management (YAML)
- Auto-reconnection on network failure
- Hardware acceleration support (RPi OMX/V4L2)
- Dark theme UI
- Runtime pipeline mode switching via valves
- Memory-efficient unified pipeline architecture
- Headless mode for recording without GUI

### Known Issues
- PyQt5/PyQt6 dependency mismatch in requirements.txt (code uses PyQt5)
- GStreamer required on Windows (use mock_gi for testing without it)
- Credentials stored in cleartext in config.yaml

### Recent Updates
- Playback functionality integrated into main window (October 2025)
- Valve-based pipeline control for efficient mode switching
- Configuration preservation improvements
- File structure reorganization (docs/, tests/, utils/)

### Platform Support
- **Primary**: Raspberry Pi (3, 4, Zero 2W)
- **Secondary**: Linux (Ubuntu 20.04+, Debian 11+)
- **Experimental**: Windows (requires GStreamer or mock)

## Korean Language Requirement
답변 및 설명은 한글로 작성한다. (All responses and explanations should be in Korean)