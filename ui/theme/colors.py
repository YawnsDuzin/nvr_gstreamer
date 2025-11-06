"""
색상 팔레트 정의

테마별 색상을 중앙에서 관리합니다.
"""


class ColorPalette:
    """테마별 색상 정의"""

    DARK = {
        # 배경색 레이어 (통일)
        'bg_primary': '#2a2a2a',       # 메인 배경 (다이얼로그, 설정 탭)
        'bg_secondary': '#3a3a3a',     # 입력 필드, 비선택 탭
        'bg_tertiary': '#252526',      # 도크, 그룹박스
        'bg_hover': '#4a4a4a',         # 호버 상태
        'bg_pressed': '#1a1a1a',       # 눌림 상태
        'bg_alternate': '#252525',     # 테이블 교대 행
        'bg_window': '#1e1e1e',        # 메인 윈도우, 테이블 배경

        # 텍스트 색상
        'text_primary': '#ffffff',     # 주 텍스트
        'text_secondary': '#cccccc',   # 부 텍스트
        'text_disabled': '#666666',    # 비활성 텍스트
        'text_info': '#999999',        # 정보성 텍스트

        # 보더 및 분리선
        'border': '#4a4a4a',           # 기본 보더
        'border_light': '#3c3c3c',     # 얇은 보더

        # 강조 색상 (통일!)
        'accent': '#007acc',           # 포커스, 선택 상태
        'accent_hover': '#1c97ea',     # 강조 색상 호버
        'accent_pressed': '#005a9e',   # 강조 색상 눌림

        # 상태 색상
        'success': '#44ff44',          # 연결됨, 성공
        'warning': '#ff9944',          # 경고, 대기 (통일!)
        'error': '#ff4444',            # 에러, 녹화 중
        'info': '#5a9fd4',             # 정보

        # 특수 용도
        'selection_bg': '#094771',     # 테이블 선택 배경
        'dock_title': '#2d2d30',       # 도크 타이틀바
        'dock_separator': '#3c3c3c',   # 도크 분리선
        'video_bg': '#0a0a0a',         # 비디오 배경
        'scrollbar_bg': '#1e1e1e',     # 스크롤바 배경
        'scrollbar_handle': '#424242', # 스크롤바 핸들
        'scrollbar_hover': '#4e4e4e',  # 스크롤바 호버
        'menu_separator': '#3c3c3c',   # 메뉴 분리선
        'tooltip_bg': '#3c3c3c',       # 툴팁 배경
    }

    LIGHT = {
        # 배경색 레이어
        'bg_primary': '#ffffff',       # 메인 배경
        'bg_secondary': '#f5f5f5',     # 입력 필드
        'bg_tertiary': '#f0f0f0',      # 도크, 그룹박스
        'bg_hover': '#e0e0e0',         # 호버 상태
        'bg_pressed': '#d0d0d0',       # 눌림 상태
        'bg_alternate': '#f9f9f9',     # 테이블 교대 행
        'bg_window': '#f3f3f3',        # 메인 윈도우

        # 텍스트 색상
        'text_primary': '#1e1e1e',     # 주 텍스트
        'text_secondary': '#606060',   # 부 텍스트
        'text_disabled': '#a0a0a0',    # 비활성 텍스트
        'text_info': '#707070',        # 정보성 텍스트

        # 보더 및 분리선
        'border': '#cccccc',           # 기본 보더
        'border_light': '#e0e0e0',     # 얇은 보더

        # 강조 색상
        'accent': '#0078d4',           # 포커스, 선택 상태
        'accent_hover': '#106ebe',     # 강조 색상 호버
        'accent_pressed': '#005a9e',   # 강조 색상 눌림

        # 상태 색상
        'success': '#107c10',          # 연결됨, 성공
        'warning': '#ff8c00',          # 경고, 대기
        'error': '#e81123',            # 에러
        'info': '#0078d4',             # 정보

        # 특수 용도
        'selection_bg': '#cce8ff',     # 테이블 선택 배경
        'dock_title': '#f5f5f5',       # 도크 타이틀바
        'dock_separator': '#e0e0e0',   # 도크 분리선
        'video_bg': '#f0f0f0',         # 비디오 배경
        'scrollbar_bg': '#f0f0f0',     # 스크롤바 배경
        'scrollbar_handle': '#c0c0c0', # 스크롤바 핸들
        'scrollbar_hover': '#a0a0a0',  # 스크롤바 호버
        'menu_separator': '#e0e0e0',   # 메뉴 분리선
        'tooltip_bg': '#f5f5f5',       # 툴팁 배경
    }

    @classmethod
    def get_color(cls, theme: str, key: str) -> str:
        """
        색상 가져오기

        Args:
            theme: 'dark' 또는 'light'
            key: 색상 키 (예: 'bg_primary', 'accent')

        Returns:
            HEX 색상 코드 (예: '#2a2a2a')
        """
        palette = cls.DARK if theme == 'dark' else cls.LIGHT
        return palette.get(key, '#000000')

    @classmethod
    def get_palette(cls, theme: str) -> dict:
        """
        전체 팔레트 가져오기

        Args:
            theme: 'dark' 또는 'light'

        Returns:
            색상 딕셔너리
        """
        return cls.DARK if theme == 'dark' else cls.LIGHT
