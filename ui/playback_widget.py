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
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDateTime, QDate, QThread
from PyQt5.QtGui import QIcon
from typing import Optional, List
from datetime import datetime
from loguru import logger
from pathlib import Path

from ui.theme import ThemedWidget
from camera.playback import PlaybackManager, PlaybackState, RecordingFile
from core.config import ConfigManager


class RecordingScanThread(QThread):
    """녹화 파일 스캔 스레드"""
    scan_completed = pyqtSignal(list)  # List[RecordingFile]
    scan_progress = pyqtSignal(str, int, int)  # 메시지, 현재, 전체

    def __init__(self, recordings_dir: str, camera_id: str = None,
                 start_date: datetime = None, end_date: datetime = None):
        super().__init__()
        self.recordings_dir = recordings_dir
        self.camera_id = camera_id
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        """스캔 실행 (스레드 내부에서 독립적으로 스캔)"""
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst

            recordings_dir = Path(self.recordings_dir)
            recording_files = []

            if not recordings_dir.exists():
                logger.warning(f"Recordings directory not found: {recordings_dir}")
                self.scan_completed.emit([])
                return

            # 지원되는 파일 형식
            supported_formats = ['.mp4', '.mkv', '.avi']

            # 카메라 디렉토리 필터링
            camera_dirs = []
            if self.camera_id and self.camera_id != "전체":
                target_dir = recordings_dir / self.camera_id
                if target_dir.exists() and target_dir.is_dir():
                    camera_dirs = [target_dir]
            else:
                camera_dirs = [d for d in recordings_dir.iterdir() if d.is_dir()]

            # 날짜 범위를 문자열로 변환 (YYYYMMDD 형식)
            start_date_str = self.start_date.strftime("%Y%m%d") if self.start_date else None
            end_date_str = self.end_date.strftime("%Y%m%d") if self.end_date else None

            # 카메라 디렉토리 스캔
            for camera_dir in camera_dirs:
                cam_id = camera_dir.name

                # 날짜 디렉토리 스캔
                for date_dir in camera_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    # 날짜 필터 적용 (디렉토리명 기준)
                    date_dir_name = date_dir.name
                    if start_date_str and date_dir_name < start_date_str:
                        continue
                    if end_date_str and date_dir_name > end_date_str:
                        continue

                    # 녹화 파일 스캔
                    for file_path in date_dir.iterdir():
                        if file_path.suffix.lower() not in supported_formats:
                            continue

                        try:
                            # 파일 정보 추출
                            file_stat = file_path.stat()

                            # 파일명에서 타임스탬프 추출
                            file_name = file_path.stem
                            parts = file_name.split('_')
                            if len(parts) >= 3:
                                date_str = parts[-2]
                                time_str = parts[-1]
                                timestamp = datetime.strptime(
                                    f"{date_str}_{time_str}",
                                    "%Y%m%d_%H%M%S"
                                )
                            else:
                                timestamp = datetime.fromtimestamp(file_stat.st_mtime)

                            # Duration 조회 건너뛰기 (성능 개선)
                            # 라즈베리파이에서 duration 조회가 너무 느리고 멈추는 경우가 있어서 비활성화
                            # duration = self._get_file_duration(str(file_path), Gst)
                            duration = 0  # duration은 나중에 재생 시점에 가져오도록 함

                            # RecordingFile 객체 생성
                            recording = RecordingFile(
                                file_path=str(file_path),
                                camera_id=cam_id,
                                camera_name=f"Camera {cam_id}",
                                timestamp=timestamp,
                                duration=duration,
                                file_size=file_stat.st_size
                            )

                            recording_files.append(recording)

                        except Exception as e:
                            logger.error(f"Error processing file {file_path}: {e}")

            # 시간순 정렬 (최신 먼저)
            recording_files.sort(key=lambda x: x.timestamp, reverse=True)

            logger.info(f"Scan thread completed: {len(recording_files)} files")
            self.scan_completed.emit(recording_files)

        except Exception as e:
            logger.error(f"Scan thread error: {e}")
            import traceback
            traceback.print_exc()
            self.scan_completed.emit([])

    def _get_file_duration(self, file_path: str, Gst) -> float:
        """파일 재생 시간 가져오기"""
        try:
            # 임시 파이프라인으로 duration 가져오기
            pipeline_str = f"filesrc location=\"{file_path}\" ! decodebin ! fakesink"
            pipeline = Gst.parse_launch(pipeline_str)

            # 타임아웃 설정 (2초)
            pipeline.set_state(Gst.State.PAUSED)
            ret = pipeline.get_state(2 * Gst.SECOND)  # 2초 타임아웃

            if ret[0] == Gst.StateChangeReturn.SUCCESS:
                success, duration = pipeline.query_duration(Gst.Format.TIME)
                pipeline.set_state(Gst.State.NULL)

                if success:
                    return duration / Gst.SECOND
            else:
                # 타임아웃 발생 시
                logger.debug(f"Timeout getting duration for {file_path}")
                pipeline.set_state(Gst.State.NULL)

        except Exception as e:
            logger.debug(f"Could not get duration for {file_path}: {e}")
            # 파이프라인이 생성된 경우 확실히 정리
            if 'pipeline' in locals():
                try:
                    pipeline.set_state(Gst.State.NULL)
                except:
                    pass

        return 0


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
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 비디오 디스플레이 영역 (placeholder) - 남는 공간 모두 차지
        self.video_widget = QWidget()
        self.video_widget.setObjectName("videoWidget")  # Set object name for styling
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Background color will be set by main window theme
        layout.addWidget(self.video_widget, stretch=1)  # stretch=1 로 남는 공간 모두 차지

        # 컨트롤 영역을 별도 위젯으로 묶기
        control_widget = QWidget()
        control_main_layout = QVBoxLayout(control_widget)
        control_main_layout.setSpacing(5)
        control_main_layout.setContentsMargins(5, 5, 5, 5)

        # 시크바
        seek_layout = QHBoxLayout()

        self.position_label = QLabel("00:00")
        font = self.position_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.position_label.setFont(font)
        seek_layout.addWidget(self.position_label)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self._on_seek_slider_released)
        self.seek_slider.sliderPressed.connect(self._on_seek_slider_pressed)
        seek_layout.addWidget(self.seek_slider)

        self.duration_label = QLabel("00:00")
        font = self.duration_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.duration_label.setFont(font)
        seek_layout.addWidget(self.duration_label)

        control_main_layout.addLayout(seek_layout)

        # 컨트롤 버튼
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        # 재생 속도 선택
        speed_label = QLabel("속도:")
        font = speed_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        speed_label.setFont(font)
        control_layout.addWidget(speed_label)
        self.speed_combo = QComboBox()
        font = self.speed_combo.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.speed_combo.setFont(font)
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x", "4.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        control_layout.addWidget(self.speed_combo)

        control_layout.addSpacing(20)  # 속도 콤보박스와 재생 버튼 사이 여백

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

        control_main_layout.addLayout(control_layout)

        # 컨트롤 위젯을 메인 레이아웃에 추가 (stretch=0 으로 고정 높이)
        layout.addWidget(control_widget, stretch=0)

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.recording_files: List[RecordingFile] = []

    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)

        # 필터 섹션 (모두 한 줄로)
        filter_group = QGroupBox("필터")
        font = filter_group.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        filter_group.setFont(font)
        filter_layout = QHBoxLayout()

        # 카메라 선택
        camera_label = QLabel("카메라:")
        font = camera_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        camera_label.setFont(font)
        camera_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(camera_label)
        self.camera_combo = QComboBox()
        font = self.camera_combo.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.camera_combo.setFont(font)
        self.camera_combo.addItem("전체")
        # 카메라 선택 변경 시 자동 새로고침 제거 (사용자가 수동으로 새로고침)
        # self.camera_combo.currentTextChanged.connect(self.refresh_list)
        filter_layout.addWidget(self.camera_combo)

        filter_layout.addSpacing(20)

        # 시작 날짜
        start_label = QLabel("시작:")
        font = start_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        start_label.setFont(font)
        start_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(start_label)
        self.start_date = QDateEdit()
        font = self.start_date.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.start_date.setFont(font)
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        # 시작 날짜 변경 시 자동 새로고침 제거 (사용자가 수동으로 새로고침)
        # self.start_date.dateChanged.connect(self.refresh_list)
        filter_layout.addWidget(self.start_date)

        filter_layout.addSpacing(20)

        # 종료 날짜
        end_label = QLabel("종료:")
        font = end_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        end_label.setFont(font)
        end_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(end_label)
        self.end_date = QDateEdit()
        font = self.end_date.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.end_date.setFont(font)
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        # 종료 날짜 변경 시 자동 새로고침 제거 (사용자가 수동으로 새로고침)
        # self.end_date.dateChanged.connect(self.refresh_list)
        filter_layout.addWidget(self.end_date)

        filter_layout.addStretch()

        # 비디오 변환 필터
        transform_label = QLabel("비디오 변환:")
        font = transform_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        transform_label.setFont(font)
        transform_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(transform_label)

        self.flip_combo = QComboBox()
        font = self.flip_combo.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.flip_combo.setFont(font)
        self.flip_combo.addItems(["None", "Horizontal", "Vertical", "Both"])
        self.flip_combo.setToolTip("좌우/상하 반전")
        filter_layout.addWidget(self.flip_combo)

        self.rotation_combo = QComboBox()
        font = self.rotation_combo.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.rotation_combo.setFont(font)
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setToolTip("회전")
        filter_layout.addWidget(self.rotation_combo)

        filter_layout.addStretch()

        # 새로고침 버튼 (우측 끝)
        self.refresh_button = QPushButton("새로고침")
        font = self.refresh_button.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.refresh_button.setFont(font)
        self.refresh_button.clicked.connect(self.refresh_list)
        filter_layout.addWidget(self.refresh_button)

        # 스캔 상태 레이블
        self.scan_status_label = QLabel("")
        font = self.scan_status_label.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.scan_status_label.setFont(font)
        self.scan_status_label.setStyleSheet("color: #4CAF50;")  # bold 제거
        filter_layout.addWidget(self.scan_status_label)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # 파일 목록 테이블
        self.file_table = QTableWidget()
        font = self.file_table.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.file_table.setFont(font)
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
        font = header.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        font.setBold(False)  # bold 제거
        header.setFont(font)
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
        font = select_all_btn.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        select_all_btn.setFont(font)
        select_all_btn.clicked.connect(self._select_all)
        button_layout.addWidget(select_all_btn)

        # 전체 해제 버튼
        deselect_all_btn = QPushButton("전체 해제")
        font = deselect_all_btn.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        deselect_all_btn.setFont(font)
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addStretch()

        # 백업 버튼
        self.backup_btn = QPushButton("백업")
        font = self.backup_btn.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        self.backup_btn.setFont(font)
        self.backup_btn.clicked.connect(self._backup_selected)
        # Theme color will be applied by ThemeManager - no hardcoded style
        button_layout.addWidget(self.backup_btn)

        button_layout.addSpacing(10)  # 백업 버튼과 삭제 버튼 사이 여백

        # 선택 삭제 버튼
        delete_btn = QPushButton("선택 삭제")
        font = delete_btn.font()
        font.setPointSize(11)  # 버튼과 동일한 폰트 크기
        delete_btn.setFont(font)
        delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

    def update_camera_list(self, camera_ids: List[str]):
        """카메라 목록 업데이트 (중복 제거 및 정렬)"""
        current_selection = self.camera_combo.currentText()

        # 카메라 콤보박스 업데이트 (시그널 임시 차단)
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("전체")

        # 중복 제거하고 정렬
        unique_cameras = sorted(set(camera_ids))
        for cam_id in unique_cameras:
            self.camera_combo.addItem(cam_id)

        # 이전 선택 복원
        index = self.camera_combo.findText(current_selection)
        if index >= 0:
            self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.setCurrentIndex(0)  # "전체"

        self.camera_combo.blockSignals(False)
        logger.debug(f"Camera list updated: {len(unique_cameras)} cameras")

    def update_file_list(self, files: List[RecordingFile]):
        """파일 목록 업데이트 (스캔 결과를 바로 테이블에 표시)"""
        self.recording_files = files

        # 테이블 초기화
        self.file_table.setRowCount(0)

        # 파일 목록을 테이블에 추가 (필터링은 이미 scan_recordings에서 완료)
        for file in files:
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

        logger.debug(f"File list updated: {len(files)} files displayed")

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
        from ui.delete_dialog import DeleteDialog

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
                "삭제할 파일을 선택해주세요."
            )
            return

        # 삭제 다이얼로그 열기
        dialog = DeleteDialog(selected_files, self)
        dialog.delete_completed.connect(lambda: self.refresh_list())  # 삭제 완료 시 목록 새로고침
        dialog.exec_()

        logger.info(f"Delete dialog closed: {len(selected_files)} files selected")


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
        self.config_manager = ConfigManager.get_instance()  # ConfigManager 인스턴스
        self.scan_thread = None  # 스캔 스레드
        self.init_ui()
        self.setup_connections()

        # 초기 카메라 목록 로드 (설정에서 가져오기)
        QTimer.singleShot(100, self._load_camera_list_from_config)

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

        # 재생 컨트롤 위젯
        self.playback_control.play_clicked.connect(self.on_play_clicked)
        self.playback_control.pause_clicked.connect(self.on_pause_clicked)
        self.playback_control.stop_clicked.connect(self.stop_playback)
        self.playback_control.seek_requested.connect(self.seek_to_position)
        self.playback_control.speed_changed.connect(self.set_playback_speed)

        # 재생 관리자 콜백
        self.playback_manager.on_file_list_updated = self.file_list.update_file_list

    def _load_camera_list_from_config(self):
        """설정에서 카메라 목록 로드 (파일 스캔 없이)"""
        # ConfigManager에서 카메라 목록 가져오기
        cameras = self.config_manager.config.get("cameras", [])
        camera_ids = [camera.get("camera_id", "") for camera in cameras if camera.get("camera_id")]

        # 카메라 목록 업데이트
        self.file_list.update_camera_list(camera_ids)

        logger.info(f"Camera list loaded from config: {len(camera_ids)} cameras")

        # # 필터 적용하여 파일 스캔 (비동기)
        # self.scan_recordings()

    def _initial_scan(self):
        """초기 스캔 (카메라 목록 초기화) - 구버전 호환용"""
        # 전체 파일 스캔 (필터 없음) - 동기 방식 (카메라 목록 구성용)
        self.playback_manager.scan_recordings(camera_id=None, start_date=None, end_date=None)

        # 카메라 목록 업데이트
        files = self.playback_manager.recording_files
        camera_ids = [f.camera_id for f in files]
        self.file_list.update_camera_list(camera_ids)

        logger.info(f"Initial scan completed: {len(files)} files, {len(set(camera_ids))} cameras")

        # 필터 적용하여 재스캔 (비동기)
        self.scan_recordings()

    def scan_recordings(self):
        """녹화 파일 스캔 (필터 적용) - 비동기"""
        # 이미 스캔 중이면 종료 시도
        if self.scan_thread and self.scan_thread.isRunning():
            logger.warning("Scan already in progress, trying to stop it")
            self.scan_thread.terminate()
            if not self.scan_thread.wait(1000):  # 1초 대기
                logger.error("Failed to stop previous scan thread")
                return

        # UI에서 필터 조건 가져오기
        camera_id = self.file_list.camera_combo.currentText()
        start_date = self.file_list.start_date.date().toPyDate()
        end_date = self.file_list.end_date.date().toPyDate()

        # datetime 객체로 변환
        from datetime import datetime, time
        start_datetime = datetime.combine(start_date, time.min)  # 00:00:00
        end_datetime = datetime.combine(end_date, time.max)      # 23:59:59

        logger.info(f"Scanning recordings: camera={camera_id}, date={start_date}~{end_date}")

        # 스캔 상태 표시
        self.file_list.scan_status_label.setText("스캔 중...")
        self.file_list.refresh_button.setEnabled(False)

        # 스캔 스레드 생성 및 시작
        self.scan_thread = RecordingScanThread(
            str(self.playback_manager.recordings_dir),
            camera_id=camera_id if camera_id != "전체" else None,
            start_date=start_datetime,
            end_date=end_datetime
        )
        self.scan_thread.scan_completed.connect(self._on_scan_completed)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_completed(self, files: List[RecordingFile]):
        """스캔 완료"""
        try:
            # UI 업데이트
            self.file_list.update_file_list(files)
            logger.info(f"Scan completed: {len(files)} files")
        except Exception as e:
            logger.error(f"Error updating file list: {e}")
        finally:
            # 스캔 상태 초기화 (완료 시에도 호출)
            self._reset_scan_status()

    def _on_scan_finished(self):
        """스캔 스레드 종료"""
        # 상태 레이블 초기화
        self._reset_scan_status()

    def _reset_scan_status(self):
        """스캔 상태 초기화"""
        try:
            self.file_list.scan_status_label.setText("")
            self.file_list.refresh_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Error resetting scan status: {e}")

        # 스레드 정리
        if self.scan_thread:
            self.scan_thread.deleteLater()
            self.scan_thread = None

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