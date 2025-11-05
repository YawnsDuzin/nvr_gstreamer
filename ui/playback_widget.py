"""
재생 위젯
녹화된 파일을 재생하는 UI 위젯
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QGroupBox,
    QComboBox, QDateEdit, QMessageBox, QStyle,
    QSizePolicy, QHeaderView, QTableWidget, QTableWidgetItem, QCheckBox, QWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDateTime, QDate
from PyQt5.QtGui import QIcon
from typing import Optional, List
from datetime import datetime
from loguru import logger
from pathlib import Path

from ui.theme import ThemedWidget
from camera.playback import PlaybackManager, PlaybackState, RecordingFile


class PlaybackControlWidget(ThemedWidget):
    """재생 컨트롤 위젯"""

    # 시그널
    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    seek_requested = pyqtSignal(float)
    speed_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self._is_playing = False
        self._duration = 0
        self._position = 0

    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 비디오 디스플레이 영역 (placeholder)
        self.video_widget = QWidget()
        self.video_widget.setMinimumHeight(300)
        self.video_widget.setObjectName("videoWidget")  # Set object name for styling
        # Background color will be set by main window theme
        layout.addWidget(self.video_widget)

        # 시크바
        seek_layout = QHBoxLayout()

        self.position_label = QLabel("00:00")
        self.position_label.setMinimumWidth(50)
        seek_layout.addWidget(self.position_label)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self._on_seek_slider_released)
        self.seek_slider.sliderPressed.connect(self._on_seek_slider_pressed)
        seek_layout.addWidget(self.seek_slider)

        self.duration_label = QLabel("00:00")
        self.duration_label.setMinimumWidth(50)
        seek_layout.addWidget(self.duration_label)

        layout.addLayout(seek_layout)

        # 컨트롤 버튼
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        # 재생/일시정지 버튼
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self._on_play_button_clicked)
        self.play_button.setFixedSize(40, 40)
        control_layout.addWidget(self.play_button)

        # 정지 버튼
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        self.stop_button.setFixedSize(40, 40)
        control_layout.addWidget(self.stop_button)

        control_layout.addStretch()

        # 재생 속도 선택
        control_layout.addWidget(QLabel("속도:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x", "4.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        control_layout.addWidget(self.speed_combo)

        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 슬라이더 업데이트 플래그
        self._slider_pressed = False

    def _on_play_button_clicked(self):
        """재생/일시정지 버튼 클릭"""
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()

    def _on_seek_slider_pressed(self):
        """시크바 눌림"""
        self._slider_pressed = True

    def _on_seek_slider_released(self):
        """시크바 놓임"""
        position = self.seek_slider.value() / 1000.0 * self._duration
        self.seek_requested.emit(position)
        self._slider_pressed = False

    def _on_speed_changed(self, text: str):
        """재생 속도 변경"""
        speed = float(text.replace('x', ''))
        self.speed_changed.emit(speed)

    def set_playing(self, is_playing: bool):
        """재생 상태 설정"""
        self._is_playing = is_playing
        if is_playing:
            self.play_button.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPause)
            )
        else:
            self.play_button.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPlay)
            )

    def update_position(self, position: float, duration: float):
        """재생 위치 업데이트"""
        self._position = position
        self._duration = duration

        # 슬라이더 업데이트 (드래그 중이 아닐 때만)
        if not self._slider_pressed and duration > 0:
            slider_pos = int((position / duration) * 1000)
            self.seek_slider.setValue(slider_pos)

        # 라벨 업데이트
        self.position_label.setText(self._format_time(position))
        self.duration_label.setText(self._format_time(duration))

    def _format_time(self, seconds: float) -> str:
        """시간 포맷팅"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def get_video_widget_id(self):
        """비디오 위젯 윈도우 ID 반환"""
        return int(self.video_widget.winId())

    def reset(self):
        """컨트롤 리셋"""
        self.set_playing(False)
        self.seek_slider.setValue(0)
        self.position_label.setText("00:00")
        self.duration_label.setText("00:00")
        self.speed_combo.setCurrentText("1.0x")


