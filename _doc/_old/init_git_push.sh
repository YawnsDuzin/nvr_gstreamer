#!/bin/bash

# Git 초기 설정 및 GitHub 푸시 스크립트
# 요구사항: git config의 user.name, user.email이 이미 설정되어 있어야 함

echo "================================================"
echo "   NVR GStreamer Git 초기화 및 푸시 스크립트"
echo "================================================"
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 현재 디렉토리 확인
CURRENT_DIR=$(pwd)
echo -e "${GREEN}현재 디렉토리:${NC} $CURRENT_DIR"
echo ""

# Git 설정 확인
echo -e "${YELLOW}Git 설정 확인...${NC}"
GIT_USER=$(git config user.name)
GIT_EMAIL=$(git config user.email)

if [ -z "$GIT_USER" ] || [ -z "$GIT_EMAIL" ]; then
    echo -e "${RED}에러: Git user.name 또는 user.email이 설정되어 있지 않습니다.${NC}"
    echo "다음 명령어로 설정해주세요:"
    echo "  git config --global user.name \"Your Name\""
    echo "  git config --global user.email \"your.email@example.com\""
    exit 1
fi

echo -e "Git User: ${GREEN}$GIT_USER${NC}"
echo -e "Git Email: ${GREEN}$GIT_EMAIL${NC}"
echo ""

# 기존 .git 디렉토리가 있는지 확인
if [ -d ".git" ]; then
    echo -e "${YELLOW}경고: 기존 .git 디렉토리가 발견되었습니다.${NC}"
    read -p "기존 git 저장소를 제거하고 새로 시작하시겠습니까? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .git
        echo -e "${GREEN}기존 .git 디렉토리를 제거했습니다.${NC}"
    else
        echo -e "${YELLOW}스크립트를 종료합니다.${NC}"
        exit 0
    fi
fi

# Git 저장소 초기화
echo -e "${YELLOW}Git 저장소 초기화...${NC}"
git init
echo -e "${GREEN}✓ Git 저장소가 초기화되었습니다.${NC}"
echo ""

# main 브랜치로 변경
echo -e "${YELLOW}main 브랜치 생성...${NC}"
git checkout -b main
echo -e "${GREEN}✓ main 브랜치가 생성되었습니다.${NC}"
echo ""

# 모든 파일 추가
echo -e "${YELLOW}파일 추가...${NC}"
git add .
echo -e "${GREEN}✓ 모든 파일이 스테이징되었습니다.${NC}"
echo ""

# 추가된 파일 목록 표시
echo -e "${YELLOW}추가된 파일 목록:${NC}"
git status --short
echo ""

# 첫 번째 커밋
echo -e "${YELLOW}첫 번째 커밋 생성...${NC}"
git commit -m "Initial commit: NVR GStreamer project

- RTSP streaming and recording system
- Unified pipeline for efficient resource usage
- PyQt6 GUI interface
- Raspberry Pi optimized
- Multi-camera support"

echo -e "${GREEN}✓ 커밋이 생성되었습니다.${NC}"
echo ""

# 원격 저장소 추가
echo -e "${YELLOW}원격 저장소 추가...${NC}"
REPO_URL="https://github.com/YawnsDuzin/nvr_gstreamer.git"
git remote add origin $REPO_URL
echo -e "${GREEN}✓ 원격 저장소가 추가되었습니다: $REPO_URL${NC}"
echo ""

# GitHub에 푸시
echo -e "${YELLOW}GitHub에 푸시 중...${NC}"
echo -e "${YELLOW}(GitHub 인증이 필요할 수 있습니다)${NC}"

# 푸시 실행
if git push -u origin main; then
    echo -e "${GREEN}✓ 성공적으로 GitHub에 푸시되었습니다!${NC}"
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}   프로젝트가 성공적으로 GitHub에 업로드되었습니다!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "저장소 URL: ${GREEN}https://github.com/YawnsDuzin/nvr_gstreamer${NC}"
    echo ""
else
    echo -e "${RED}푸시 실패!${NC}"
    echo ""
    echo -e "${YELLOW}다음을 확인해주세요:${NC}"
    echo "1. GitHub 저장소가 생성되어 있는지 확인"
    echo "2. 인증 정보(토큰/패스워드)가 올바른지 확인"
    echo "3. 저장소 URL이 올바른지 확인"
    echo ""
    echo "수동으로 푸시하려면:"
    echo "  git remote -v  # 원격 저장소 확인"
    echo "  git push -u origin main"
    exit 1
fi

# 추가 정보 표시
echo -e "${YELLOW}다음 단계:${NC}"
echo "1. GitHub에서 저장소 확인: https://github.com/YawnsDuzin/nvr_gstreamer"
echo "2. README.md 파일 확인 및 수정"
echo "3. LICENSE 파일 추가 (필요한 경우)"
echo "4. requirements.txt 파일 생성:"
echo "   pip freeze > requirements.txt"
echo ""
echo -e "${GREEN}Git 작업이 완료되었습니다!${NC}"