@echo off
setlocal enabledelayedexpansion

REM Git 초기 설정 및 GitHub 푸시 스크립트 (Windows)
REM 요구사항: git config의 user.name, user.email이 이미 설정되어 있어야 함

echo ================================================
echo    NVR GStreamer Git 초기화 및 푸시 스크립트
echo ================================================
echo.

REM 현재 디렉토리 확인
echo 현재 디렉토리: %CD%
echo.

REM Git 설정 확인
echo Git 설정 확인...
for /f "tokens=*" %%i in ('git config user.name') do set GIT_USER=%%i
for /f "tokens=*" %%i in ('git config user.email') do set GIT_EMAIL=%%i

if "%GIT_USER%"=="" (
    echo 에러: Git user.name이 설정되어 있지 않습니다.
    echo 다음 명령어로 설정해주세요:
    echo   git config --global user.name "Your Name"
    echo   git config --global user.email "your.email@example.com"
    exit /b 1
)

if "%GIT_EMAIL%"=="" (
    echo 에러: Git user.email이 설정되어 있지 않습니다.
    echo 다음 명령어로 설정해주세요:
    echo   git config --global user.name "Your Name"
    echo   git config --global user.email "your.email@example.com"
    exit /b 1
)

echo Git User: %GIT_USER%
echo Git Email: %GIT_EMAIL%
echo.

REM 기존 .git 디렉토리가 있는지 확인
if exist ".git" (
    echo 경고: 기존 .git 디렉토리가 발견되었습니다.
    set /p CONFIRM=기존 git 저장소를 제거하고 새로 시작하시겠습니까? (y/n):
    if /i "!CONFIRM!"=="y" (
        rmdir /s /q .git
        echo 기존 .git 디렉토리를 제거했습니다.
    ) else (
        echo 스크립트를 종료합니다.
        exit /b 0
    )
)

REM Git 저장소 초기화
echo Git 저장소 초기화...
git init
if %ERRORLEVEL% neq 0 (
    echo Git 초기화 실패!
    exit /b 1
)
echo √ Git 저장소가 초기화되었습니다.
echo.

REM main 브랜치로 변경
echo main 브랜치 생성...
git checkout -b main
if %ERRORLEVEL% neq 0 (
    echo 브랜치 생성 실패!
    exit /b 1
)
echo √ main 브랜치가 생성되었습니다.
echo.

REM 모든 파일 추가
echo 파일 추가...
git add .
if %ERRORLEVEL% neq 0 (
    echo 파일 추가 실패!
    exit /b 1
)
echo √ 모든 파일이 스테이징되었습니다.
echo.

REM 추가된 파일 목록 표시
echo 추가된 파일 목록:
git status --short
echo.

REM 첫 번째 커밋
echo 첫 번째 커밋 생성...
git commit -m "Initial commit: NVR GStreamer project" -m "- RTSP streaming and recording system" -m "- Unified pipeline for efficient resource usage" -m "- PyQt6 GUI interface" -m "- Raspberry Pi optimized" -m "- Multi-camera support"
if %ERRORLEVEL% neq 0 (
    echo 커밋 생성 실패!
    exit /b 1
)
echo √ 커밋이 생성되었습니다.
echo.

REM 원격 저장소 추가
echo 원격 저장소 추가...
set REPO_URL=https://github.com/YawnsDuzin/nvr_gstreamer.git
git remote add origin %REPO_URL%
if %ERRORLEVEL% neq 0 (
    echo 원격 저장소가 이미 존재합니다. 업데이트 중...
    git remote set-url origin %REPO_URL%
)
echo √ 원격 저장소가 추가되었습니다: %REPO_URL%
echo.

REM GitHub에 푸시
echo GitHub에 푸시 중...
echo (GitHub 인증이 필요할 수 있습니다)
echo.

git push -u origin main
if %ERRORLEVEL% equ 0 (
    echo.
    echo √ 성공적으로 GitHub에 푸시되었습니다!
    echo.
    echo ================================================
    echo    프로젝트가 성공적으로 GitHub에 업로드되었습니다!
    echo ================================================
    echo.
    echo 저장소 URL: https://github.com/YawnsDuzin/nvr_gstreamer
    echo.
    echo 다음 단계:
    echo 1. GitHub에서 저장소 확인: https://github.com/YawnsDuzin/nvr_gstreamer
    echo 2. README.md 파일 확인 및 수정
    echo 3. LICENSE 파일 추가 (필요한 경우)
    echo 4. requirements.txt 파일 생성:
    echo    pip freeze ^> requirements.txt
    echo.
    echo Git 작업이 완료되었습니다!
) else (
    echo.
    echo 푸시 실패!
    echo.
    echo 다음을 확인해주세요:
    echo 1. GitHub 저장소가 생성되어 있는지 확인
    echo    - https://github.com/new 에서 'nvr_gstreamer' 저장소 생성
    echo 2. 인증 정보(토큰/패스워드)가 올바른지 확인
    echo    - Personal Access Token 사용 권장
    echo 3. 저장소 URL이 올바른지 확인
    echo.
    echo 수동으로 푸시하려면:
    echo   git remote -v
    echo   git push -u origin main
    exit /b 1
)

pause