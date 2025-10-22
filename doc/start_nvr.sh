#!/bin/bash
# NVR 시스템 시작 스크립트

echo "Starting NVR System..."

# 현재 디렉토리 저장
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Python 경로 설정
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# GStreamer 환경 변수
export GST_DEBUG=2

# 로그 디렉토리 생성
mkdir -p logs
mkdir -p recordings

# Python 버전 확인
python3 --version

# 필요한 패키지 확인
echo "Checking dependencies..."
python3 -c "import PyQt5" 2>/dev/null || echo "Warning: PyQt5 not installed"
python3 -c "import gi; gi.require_version('Gst', '1.0')" 2>/dev/null || echo "Warning: GStreamer Python bindings not installed"

# NVR 실행
echo "Launching NVR..."
python3 run_nvr.py "$@"