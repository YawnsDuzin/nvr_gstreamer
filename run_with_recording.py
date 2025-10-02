#!/usr/bin/env python3
"""
PyNVR 실행 스크립트 (녹화 기능 포함)
"""

import sys
import os
from pathlib import Path

# 현재 디렉토리를 파이썬 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 메인 실행
if __name__ == "__main__":
    from main import main
    main()