class RecordingListWidget(ThemedWidget):
    """녹화 파일 목록 위젯"""

    # 시그널
    file_selected = pyqtSignal(str)  # 파일 경로
    file_deleted = pyqtSignal(list)  # 파일 경로 리스트

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.recording_files: List[RecordingFile] = []

    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)

        # 필터 섹션 (모두 한 줄로)
        filter_group = QGroupBox("필터")
        filter_layout = QHBoxLayout()

        # 카메라 선택
        camera_label = QLabel("카메라:")
        camera_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(camera_label)
        self.camera_combo = QComboBox()
        self.camera_combo.addItem("전체")
        self.camera_combo.currentTextChanged.connect(self._apply_filter)
        self.camera_combo.setMinimumWidth(100)
        filter_layout.addWidget(self.camera_combo)

        filter_layout.addSpacing(20)

        # 시작 날짜
        start_label = QLabel("시작:")
        start_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(start_label)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.dateChanged.connect(self._apply_filter)
        self.start_date.setMinimumWidth(120)
        filter_layout.addWidget(self.start_date)

        filter_layout.addSpacing(20)

        # 종료 날짜
        end_label = QLabel("종료:")
        end_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(end_label)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.dateChanged.connect(self._apply_filter)
        self.end_date.setMinimumWidth(120)
        filter_layout.addWidget(self.end_date)

        filter_layout.addStretch()

        # 비디오 변환 필터
        transform_label = QLabel("비디오 변환:")
        transform_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(transform_label)

        self.flip_combo = QComboBox()
        self.flip_combo.addItems(["None", "Horizontal", "Vertical", "Both"])
        self.flip_combo.setToolTip("좌우/상하 반전")
        self.flip_combo.setMinimumWidth(100)
        filter_layout.addWidget(self.flip_combo)

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setToolTip("회전")
        self.rotation_combo.setMinimumWidth(80)
        filter_layout.addWidget(self.rotation_combo)

        filter_layout.addStretch()

        # 새로고침 버튼 (우측 끝)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.refresh_list)
        filter_layout.addWidget(self.refresh_button)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # 파일 목록 테이블
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(6)  # 체크박스 컬럼 추가
        self.file_table.setHorizontalHeaderLabels([
            "선택", "카메라", "파일명", "날짜/시간", "재생시간", "크기"
        ])
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SingleSelection)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 수정 불가
        self.file_table.setAlternatingRowColors(True)
        self.file_table.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 컬럼 너비 조정
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 선택 (체크박스)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 카메라
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 파일명 (남은 공간 차지)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 날짜/시간
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 재생시간
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 크기

        layout.addWidget(self.file_table)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        # 전체 선택 버튼
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.clicked.connect(self._select_all)
        button_layout.addWidget(select_all_btn)

        # 전체 해제 버튼
        deselect_all_btn = QPushButton("전체 해제")
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addStretch()

        # 백업 버튼
        self.backup_btn = QPushButton("백업")
        self.backup_btn.clicked.connect(self._backup_selected)
        # Theme color will be applied by ThemeManager - no hardcoded style
        button_layout.addWidget(self.backup_btn)

        # 선택 삭제 버튼
        delete_btn = QPushButton("선택 삭제")
        delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

    def update_file_list(self, files: List[RecordingFile]):
        """파일 목록 업데이트"""
        self.recording_files = files
        self._update_camera_filter()
        self._apply_filter()

    def _update_camera_filter(self):
        """카메라 필터 업데이트"""
        # 현재 선택 저장
        current = self.camera_combo.currentText()

        # 카메라 목록 업데이트
        self.camera_combo.clear()
        self.camera_combo.addItem("전체")

        camera_ids = set(f.camera_id for f in self.recording_files)
        for camera_id in sorted(camera_ids):
            self.camera_combo.addItem(camera_id)

        # 이전 선택 복원
        index = self.camera_combo.findText(current)
        if index >= 0:
            self.camera_combo.setCurrentIndex(index)

    def _apply_filter(self):
        """필터 적용"""
        # 필터 조건
        camera_filter = self.camera_combo.currentText()
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()

        # 테이블 초기화
        self.file_table.setRowCount(0)

        # 필터링 및 표시
        for file in self.recording_files:
            # 카메라 필터
            if camera_filter != "전체" and file.camera_id != camera_filter:
                continue

            # 날짜 필터
            file_date = file.timestamp.date()
            if file_date < start or file_date > end:
                continue

            # 테이블에 추가
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)

            # 체크박스 (첫 번째 컬럼)
            checkbox = QCheckBox()
            checkbox.setStyleSheet("QCheckBox { margin-left: 10px; }")
            self.file_table.setCellWidget(row, 0, checkbox)

            # 파일 정보
            self.file_table.setItem(row, 1, QTableWidgetItem(file.camera_id))
            self.file_table.setItem(row, 2, QTableWidgetItem(file.file_name))
            self.file_table.setItem(row, 3, QTableWidgetItem(
                file.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ))
            self.file_table.setItem(row, 4, QTableWidgetItem(file.formatted_duration))
            self.file_table.setItem(row, 5, QTableWidgetItem(file.formatted_size))

            # 파일 경로를 행에 저장 (카메라 ID 컬럼에 저장)
            self.file_table.item(row, 1).setData(Qt.UserRole, file.file_path)

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """아이템 더블클릭"""
        row = item.row()
        # 파일 경로는 카메라 ID 컬럼(1번)에 저장되어 있음
        file_path = self.file_table.item(row, 1).data(Qt.UserRole)
        if file_path:
            self.file_selected.emit(file_path)

    def _select_all(self):
        """전체 선택"""
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)

    def _deselect_all(self):
        """전체 해제"""
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

    def _backup_selected(self):
        """선택된 파일들 백업"""
        from ui.backup_dialog import BackupDialog

        # 체크된 파일 경로 수집
        selected_files = []
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                file_path = self.file_table.item(row, 1).data(Qt.UserRole)
                if file_path:
                    selected_files.append(file_path)

        if not selected_files:
            QMessageBox.information(
                self,
                "선택 없음",
                "백업할 파일을 선택해주세요."
            )
            return

        # 백업 다이얼로그 열기
        dialog = BackupDialog(selected_files, self)
        dialog.exec_()

        logger.info(f"Backup dialog closed: {len(selected_files)} files selected")

    def _delete_selected(self):
        """선택된 파일들 삭제"""
        # 체크된 파일 경로 수집
        selected_files = []
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                file_path = self.file_table.item(row, 1).data(Qt.UserRole)
                file_name = self.file_table.item(row, 2).text()
                if file_path:
                    selected_files.append((file_path, file_name))

        if not selected_files:
            QMessageBox.information(
                self,
                "선택 없음",
                "삭제할 파일을 선택해주세요."
            )
            return

        # 확인 다이얼로그
        reply = QMessageBox.question(
            self,
            "파일 삭제",
            f"{len(selected_files)}개 파일을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 파일 경로 리스트 생성
            file_paths = [file_path for file_path, file_name in selected_files]

            # 삭제 로그 출력
            for file_path, file_name in selected_files:
                logger.info(f"Deleting file: {file_name}")

            # 파일 경로 배열을 한번에 emit
            self.file_deleted.emit(file_paths)


    def refresh_list(self):
        """목록 새로고침"""
        # 부모 위젯(PlaybackWidget)의 scan_recordings 호출
        parent_widget = self.parent()
        while parent_widget is not None:
            if isinstance(parent_widget, PlaybackWidget):
                parent_widget.scan_recordings()
                logger.info("Recording list refreshed")
                break
            parent_widget = parent_widget.parent()


class PlaybackWidget(ThemedWidget):
    """통합 재생 위젯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playback_manager = PlaybackManager()
        self.init_ui()
        self.setup_connections()

        # 초기 스캔
        QTimer.singleShot(100, self.scan_recordings)

    def init_ui(self):
        """UI 초기화"""
        layout = QHBoxLayout(self)

        # Use theme from main window - no hardcoded style

        # 스플리터
        splitter = QSplitter(Qt.Horizontal)

        # 왼쪽: 파일 목록
        self.file_list = RecordingListWidget()
        splitter.addWidget(self.file_list)

        # 오른쪽: 재생 컨트롤
        self.playback_control = PlaybackControlWidget()
        splitter.addWidget(self.playback_control)

        # 스플리터 비율 설정 (30:70)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

    def setup_connections(self):
        """시그널 연결"""
        # 파일 목록 위젯
        self.file_list.file_selected.connect(self.play_file)
        self.file_list.file_deleted.connect(self.delete_file)

        # 재생 컨트롤 위젯
        self.playback_control.play_clicked.connect(self.on_play_clicked)
        self.playback_control.pause_clicked.connect(self.on_pause_clicked)
        self.playback_control.stop_clicked.connect(self.stop_playback)
        self.playback_control.seek_requested.connect(self.seek_to_position)
        self.playback_control.speed_changed.connect(self.set_playback_speed)

        # 재생 관리자 콜백
        self.playback_manager.on_file_list_updated = self.file_list.update_file_list

    def scan_recordings(self):
        """녹화 파일 스캔"""
        logger.info("Scanning recordings...")
        self.playback_manager.scan_recordings()

    def play_file(self, file_path: str):
        """파일 재생"""
        logger.info(f"Playing file: {file_path}")

        # 비디오 위젯 ID 가져오기
        window_handle = self.playback_control.get_video_widget_id()

        # Transform 설정 가져오기
        flip_map = {"None": "none", "Horizontal": "horizontal", "Vertical": "vertical", "Both": "both"}
        flip_mode = flip_map.get(self.file_list.flip_combo.currentText(), "none")

        rotation_map = {"0°": 0, "90°": 90, "180°": 180, "270°": 270}
        rotation = rotation_map.get(self.file_list.rotation_combo.currentText(), 0)

        # 재생 시작
        if self.playback_manager.play_file(file_path, window_handle, flip_mode, rotation):
            # 재생 파이프라인 콜백 설정
            pipeline = self.playback_manager.playback_pipeline
            if pipeline:
                pipeline.on_position_changed = self.playback_control.update_position
                pipeline.on_state_changed = self.on_state_changed
                pipeline.on_eos = self.on_end_of_stream

            self.playback_control.set_playing(True)
        else:
            QMessageBox.warning(self, "재생 오류", "파일을 재생할 수 없습니다.")

    def on_play_clicked(self):
        """재생 버튼 클릭"""
        state = self.playback_manager.get_playback_state()

        if state == PlaybackState.PAUSED:
            # 일시정지 -> 재생
            if self.playback_manager.resume_playback():
                self.playback_control.set_playing(True)
        elif state == PlaybackState.STOPPED:
            # 정지 -> 재생 (마지막 파일 재생)
            if self.playback_manager.current_file:
                self.play_file(self.playback_manager.current_file.file_path)

    def on_pause_clicked(self):
        """일시정지 버튼 클릭"""
        if self.playback_manager.pause_playback():
            self.playback_control.set_playing(False)

    def stop_playback(self):
        """재생 정지"""
        self.playback_manager.stop_playback()
        self.playback_control.reset()

    def seek_to_position(self, position: float):
        """특정 위치로 이동"""
        self.playback_manager.seek(position)

    def set_playback_speed(self, speed: float):
        """재생 속도 설정"""
        self.playback_manager.set_playback_rate(speed)

    def delete_file(self, file_paths: list):
        """파일 삭제 (배치 처리)"""
        if not file_paths:
            return

        # 여러 파일 삭제
        success_count = 0
        fail_count = 0
        failed_files = []

        for file_path in file_paths:
            if self.playback_manager.delete_recording(file_path):
                success_count += 1
            else:
                fail_count += 1
                failed_files.append(file_path)

        # 결과 메시지
        if fail_count == 0:
            QMessageBox.information(
                self,
                "삭제 완료",
                f"{success_count}개 파일이 삭제되었습니다."
            )
        else:
            QMessageBox.warning(
                self,
                "삭제 완료 (일부 실패)",
                f"성공: {success_count}개\n실패: {fail_count}개\n\n실패한 파일:\n" + "\n".join(failed_files[:5])
            )

        # 목록 새로고침
        self.scan_recordings()

    def on_state_changed(self, state: PlaybackState):
        """재생 상태 변경"""
        logger.debug(f"Playback state changed: {state.value}")
        if state == PlaybackState.STOPPED:
            self.playback_control.reset()
        elif state == PlaybackState.PLAYING:
            self.playback_control.set_playing(True)
        elif state == PlaybackState.PAUSED:
            self.playback_control.set_playing(False)

    def on_end_of_stream(self):
        """재생 종료"""
        logger.info("End of stream reached")
        self.playback_control.reset()

        # 다음 파일 자동 재생 (옵션)
        # self.play_next_file()

    def cleanup(self):
        """정리"""
        self.stop_playback()