# PyNVR - Network Video Recorder for Raspberry Pi

PyNVR is a lightweight Network Video Recorder system designed for Raspberry Pi, using GStreamer for video processing and PyQt5 for the user interface.

## Features

- **RTSP Stream Support**: Connect to IP cameras via RTSP protocol
- **Multi-Camera Display**: 1x1, 2x2, 3x3, and 4x4 grid layouts
- **Hardware Acceleration**: Support for Raspberry Pi hardware decoding
- **Configuration Management**: YAML-based camera configuration
- **Automatic Reconnection**: Auto-reconnect on stream failure
- **Modular Architecture**: Clean, extensible codebase

## Installation

### Prerequisites

On Raspberry Pi (Raspbian/Raspberry Pi OS):

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-omx \
    python3-pyqt5

# Install Python dependencies
pip3 install -r requirements.txt
```

On Ubuntu/Debian:

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-pyqt5

# Install Python dependencies
pip3 install -r requirements.txt
```

## Configuration

Edit `config.yaml` to add your cameras:

```yaml
cameras:
  - camera_id: cam_01
    name: Front Door
    rtsp_url: rtsp://192.168.1.101:554/stream1
    enabled: true
    username: admin
    password: your_password
    use_hardware_decode: true
```

## Usage

### Running the Main Application

```bash
python3 main.py
```

With debug logging:

```bash
python3 main.py --debug
```

### Testing RTSP Stream

Test a single RTSP stream:

```bash
# Direct pipeline test
python3 test_stream.py rtsp://192.168.1.100:554/stream

# With hardware acceleration
python3 test_stream.py rtsp://192.168.1.100:554/stream --hardware

# Test camera stream handler
python3 test_stream.py rtsp://192.168.1.100:554/stream --mode stream

# Test frame capture
python3 test_stream.py rtsp://192.168.1.100:554/stream --mode capture
```

## Project Structure

```
nvr_gstreamer/
├── main.py                 # Main application entry point
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── test_stream.py        # RTSP stream testing utility
│
├── config/               # Configuration management
│   └── config_manager.py
│
├── streaming/           # Video streaming components
│   ├── pipeline_manager.py  # GStreamer pipeline management
│   └── camera_stream.py     # Camera stream handler
│
├── ui/                 # User interface components
│   ├── main_window.py      # Main application window
│   └── video_widget.py     # Video display widgets
│
├── core/              # Core functionality (future)
├── utils/             # Utility functions (future)
└── tests/             # Unit tests (future)
```

## Hardware Acceleration

On Raspberry Pi, hardware acceleration is supported through:
- **OMX**: OpenMAX IL hardware decoder (`omxh264dec`)
- **V4L2**: Video4Linux2 hardware encoder/decoder

The system automatically detects and uses hardware acceleration when available.

## Troubleshooting

### GStreamer not found

If you get GStreamer import errors:

```bash
# Verify GStreamer installation
gst-inspect-1.0 --version

# Check Python GObject bindings
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst"
```

### RTSP Connection Issues

1. Verify camera URL is correct
2. Check network connectivity
3. Ensure camera credentials are correct
4. Test with VLC or ffplay:
   ```bash
   ffplay rtsp://username:password@192.168.1.100:554/stream
   ```

### Performance Issues

1. Enable hardware acceleration in config.yaml
2. Reduce stream resolution at camera
3. Limit number of simultaneous streams
4. Check CPU/memory usage:
   ```bash
   htop
   ```

## Development Status

Current implementation (Phase 1 - Basic Streaming):
- ✅ GStreamer pipeline management
- ✅ Camera stream handler
- ✅ PyQt5 UI with multi-camera grid
- ✅ Configuration management
- ✅ Basic testing utilities

Planned features:
- 🔄 Recording functionality
- 🔄 Playback system
- 🔄 Motion detection
- 🔄 PTZ control
- 🔄 Event management
- 🔄 Web interface

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit pull requests.