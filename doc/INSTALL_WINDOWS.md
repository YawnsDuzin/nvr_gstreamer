# Windows에서 GStreamer NVR 설치 가이드

## 현재 상태
✅ Python 3.13.5 설치됨
✅ PyQt5 설치됨
✅ loguru 설치됨
✅ pyyaml 설치됨
❌ PyGObject (GStreamer Python 바인딩) 설치 필요

## PyGObject 설치 방법 (Windows)

Windows에서 PyGObject를 설치하는 것은 C 컴파일러가 필요하므로 복잡합니다.
다음 방법들 중 하나를 선택하세요:

### 방법 1: MSYS2를 사용한 설치 (권장)

1. **MSYS2 설치**
   - https://www.msys2.org/ 에서 다운로드
   - 기본 경로에 설치: `C:\msys64`

2. **MSYS2 MinGW 64-bit 터미널 실행**

   **중요**: "MSYS2 MSYS" 터미널이 아닌 **"MSYS2 MinGW 64-bit"** 터미널을 사용하세요!

   ```bash
   # 패키지 데이터베이스 업데이트
   pacman -Syu

   # 모든 필수 패키지 한 번에 설치 (권장)
   pacman -S --noconfirm \
     mingw-w64-x86_64-python \
     mingw-w64-x86_64-python-pip \
     mingw-w64-x86_64-python-gobject \
     mingw-w64-x86_64-python-pyqt5 \
     mingw-w64-x86_64-python-yaml \
     mingw-w64-x86_64-gstreamer \
     mingw-w64-x86_64-gst-plugins-base \
     mingw-w64-x86_64-gst-plugins-good \
     mingw-w64-x86_64-gst-plugins-bad \
     mingw-w64-x86_64-gst-plugins-ugly \
     mingw-w64-x86_64-gst-libav
   ```

3. **가상환경 생성 및 loguru 설치**

   MSYS2는 시스템 패키지를 관리하므로 `pip install`이 직접 안됩니다.
   가상환경을 사용해야 합니다:

   ```bash
   # 프로젝트 디렉토리로 이동
   cd /d/Project/NVR_PYTHON/Source/nvr_gstreamer/nvr_gstreamer

   # 가상환경 생성
   python -m venv venv

   # 가상환경 활성화
   source venv/bin/activate

   # loguru 설치 (pacman에는 없는 패키지)
   pip install loguru
   ```

4. **설치 확인**
   ```bash
   # GStreamer 확인
   python -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('GStreamer:', Gst.version_string())"

   # PyQt5 확인
   python -c "import PyQt5; print('PyQt5 OK')"

   # loguru 확인
   python -c "from loguru import logger; print('loguru OK')"

   # PyYAML 확인
   python -c "import yaml; print('PyYAML OK')"
   ```

5. **환경 변수 설정 (선택사항)**

   Windows 시스템 환경 변수에 추가하면 일반 CMD/PowerShell에서도 사용 가능:
   - Path에 추가: `C:\msys64\mingw64\bin`

6. **MSYS2 터미널에서 프로그램 실행**
   ```bash
   # 가상환경 활성화 (새 터미널을 열 때마다 필요)
   cd /d/Project/NVR_PYTHON/Source/nvr_gstreamer/nvr_gstreamer
   source venv/bin/activate

   # 프로그램 실행
   python run_single_camera.py --debug
   ```

### 방법 2: Anaconda/Miniconda 사용

1. **Anaconda 설치**
   - https://www.anaconda.com/download 에서 다운로드

2. **Conda 환경 생성 및 패키지 설치**
   ```bash
   conda create -n nvr python=3.11
   conda activate nvr
   conda install -c conda-forge pygobject gtk3 gstreamer
   pip install PyQt5 loguru pyyaml
   ```

3. **프로그램 실행**
   ```bash
   conda activate nvr
   cd D:\Project\NVR_PYTHON\Source\nvr_gstreamer\nvr_gstreamer
   python run_single_camera.py
   ```

### 방법 3: GStreamer 공식 바이너리 + PyGObject 휠 파일 사용

1. **GStreamer 설치**
   - https://gstreamer.freedesktop.org/download/ 에서 다운로드
   - Runtime과 Development 버전 모두 설치
   - 기본 경로: `C:\gstreamer\1.0\msvc_x86_64`

2. **환경 변수 설정**
   ```
   Path에 추가:
   C:\gstreamer\1.0\msvc_x86_64\bin

   새 변수 추가:
   GST_PLUGIN_PATH=C:\gstreamer\1.0\msvc_x86_64\lib\gstreamer-1.0
   GSTREAMER_ROOT=C:\gstreamer\1.0\msvc_x86_64
   ```

3. **PyGObject 사전 빌드 휠 다운로드**
   - https://github.com/pygobject/pycairo/releases
   - https://github.com/pygobject/pygobject/releases
   - Python 3.13용 .whl 파일 다운로드

4. **휠 파일 설치**
   ```bash
   pip install [다운로드한 pycairo.whl 파일]
   pip install [다운로드한 pygobject.whl 파일]
   ```

### 방법 4: Visual Studio Build Tools 설치 후 빌드 (고급)

