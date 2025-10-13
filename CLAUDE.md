# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based Network Video Recorder (NVR) system using GStreamer for video processing and PyQt5 for the GUI. The system is optimized for embedded devices (Raspberry Pi) and supports multi-camera streaming, continuous recording, and playback.

## Commands

### Installation
```bash
# Install system dependencies (Linux/Raspberry Pi)
sudo apt-get install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav python3-gi python3-gi-cairo gir1.2-gstreamer-1.0

# Install Python dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Main application with 4-channel UI
python main.py

# With debug logging
python main.py --debug

# With custom config
python main.py --config custom_config.yaml

# With playback support
python main_with_playback.py
```

### Testing
```bash
# Test RTSP streaming
python test_stream.py rtsp://admin:password@192.168.0.131:554/stream

# Test unified pipeline (streaming + recording)
python test_unified_pipeline.py --mode both --rtsp <URL>

# Test recording functionality
python test_recording.py

# Test playback with UI
python test_playback.py --mode ui
```

## Architecture

### Unified Pipeline Pattern
The core innovation is a **unified pipeline architecture** that reduces CPU usage by ~50% on embedded systems:

```
RTSP Source → Decode → Tee ─┬─→ Streaming Branch (Display)
                            └─→ Recording Branch (File Storage)
```

Instead of separate pipelines for streaming and recording (which duplicates decoding), a single `tee` element splits the decoded stream. Recording is controlled dynamically using a `valve` element.

### Key Components

1. **Pipeline Management** (`streaming/`)
   - `pipeline_manager.py`: Core GStreamer pipeline lifecycle
   - `unified_pipeline.py`: Unified streaming+recording pipeline
   - `optimized_pipeline.py`: Performance-optimized variant
   - `camera_stream.py`: Individual camera stream handler

2. **Recording System** (`recording/`)
   - `recording_manager.py`: Multi-camera recording with automatic file rotation
   - File organization: `recordings/{camera_id}/{date}/{camera_id}_{date}_{time}.mp4`
   - Rotation intervals: 5/10/30/60 minutes

3. **UI Components** (`ui/`)
   - `main_window_enhanced.py`: Main 4-channel UI window
   - `grid_view.py`: Multi-camera grid layouts (1x1, 2x2, 3x3, 4x4)
   - `video_widget.py`: Individual video display widget
   - Uses PyQt5 (NOT PyQt6 despite requirements.txt)

4. **Configuration** (`config/`)
   - `config_manager.py`: YAML/JSON configuration handling
   - `config.yaml`: Camera settings and application configuration

### Design Patterns
- **Manager Pattern**: PipelineManager, RecordingManager, PlaybackManager
- **State Pattern**: RecordingStatus, PlaybackState, PipelineMode enums
- **Observer Pattern**: GStreamer bus messages, Qt signals/slots
- **Dataclass Pattern**: Configuration objects (AppConfig, CameraConfigData)

## Important Notes

### Dependency Issue
**CRITICAL**: There's a PyQt version mismatch - the code uses PyQt5 but requirements.txt specifies PyQt6. When modifying dependencies, ensure PyQt5 is used.

### GStreamer Pipelines
Different pipeline configurations are used based on the platform and requirements:
- Hardware acceleration: Uses `omxh264dec` (older RPi) or `v4l2h264dec` (newer RPi)
- Software decoding: Uses `avdec_h264` when hardware acceleration is unavailable
- Recording: Bypasses decoding using `h264parse → mp4mux` for efficiency

### Performance Optimization
The system is optimized for Raspberry Pi with:
- Unified pipeline to avoid duplicate decoding
- Queue elements for buffering
- Hardware acceleration when available
- Adaptive decoder selection based on platform

### File Recording Strategy
- Continuous recording with automatic rotation
- Date-based directory structure
- Multiple format support (MP4, MKV, AVI)
- Disk space monitoring and management

## Development Workflow

When modifying the codebase:
1. Test changes with individual test scripts before integration
2. Use `--debug` flag for verbose logging
3. Check GStreamer pipeline graphs using `GST_DEBUG_DUMP_DOT_DIR` environment variable
4. For UI changes, test with different grid layouts (1x1 through 4x4)
5. For recording changes, verify file rotation and directory structure

## Current Status

### Implemented Features
- Multi-camera streaming (up to 4 cameras)
- Continuous recording with file rotation
- Playback system with timeline navigation
- Configuration management (YAML)
- Auto-reconnection on network failure
- Hardware acceleration support
- Dark theme UI with dockable widgets

### Known Issues
- Screen flickering reported (status unclear)
- No automated test suite despite pytest in requirements
- Documentation partially in Korean (README_RECORDING.md, prompts.md)
- Settings management feature (#5) incomplete according to prompts.md
- 모든 답변 및 설명은 한글로 한다.