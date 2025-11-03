"""
Key Sequence Edit Widget
키 바인딩 입력 위젯
"""

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence


class KeySequenceEdit(QLineEdit):
    """
    키 입력을 감지하는 커스텀 위젯
    사용자가 키를 누르면 자동으로 키 이름이 표시됨
    """

    key_changed = pyqtSignal(str)  # 키 변경 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Press a key...")
        self._current_key = ""

        # Style
        self.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #5a9fd4;
                background-color: #4a4a4a;
            }
        """)

    def keyPressEvent(self, event):
        """키 입력 이벤트"""
        key = event.key()

        # Escape 키로 초기화
        if key == Qt.Key_Escape:
            self.setText("")
            self._current_key = ""
            self.key_changed.emit("")
            return

        # 특수키 무시 (Shift, Ctrl, Alt 단독)
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            return

        # 키 이름 변환
        key_sequence = QKeySequence(key)
        key_name = key_sequence.toString()

        # 수정자 키 추가 (Ctrl, Alt, Shift)
        modifiers = event.modifiers()
        modifier_str = ""

        if modifiers & Qt.ControlModifier:
            modifier_str += "Ctrl+"
        if modifiers & Qt.AltModifier:
            modifier_str += "Alt+"
        if modifiers & Qt.ShiftModifier:
            # Shift는 문자키와 함께 눌렸을 때는 제외
            # (예: Shift+A는 그냥 A로 표시)
            if not (key >= Qt.Key_A and key <= Qt.Key_Z):
                modifier_str += "Shift+"

        final_key = modifier_str + key_name

        self.setText(final_key)
        self._current_key = final_key
        self.key_changed.emit(final_key)

    def get_key(self) -> str:
        """현재 키 반환"""
        return self._current_key

    def set_key(self, key: str):
        """키 설정"""
        self.setText(key)
        self._current_key = key

    def clear_key(self):
        """키 초기화"""
        self.setText("")
        self._current_key = ""
        self.key_changed.emit("")
