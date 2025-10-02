#!/bin/bash
# Install GStreamer packages for Raspberry Pi

echo "Installing GStreamer packages for Raspberry Pi..."

# Update package list
sudo apt-get update

# Install GStreamer base packages
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3 \
    gstreamer1.0-pulseaudio

# Install Python GStreamer bindings
sudo apt-get install -y \
    python3-gst-1.0 \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0

# Try to install hardware acceleration support
echo "Checking for hardware acceleration support..."

# For newer Raspberry Pi OS (V4L2)
sudo apt-get install -y gstreamer1.0-libcamera 2>/dev/null || echo "libcamera not available"

# For older Raspberry Pi OS (OMX)
sudo apt-get install -y gstreamer1.0-omx-rpi gstreamer1.0-omx-rpi-config 2>/dev/null || echo "OMX not available"

# Install V4L2 utilities
sudo apt-get install -y v4l-utils

echo "GStreamer installation complete!"
echo ""
echo "Checking available decoders..."
gst-inspect-1.0 | grep -i h264 | grep -i dec

echo ""
echo "Testing GStreamer..."
gst-launch-1.0 --version

echo ""
echo "Installation complete! You can now run the PyNVR application."