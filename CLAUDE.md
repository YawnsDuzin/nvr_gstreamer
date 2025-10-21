# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based Network Video Recorder (NVR) system using GStreamer for video processing and PyQt5 for GUI. **Currently configured for single camera operation** with real-time streaming, continuous recording, and playback support. Optimized for embedded devices (Raspberry Pi) with unified pipeline architecture for efficient resource usage.

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
# Main application (single camera mode)
python main.py

# Simplified single camera launcher
python run_single_camera.py

# With debug logging
python main.py --debug
python run_single_camera.py --debug

# Auto-start recording
python run_single_camera.py --recording

# Headless mode (no GUI, recording only)
python run_single_camera.py --headless

# With custom config
python main.py --config custom_config.yaml

# Set GStreamer debug environment for pipeline debugging
GST_DEBUG=3 python main.py
GST_DEBUG_DUMP_DOT_DIR=/tmp python main.py  # Generates pipeline graphs
```

### Testing
```bash
# Comprehensive single camera test (streaming, recording, both)
python test_single_camera.py

# Test RTSP streaming with specific camera
python reference/test_stream.py rtsp://admin:password@192.168.0.131:554/stream

# Test unified pipeline modes
python reference/test_unified_pipeline.py --mode streaming --rtsp rtsp://admin:password@192.168.0.131:554/stream
python reference/test_unified_pipeline.py --mode recording --rtsp rtsp://admin:password@192.168.0.131:554/stream
python reference/test_unified_pipeline.py --mode both --rtsp rtsp://admin:password@192.168.0.131:554/stream
python reference/test_unified_pipeline.py --mode rotation --rtsp rtsp://admin:password@192.168.0.131:554/stream

# Test recording functionality
python reference/test_recording.py

# Test playback with UI
python reference/test_playback.py --mode ui

# Test valve-based mode switching
python reference/test_valve_mode_switch.py

# Monitor memory usage
python tests/memory_monitor.py

# Test individual camera connection
python -c "from streaming.camera_stream import CameraStream; cs = CameraStream('cam_01', 'rtsp://admin:password@192.168.0.131:554/stream'); cs.connect(); input('Press Enter to stop...')"
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
   - `pipeline_manager.py`: Core GStreamer pipeline lifecycle
   - `unified_pipeline.py`: Unified streaming+recording pipeline with valve control (514 lines, main innovation)
   - `camera_stream.py`: Individual camera stream handler with auto-reconnection
   - Adaptive decoder selection: avdec_h264, omxh264dec (older RPi), v4l2h264dec (newer RPi)

2. **Recording System** (`recording/`)
   - `recording_manager.py`: Multi-camera continuous recording with automatic file rotation
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{date}_{time}.mp4`
   - Rotation intervals: 5/10/30/60 minutes (configurable)

3. **UI Components** (`ui/`)
   - `main_window_enhanced.py`: Main single camera UI window with dockable widgets (simplified for 1x1 view)
   - `grid_view.py`: Single camera view widget (fixed at 1x1 layout, multi-grid options removed)
   - `video_widget.py`: Individual video display widget with window handle management
   - Uses PyQt5 (NOT PyQt6 despite requirements.txt listing)

4. **Configuration** (`config/`)
   - `config_manager.py`: YAML/JSON configuration handling (307 lines)
   - `config.yaml`: Camera settings and application configuration

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
3. In single camera mode, handle management is simplified (only one channel)

### Current Configuration: Single Camera Mode
The system is currently configured for single camera operation:
- `config.yaml`: Contains only one enabled camera (cam_01)
- UI: Fixed 1x1 layout (grid switching disabled)
- Recording: Optimized for single stream
- Test scripts: `test_single_camera.py` and `run_single_camera.py` for single camera workflows

## Development Workflow

When modifying the codebase:
1. Test changes with individual test scripts in `reference/` before integration
2. Use `--debug` flag for verbose logging
3. Check GStreamer pipeline graphs using `GST_DEBUG_DUMP_DOT_DIR=/tmp` environment variable
4. For UI changes, test with single camera view (`python run_single_camera.py`)
5. For recording changes, verify file rotation and directory structure
6. For pipeline changes, test valve-based mode switching
7. Run memory monitor to check for leaks: `python tests/memory_monitor.py`
8. For single camera testing, use `python test_single_camera.py` to run all test scenarios

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
- Single camera streaming with real-time display
- Continuous recording with file rotation
- Playback system with timeline navigation
- Configuration management (YAML)
- Auto-reconnection on network failure
- Hardware acceleration support
- Dark theme UI with dockable widgets
- Runtime pipeline mode switching via valves (streaming/recording/both)
- Memory-efficient unified pipeline architecture
- Headless mode for recording without GUI
- Simplified single camera launcher scripts

### Known Issues
- PyQt5/PyQt6 dependency mismatch in requirements.txt
- Settings management UI incomplete (feature #5 in development)
- Some documentation in Korean (README_RECORDING.md, README_SINGLE_CAMERA.md)
- Credentials stored in cleartext in config.yaml (security risk)

### Recent Changes (Single Camera Mode)
- System reconfigured from multi-camera (4-channel) to single camera mode
- UI simplified to 1x1 layout only
- Grid layout switching options removed
- New test and launcher scripts added: `test_single_camera.py`, `run_single_camera.py`
- Documentation updated: `README_SINGLE_CAMERA.md`

### Platform Support
- **Primary**: Raspberry Pi (3, 4, Zero 2W)
- **Secondary**: Linux (Ubuntu 20.04+, Debian 11+)
- **Experimental**: Windows (limited testing, may require adjustments)

## Korean Language Requirement
답변 및 설명은 한글로 작성한다. (All responses and explanations should be in Korean)