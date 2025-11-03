"""
녹화 파일 백업 다이얼로그
선택한 녹화 파일을 지정한 경로로 백업
"""

import os
import json
import shutil
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QFileDialog, QMessageBox, QTextEdit,
    QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont
from loguru import logger

from core.config import ConfigManager


class BackupWorkerSignals(QObject):
    """백업 작업 시그널"""
    progress_updated = pyqtSignal(int, str, int, int)  # progress%, current_file, current_idx, total
    file_completed = pyqtSignal(str, str, bool)  # source, destination, success
    backup_completed = pyqtSignal(bool, str)  # success, message
    error_occurred = pyqtSignal(str)  # error_message


class BackupWorker:
    """비동기 백업 작업 수행"""

    def __init__(self, source_files: List[str], destination_path: str):
        self.source_files = source_files
        self.destination_path = Path(destination_path)
        self.signals = BackupWorkerSignals()
        self._is_running = False
        self._stop_requested = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """백업 시작"""
        if self._is_running:
            logger.warning("Backup already running")
            return

        self._is_running = True
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run_backup, daemon=True)
        self._thread.start()
        logger.info("Backup worker started")

    def stop(self):
        """백업 중지"""
        if not self._is_running:
            return

        logger.info("Stopping backup...")
        self._stop_requested = True

        # 스레드 종료 대기 (최대 3초)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        self._is_running = False
        logger.info("Backup worker stopped")

    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self._is_running

    def _run_backup(self):
        """백업 실행 (별도 스레드)"""
        try:
            total_files = len(self.source_files)
            success_count = 0
            fail_count = 0
            failed_files = []

            logger.info(f"Starting backup: {total_files} files to {self.destination_path}")

            for idx, source_path in enumerate(self.source_files):
                if self._stop_requested:
                    logger.info("Backup cancelled by user")
                    self.signals.backup_completed.emit(
                        False,
                        f"백업이 취소되었습니다.\n완료: {success_count}/{total_files} 파일"
                    )
                    self._is_running = False
                    return

                source = Path(source_path)

                if not source.exists():
                    logger.error(f"Source file not found: {source_path}")
                    fail_count += 1
                    failed_files.append(f"{source.name} (파일 없음)")
                    continue

                # 진행률 업데이트
                progress = int((idx / total_files) * 100)
                self.signals.progress_updated.emit(progress, source.name, idx + 1, total_files)

                # 대상 경로 생성 (날짜별 폴더 유지)
                # 예: E:/_recordings/cam_01/20251103/file.mkv → F:/backup/cam_01/20251103/file.mkv
                try:
                    # 원본 경로에서 카메라ID와 날짜 폴더 추출
                    relative_parts = source.parts[-3:]  # cam_01/20251103/file.mkv
                    dest_path = self.destination_path / Path(*relative_parts)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # 파일 복사
                    logger.debug(f"Copying: {source} -> {dest_path}")
                    shutil.copy2(source, dest_path)

                    # 파일 검증 (크기 비교)
                    if source.stat().st_size == dest_path.stat().st_size:
                        success_count += 1
                        self.signals.file_completed.emit(str(source), str(dest_path), True)
                        logger.info(f"Backup completed: {source.name}")
                    else:
                        fail_count += 1
                        failed_files.append(f"{source.name} (크기 불일치)")
                        self.signals.file_completed.emit(str(source), str(dest_path), False)
                        logger.error(f"Backup failed (size mismatch): {source.name}")

                except Exception as e:
                    fail_count += 1
                    failed_files.append(f"{source.name} ({str(e)})")
                    self.signals.file_completed.emit(str(source), "", False)
                    logger.error(f"Backup failed: {source.name} - {e}")

            # 완료
            self.signals.progress_updated.emit(100, "완료", total_files, total_files)

            if fail_count == 0:
                message = f"백업이 완료되었습니다!\n\n총 {total_files}개 파일"
                self.signals.backup_completed.emit(True, message)
                logger.success(f"Backup completed successfully: {total_files} files")
            else:
                message = (
                    f"백업이 완료되었습니다. (일부 실패)\n\n"
                    f"성공: {success_count}개\n"
                    f"실패: {fail_count}개\n\n"
                    f"실패한 파일:\n" + "\n".join(failed_files[:10])
                )
                if len(failed_files) > 10:
                    message += f"\n... 외 {len(failed_files) - 10}개"
                self.signals.backup_completed.emit(False, message)
                logger.warning(f"Backup completed with errors: {success_count}/{total_files} succeeded")

        except Exception as e:
            error_msg = f"백업 중 오류가 발생했습니다:\n{str(e)}"
            self.signals.error_occurred.emit(error_msg)
            logger.error(f"Backup error: {e}")

        finally:
            self._is_running = False


