"""
Base class for all settings tabs
설정 탭의 추상 베이스 클래스
"""

from abc import ABCMeta, abstractmethod
from PyQt5.QtWidgets import QWidget
from loguru import logger

from core.config import ConfigManager


# QWidget와 ABC를 동시에 상속하기 위한 메타클래스
class CombinedMeta(type(QWidget), ABCMeta):
    """PyQt5와 ABC를 결합한 메타클래스"""
    pass


class BaseSettingsTab(QWidget, metaclass=CombinedMeta):
    """
    설정 탭의 베이스 클래스
    모든 설정 탭은 이 클래스를 상속받아 구현
    """

    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        초기화

        Args:
            config_manager: ConfigManager 인스턴스
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self._original_data = {}  # 원본 데이터 (변경 감지용)
        self._has_unsaved_changes = False  # 저장되지 않은 변경사항 플래그
        self._section_name = None  # 설정 섹션 이름 (예: "ui", "cameras")

    @abstractmethod
    def load_settings(self):
        """
        설정 로드
        서브클래스에서 반드시 구현해야 함
        """
        pass

    @abstractmethod
    def save_settings(self) -> bool:
        """
        설정 저장 (메모리에만)
        서브클래스에서 반드시 구현해야 함

        Note: 이 메서드는 ConfigManager의 메모리 객체만 업데이트합니다.
              실제 DB 저장은 save_to_db()에서 처리합니다.

        Returns:
            bool: 저장 성공 여부
        """
        pass

    def save_to_db(self) -> bool:
        """
        변경된 설정을 DB에 저장

        Returns:
            bool: DB 저장 성공 여부
        """
        # has_changes() 메서드를 사용하여 실제 변경 여부 확인
        if not self.has_changes():
            logger.debug(f"{self.__class__.__name__}: No changes to save")
            return True

        try:
            # 먼저 메모리에 저장
            if not self.save_settings():
                return False

            # 섹션별 DB 저장 (서브클래스에서 오버라이드 가능)
            success = self._save_section_to_db()

            if success:
                # 저장 후 원본 데이터 갱신
                self._update_original_data()
                self._has_unsaved_changes = False
                logger.info(f"{self.__class__.__name__}: Saved to DB successfully")

            return success

        except Exception as e:
            logger.error(f"{self.__class__.__name__}: Failed to save to DB: {e}")
            return False

    def _save_section_to_db(self) -> bool:
        """
        해당 섹션을 DB에 저장
        서브클래스에서 오버라이드하여 구현

        Returns:
            bool: 저장 성공 여부
        """
        # 기본 구현 - 서브클래스에서 오버라이드
        logger.warning(f"{self.__class__.__name__}: _save_section_to_db not implemented")
        return True

    def _update_original_data(self):
        """
        현재 데이터를 원본으로 갱신 (Apply 후 호출)
        서브클래스에서 오버라이드 필요
        """
        pass

    @abstractmethod
    def validate_settings(self) -> tuple[bool, str]:
        """
        설정 검증
        서브클래스에서 반드시 구현해야 함

        Returns:
            tuple[bool, str]: (검증 성공 여부, 에러 메시지)
        """
        pass

    def has_changes(self) -> bool:
        """
        변경 사항이 있는지 확인
        서브클래스에서 오버라이드 가능

        Returns:
            bool: 변경 사항 존재 여부
        """
        # 기본 구현: 플래그 확인
        # 서브클래스에서 필요시 오버라이드하여 실시간 비교 가능
        return self._has_unsaved_changes

    def mark_as_changed(self):
        """변경사항 발생 표시"""
        self._has_unsaved_changes = True
        logger.debug(f"{self.__class__.__name__}: Marked as changed")

    def mark_as_saved(self):
        """저장 완료 표시"""
        self._has_unsaved_changes = False
        logger.debug(f"{self.__class__.__name__}: Marked as saved")

    def _store_original_data(self, data: dict):
        """
        원본 데이터 저장 (변경 감지용)

        Args:
            data: 원본 데이터 딕셔너리
        """
        import copy
        self._original_data = copy.deepcopy(data)

    def _get_original_data(self) -> dict:
        """
        원본 데이터 반환

        Returns:
            dict: 원본 데이터
        """
        import copy
        return copy.deepcopy(self._original_data)

    def reset_to_original(self):
        """
        원본 데이터로 되돌리기
        서브클래스에서 오버라이드 가능
        """
        if self._original_data:
            self.load_settings()
            logger.debug(f"{self.__class__.__name__}: Reset to original settings")
