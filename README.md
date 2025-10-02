# NVR GStreamer

A Network Video Recorder (NVR) system built with Python and GStreamer for RTSP stream recording and monitoring.

## Features

- **RTSP Stream Support**: Connect to IP cameras via RTSP protocol
- **Real-time Streaming**: Live video streaming with low latency
- **Recording Management**: Continuous recording with automatic file rotation
- **Unified Pipeline**: Efficient single-pipeline architecture for both streaming and recording
- **Multi-camera Support**: Handle multiple camera streams simultaneously
- **PyQt6 GUI**: Modern and intuitive user interface
- **Raspberry Pi Optimized**: Designed for resource-constrained environments

## System Architecture

### Unified Pipeline
The system uses a unified GStreamer pipeline that efficiently handles both streaming and recording through a single pipeline, reducing resource consumption on devices like Raspberry Pi.

```
RTSP Source → Decode → Tee ─┬─→ Streaming Branch (Display)
                            └─→ Recording Branch (File Storage)
```

## Requirements

- Python 3.8+
- GStreamer 1.0
- PyQt6
- Additional Python packages (see requirements.txt)

## Installation

### Prerequisites

1. Install GStreamer and dependencies:
```bash
# Ubuntu/Debian/Raspberry Pi OS
sudo apt-get update
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0

# For Raspberry Pi hardware acceleration
sudo apt-get install -y gstreamer1.0-omx-generic
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

1. **Run the main application**:
```bash
python nvr_gstreamer/main.py
```

2. **Test unified pipeline**:
```bash
# Test streaming only
python nvr_gstreamer/test_unified_pipeline.py --mode streaming --rtsp rtsp://your_camera_url

# Test recording only
python nvr_gstreamer/test_unified_pipeline.py --mode recording --rtsp rtsp://your_camera_url

# Test both streaming and recording
python nvr_gstreamer/test_unified_pipeline.py --mode both --rtsp rtsp://your_camera_url
```

### Configuration

The system can be configured through the GUI or by editing configuration files:

- Camera settings (URL, credentials)
- Recording parameters (file format, duration, storage path)
- Streaming settings (resolution, codec)

### API Example

```python
from nvr_gstreamer.streaming.unified_pipeline import UnifiedPipeline, PipelineMode

# Create unified pipeline for streaming and recording
pipeline = UnifiedPipeline(
    rtsp_url="rtsp://admin:password@192.168.1.100:554/stream1",
    camera_id="cam01",
    camera_name="Front Camera",
    mode=PipelineMode.BOTH
)

# Start pipeline
if pipeline.create_pipeline():
    pipeline.start()

    # Start recording
    pipeline.start_recording()

    # ... do something ...

    # Stop recording
    pipeline.stop_recording()

    # Stop pipeline
    pipeline.stop()
```

## Project Structure

```
nvr_gstreamer/
├── streaming/          # Streaming pipeline modules
│   ├── unified_pipeline.py    # Unified pipeline implementation
│   ├── pipeline_manager.py    # Pipeline management
│   └── camera_stream.py       # Camera stream handling
├── recording/          # Recording management
│   └── recording_manager.py   # Recording control and file management
├── ui/                 # PyQt6 GUI components
│   ├── main_window.py         # Main application window
│   ├── video_widget.py        # Video display widget
│   └── grid_view.py           # Multi-camera grid view
├── config/            # Configuration management
│   └── config_manager.py      # Settings and configuration
├── main.py            # Application entry point
└── test_*.py          # Test scripts
```

## Features in Detail

### Streaming
- Real-time RTSP stream decoding and display
- Hardware acceleration support (Raspberry Pi OMX/V4L2)
- Adaptive buffering for network stability
- Multiple camera grid view

### Recording
- Continuous recording with automatic file rotation
- Configurable file duration and format (MP4, MKV, AVI)
- Timestamp-based file naming
- Automatic directory organization by date

### Performance Optimization
- Single pipeline architecture reduces CPU usage
- Efficient memory management with GStreamer queues
- Hardware decoder selection for Raspberry Pi
- Configurable buffer sizes and threading

## Troubleshooting

### Common Issues

1. **Stream not displaying**:
   - Check RTSP URL and network connectivity
   - Verify camera credentials
   - Ensure GStreamer plugins are installed

2. **Recording not starting**:
   - Check disk space availability
   - Verify write permissions for recording directory
   - Ensure pipeline mode includes recording

3. **High CPU usage**:
   - Enable hardware acceleration
   - Reduce stream resolution
   - Adjust buffer sizes

### Debug Mode

Enable detailed logging:
```bash
export GST_DEBUG=3
python nvr_gstreamer/main.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- GStreamer team for the excellent multimedia framework
- PyQt team for the GUI framework
- Contributors and testers

## Support

For issues and questions, please use the GitHub issue tracker.

## Roadmap

- [ ] Motion detection
- [ ] Cloud storage integration
- [ ] Mobile app support
- [ ] AI-based object detection
- [ ] Web interface
- [ ] Docker support

---

**Note**: This project is optimized for Raspberry Pi but works on any Linux system with GStreamer support.