class BackupDialog(QDialog):
    """백업 다이얼로그"""

    def __init__(self, source_files: List[str], parent=None):
        super().__init__(parent)
        self.source_files = source_files
        self.backup_worker: Optional[BackupWorker] = None

        self.setWindowTitle("녹화 파일 백업")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)
        self.setModal(True)

        self._setup_ui()
        self._load_default_path()
        self._update_file_info()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # === 파일 정보 섹션 ===
        info_group = QGroupBox("백업 정보")
        info_layout = QVBoxLayout()

        self.file_count_label = QLabel()
        self.total_size_label = QLabel()

        font = QFont()
        font.setPointSize(10)
        self.file_count_label.setFont(font)
        self.total_size_label.setFont(font)

        info_layout.addWidget(self.file_count_label)
        info_layout.addWidget(self.total_size_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # === 백업 경로 섹션 ===
        path_group = QGroupBox("백업 경로")
        path_layout = QVBoxLayout()

        # 경로 입력 레이아웃
        path_input_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("백업 저장 경로를 선택하세요...")
        path_input_layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("찾아보기")
        self.browse_button.clicked.connect(self._browse_destination)
        path_input_layout.addWidget(self.browse_button)

        path_layout.addLayout(path_input_layout)

        # 경로 상태 레이블
        self.path_status_label = QLabel()
        self.path_status_label.setWordWrap(True)
        path_layout.addWidget(self.path_status_label)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # === 진행 상황 섹션 ===
        progress_group = QGroupBox("진행 상황")
        progress_layout = QVBoxLayout()

        # 현재 파일 레이블
        self.current_file_label = QLabel("대기 중...")
        progress_layout.addWidget(self.current_file_label)

        # 프로그레스바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m)")
        progress_layout.addWidget(self.progress_bar)

        # 진행 정보 레이블
        self.progress_info_label = QLabel("0 / 0 파일")
        progress_layout.addWidget(self.progress_info_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # === 로그 섹션 ===
        log_group = QGroupBox("백업 로그")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # === 버튼 섹션 ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_button = QPushButton("백업 시작")
        self.start_button.clicked.connect(self._start_backup)
        self.start_button.setMinimumWidth(100)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("백업 중지")
        self.stop_button.clicked.connect(self._stop_backup)
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumWidth(100)
        button_layout.addWidget(self.stop_button)

        self.close_button = QPushButton("종료")
        self.close_button.clicked.connect(self._close_dialog)
        self.close_button.setMinimumWidth(100)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _load_default_path(self):
        """기본 백업 경로 로드"""
        try:
            config = ConfigManager.get_instance()
            recording_config = config.get_recording_config()

            # Des_path 가져오기
            default_path = recording_config.get("Des_path", "")

            if default_path and Path(default_path).exists():
                self.path_edit.setText(default_path)
                self._validate_destination_path()
            else:
                self.path_status_label.setText("⚠ 기본 경로가 설정되지 않았거나 유효하지 않습니다.")
                self.path_status_label.setStyleSheet("color: orange;")

        except Exception as e:
            logger.error(f"Failed to load default backup path: {e}")

    def _save_backup_path(self, path: str):
        """백업 경로를 IT_RNVR.json에 저장"""
        try:
            config = ConfigManager.get_instance()

            # recording_config 업데이트
            config.recording_config["Des_path"] = path

            # JSON 파일에 recording 섹션만 부분 업데이트
            if not config.config_file.exists():
                logger.error(f"Config file not found: {config.config_file}")
                return False

            # 기존 JSON 파일 로드
            with open(config.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # recording 섹션의 Des_path만 업데이트
            if 'recording' not in data:
                data['recording'] = {}

            data['recording']['Des_path'] = path

            # JSON 파일에 저장
            with open(config.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Backup path saved to config: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save backup path: {e}")
            return False

    def _update_file_info(self):
        """파일 정보 업데이트"""
        total_size = 0
        valid_files = 0

        for file_path in self.source_files:
            path = Path(file_path)
            if path.exists():
                total_size += path.stat().st_size
                valid_files += 1

        # 파일 개수
        self.file_count_label.setText(f"📁 백업할 파일: {valid_files}개")

        # 총 용량
        size_mb = total_size / (1024 * 1024)
        size_gb = total_size / (1024 * 1024 * 1024)

        if size_gb >= 1.0:
            size_str = f"{size_gb:.2f} GB"
        else:
            size_str = f"{size_mb:.2f} MB"

        self.total_size_label.setText(f"💾 총 용량: {size_str}")

        # 유효하지 않은 파일이 있으면 로그에 표시
        invalid_count = len(self.source_files) - valid_files
        if invalid_count > 0:
            self._add_log(f"⚠ {invalid_count}개 파일을 찾을 수 없습니다.", "orange")

    def _browse_destination(self):
        """백업 경로 선택"""
        current_path = self.path_edit.text()
        if not current_path:
            current_path = str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            "백업 저장 경로 선택",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder:
            self.path_edit.setText(folder)
            self._validate_destination_path()

            # 변경된 경로를 IT_RNVR.json에 저장
            self._save_backup_path(folder)

    def _validate_destination_path(self) -> bool:
        """백업 경로 검증"""
        dest_path = self.path_edit.text().strip()

        if not dest_path:
            self.path_status_label.setText("❌ 백업 경로를 선택해주세요.")
            self.path_status_label.setStyleSheet("color: red;")
            return False

        path = Path(dest_path)

        # 경로 존재 여부
        if not path.exists():
            self.path_status_label.setText("❌ 경로가 존재하지 않습니다.")
            self.path_status_label.setStyleSheet("color: red;")
            return False

        # 쓰기 권한 확인
        if not os.access(dest_path, os.W_OK):
            self.path_status_label.setText("❌ 쓰기 권한이 없습니다.")
            self.path_status_label.setStyleSheet("color: red;")
            return False

        # 여유 공간 확인
        try:
            stat = shutil.disk_usage(dest_path)
            free_space = stat.free

            # 필요 공간 계산
            total_size = sum(
                Path(f).stat().st_size
                for f in self.source_files
                if Path(f).exists()
            )

            free_gb = free_space / (1024 ** 3)
            required_gb = total_size / (1024 ** 3)

            # 여유 공간이 필요 공간의 110% 이상인지 확인 (여유분 10%)
            if free_space < total_size * 1.1:
                self.path_status_label.setText(
                    f"❌ 공간이 부족합니다.\n"
                    f"여유 공간: {free_gb:.2f} GB / 필요 공간: {required_gb:.2f} GB"
                )
                self.path_status_label.setStyleSheet("color: red;")
                return False
            else:
                self.path_status_label.setText(
                    f"✅ 경로가 유효합니다.\n"
                    f"여유 공간: {free_gb:.2f} GB / 필요 공간: {required_gb:.2f} GB"
                )
                self.path_status_label.setStyleSheet("color: green;")
                return True

        except Exception as e:
            self.path_status_label.setText(f"❌ 경로 검증 실패: {str(e)}")
            self.path_status_label.setStyleSheet("color: red;")
            logger.error(f"Path validation error: {e}")
            return False

    def _start_backup(self):
        """백업 시작"""
        # 경로 검증
        if not self._validate_destination_path():
            QMessageBox.warning(
                self,
                "경로 오류",
                "백업 경로가 유효하지 않습니다.\n경로를 확인해주세요."
            )
            return

        # 이미 실행 중인지 확인
        if self.backup_worker and self.backup_worker.is_running():
            QMessageBox.warning(self, "백업 진행 중", "백업이 이미 진행 중입니다.")
            return

        # 백업 시작 확인
        dest_path = self.path_edit.text().strip()
        reply = QMessageBox.question(
            self,
            "백업 시작",
            f"선택한 {len(self.source_files)}개 파일을\n{dest_path}\n경로로 백업하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # UI 상태 변경
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.close_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.path_edit.setEnabled(False)

        # 진행 상황 초기화
        self.progress_bar.setValue(0)
        self.current_file_label.setText("백업 시작 중...")
        self.log_text.clear()
        self._add_log("백업을 시작합니다...", "blue")

        # 백업 워커 생성 및 시작
        self.backup_worker = BackupWorker(self.source_files, dest_path)
        self.backup_worker.signals.progress_updated.connect(self._on_progress_updated)
        self.backup_worker.signals.file_completed.connect(self._on_file_completed)
        self.backup_worker.signals.backup_completed.connect(self._on_backup_completed)
        self.backup_worker.signals.error_occurred.connect(self._on_error_occurred)
        self.backup_worker.start()

        logger.info(f"Backup started: {len(self.source_files)} files to {dest_path}")

    def _stop_backup(self):
        """백업 중지"""
        if not self.backup_worker or not self.backup_worker.is_running():
            return

        reply = QMessageBox.question(
            self,
            "백업 중지",
            "백업을 중지하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._add_log("백업을 중지합니다...", "orange")
            self.backup_worker.stop()

            # UI 상태 복원
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.close_button.setEnabled(True)
            self.browse_button.setEnabled(True)
            self.path_edit.setEnabled(True)

            self.current_file_label.setText("백업이 중지되었습니다.")

    def _close_dialog(self):
        """다이얼로그 닫기"""
        # 백업 진행 중이면 경고
        if self.backup_worker and self.backup_worker.is_running():
            reply = QMessageBox.question(
                self,
                "백업 진행 중",
                "백업이 진행 중입니다.\n중지하고 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.backup_worker.stop()
                self.accept()
        else:
            self.accept()

    def _on_progress_updated(self, progress: int, current_file: str, current_idx: int, total: int):
        """진행률 업데이트"""
        self.progress_bar.setValue(progress)
        self.current_file_label.setText(f"복사 중: {current_file}")
        self.progress_info_label.setText(f"{current_idx} / {total} 파일")

    def _on_file_completed(self, source: str, destination: str, success: bool):
        """파일 백업 완료"""
        file_name = Path(source).name
        if success:
            self._add_log(f"✅ {file_name}", "green")
        else:
            self._add_log(f"❌ {file_name} (실패)", "red")

    def _on_backup_completed(self, success: bool, message: str):
        """백업 완료"""
        # UI 상태 복원
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.path_edit.setEnabled(True)

        self.current_file_label.setText("백업이 완료되었습니다.")

        if success:
            self._add_log("백업이 성공적으로 완료되었습니다!", "green")
        else:
            self._add_log("백업이 완료되었습니다. (일부 실패)", "orange")

        # 완료 메시지
        QMessageBox.information(self, "백업 완료", message)

    def _on_error_occurred(self, error_message: str):
        """오류 발생"""
        self._add_log(f"❌ 오류: {error_message}", "red")

        # UI 상태 복원
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.path_edit.setEnabled(True)

        QMessageBox.critical(self, "백업 오류", error_message)

    def _add_log(self, message: str, color: str = "white"):
        """로그 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.log_text.append(html)

        # 자동 스크롤
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """창 닫기 이벤트"""
        # 백업 진행 중이면 중지
        if self.backup_worker and self.backup_worker.is_running():
            self.backup_worker.stop()
        event.accept()
