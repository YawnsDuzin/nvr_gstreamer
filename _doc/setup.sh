#!/bin/bash
# NVR 시스템 초기 설정 스크립트

echo "==================================="
echo "NVR System Setup"
echo "==================================="

# 스크립트 실행 권한 설정
chmod +x start_nvr.sh
chmod +x run_nvr.py

# 필요한 디렉토리 생성
echo "Creating directories..."
mkdir -p logs
mkdir -p recordings
mkdir -p config

# Python 패키지 설치 확인
echo ""
echo "Checking Python packages..."
echo ""

# PyQt5 확인
if python3 -c "import PyQt5" 2>/dev/null; then
    echo "✓ PyQt5 installed"
else
    echo "✗ PyQt5 not installed"
    echo "  Install with: pip3 install PyQt5"
fi

# loguru 확인
if python3 -c "import loguru" 2>/dev/null; then
    echo "✓ loguru installed"
else
    echo "✗ loguru not installed"
    echo "  Install with: pip3 install loguru"
fi

# GStreamer Python 확인
if python3 -c "import gi; gi.require_version('Gst', '1.0')" 2>/dev/null; then
    echo "✓ GStreamer Python bindings installed"
else
    echo "✗ GStreamer Python bindings not installed"
    echo "  Install with: sudo apt-get install python3-gi python3-gi-cairo gir1.2-gstreamer-1.0"
fi

# PyYAML 확인
if python3 -c "import yaml" 2>/dev/null; then
    echo "✓ PyYAML installed"
else
    echo "✗ PyYAML not installed"
    echo "  Install with: pip3 install pyyaml"
fi

echo ""
echo "==================================="
echo "Setup complete!"
echo ""
echo "To start NVR:"
echo "  ./start_nvr.sh"
echo ""
echo "Or directly:"
echo "  python3 run_nvr.py"
echo "==================================="