1. **Visual Studio Build Tools 설치**
   - https://visualstudio.microsoft.com/downloads/
   - "C++ 빌드 도구" 선택

2. **pkg-config 및 GTK 설치**
   - https://github.com/wingtk/gvsbuild 사용

3. **PyGObject 설치**
   ```bash
   pip install pygobject
   ```

## 임시 해결책: GStreamer 없이 테스트

GStreamer 설치가 복잡하다면, 먼저 UI만 테스트할 수 있습니다:

```python
# test_ui_only.py 생성
from PyQt5.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
print("✓ PyQt5가 정상적으로 작동합니다!")
sys.exit(0)
```

## 권장 방법

**가장 쉬운 방법**: MSYS2 사용 (방법 1)
- 모든 의존성이 자동으로 설치됨
- Windows에서 Linux 스타일 개발 환경 제공
- GStreamer와 Python이 잘 통합됨

## GStreamer 설치 확인

설치 후 다음 명령으로 확인:

```bash
# GStreamer 버전 확인
gst-launch-1.0 --version

# Python에서 GStreamer 임포트 테스트
python -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print('GStreamer OK')"
```

## 도움이 필요하면

1. MSYS2 방법이 가장 안정적입니다
2. Anaconda가 이미 설치되어 있다면 방법 2 사용
3. 문제가 계속되면 Linux VM이나 WSL2 사용 권장

## 일반적인 문제 해결

### 문제 1: "python3: command not found"

**원인**: MSYS2에서는 `python3` 대신 `python` 명령을 사용합니다.

**해결**:
```bash
python --version  # python3 대신 python 사용
python run_single_camera.py
```

### 문제 2: "externally-managed-environment" 오류

**원인**: MSYS2 Python은 시스템 패키지 관리자(pacman)로 관리되므로 직접 pip 사용 불가

**해결**:
```bash
# 방법 1: pacman으로 설치
pacman -S mingw-w64-x86_64-python-패키지명

# 방법 2: 가상환경 사용 (권장)
python -m venv venv
source venv/bin/activate
pip install loguru
```

### 문제 3: PyQt5 빌드 오류

**원인**: pip로 PyQt5를 설치하려고 하면 C++ 컴파일러가 필요합니다.

**해결**:
```bash
# pip 대신 pacman으로 설치
pacman -S mingw-w64-x86_64-python-pyqt5
```

### 문제 4: 가상환경에서 GStreamer를 찾을 수 없음

**원인**: 가상환경은 시스템 패키지를 상속받지 않습니다.

**해결**: 가상환경 생성 시 `--system-site-packages` 옵션 사용
```bash
python -m venv --system-site-packages venv
source venv/bin/activate
pip install loguru
```

### 문제 5: "No module named 'gi'"

**원인**: PyGObject가 설치되지 않았습니다.

**해결**:
```bash
# MSYS2에서
pacman -S mingw-w64-x86_64-python-gobject

# 또는 가상환경에 --system-site-packages 사용
```

## 빠른 시작 체크리스트 (MSYS2)

MSYS2 MinGW 64-bit 터미널에서 순서대로 실행:

```bash
# 1. 시스템 패키지 설치
pacman -S --noconfirm \
  mingw-w64-x86_64-python \
  mingw-w64-x86_64-python-pip \
  mingw-w64-x86_64-python-gobject \
  mingw-w64-x86_64-python-pyqt5 \
  mingw-w64-x86_64-python-yaml \
  mingw-w64-x86_64-gstreamer \
  mingw-w64-x86_64-gst-plugins-base \
  mingw-w64-x86_64-gst-plugins-good \
  mingw-w64-x86_64-gst-plugins-bad \
  mingw-w64-x86_64-gst-plugins-ugly \
  mingw-w64-x86_64-gst-libav

# 2. 프로젝트로 이동
cd /d/Project/NVR_PYTHON/Source/nvr_gstreamer/nvr_gstreamer

# 3. 가상환경 생성 (시스템 패키지 접근 허용)
python -m venv --system-site-packages venv

# 4. 가상환경 활성화
source venv/bin/activate

# 5. loguru 설치
pip install loguru

# 6. 설치 확인
python -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('✓ GStreamer:', Gst.version_string())"
python -c "import PyQt5; print('✓ PyQt5 OK')"
python -c "from loguru import logger; print('✓ loguru OK')"
python -c "import yaml; print('✓ PyYAML OK')"

# 7. config.yaml에 카메라 정보 입력 (Windows 메모장 등으로 편집)

# 8. 프로그램 실행
python run_single_camera.py --debug
```

## 매번 실행할 때

MSYS2 MinGW 64-bit 터미널을 새로 열었을 때:

```bash
cd /d/Project/NVR_PYTHON/Source/nvr_gstreamer/nvr_gstreamer
source venv/bin/activate
python run_single_camera.py
```

## 다음 단계

PyGObject 설치가 완료되면:

```bash
# 디버그 모드로 실행 (상세 로그)
python run_single_camera.py --debug

# 자동 녹화 시작
python run_single_camera.py --recording

# GUI 없이 녹화만 (백그라운드)
python run_single_camera.py --headless

# 종합 테스트
python test_single_camera.py
```