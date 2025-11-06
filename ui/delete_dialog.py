"""
Delete Dialog
비동기 파일 삭제 다이얼로그
"""

import os
import threading
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QTextCursor
from loguru import logger

from ui.theme import ThemedDialog


class DeleteWorkerSignals(QObject):
    """삭제 작업 시그널"""
    progress_updated = pyqtSignal(int, str, int, int)  # progress, current_file, current_idx, total
    file_completed = pyqtSignal(str, bool)  # file_path, success
    delete_completed = pyqtSignal(bool, str)  # success, message
    log_message = pyqtSignal(str, str)  # message, level (info/success/error)


class DeleteWorker:
    """비동기 삭제 작업 수행"""

    def __init__(self, file_paths: List[str]):
        """
        초기화

        Args:
            file_paths: 삭제할 파일 경로 리스트
        """
        self.file_paths = file_paths
        self.signals = DeleteWorkerSignals()
        self._thread = None
        self._stop_requested = False
        self._is_running = False

    def start(self):
        """삭제 작업 시작"""
        if self._is_running:
            return

        self._stop_requested = False
        self._thread = threading.Thread(target=self._run_delete, daemon=True)
        self._thread.start()
        self._is_running = True

    def stop(self):
        """삭제 작업 중지"""
        self._stop_requested = True

    def _run_delete(self):
        """실제 삭제 작업 수행"""
        try:
            total_files = len(self.file_paths)
            success_count = 0
            fail_count = 0

            self.signals.log_message.emit(f"{total_files}개 파일 삭제 시작", "info")

            for idx, file_path in enumerate(self.file_paths):
                if self._stop_requested:
                    self.signals.log_message.emit("사용자가 삭제를 취소했습니다", "error")
                    self.signals.delete_completed.emit(False, f"삭제가 취소되었습니다.")
                    return

                file = Path(file_path)
                file_name = file.name

                # 진행 상태 업데이트
                progress = int((idx / total_files) * 100)
                self.signals.progress_updated.emit(progress, file_name, idx + 1, total_files)

                try:
                    # 파일 삭제
                    if file.exists():
                        file.unlink()
                        success_count += 1
                        self.signals.file_completed.emit(file_path, True)
                        self.signals.log_message.emit(f"삭제됨: {file_name}", "success")
                    else:
                        fail_count += 1
                        self.signals.file_completed.emit(file_path, False)
                        self.signals.log_message.emit(f"파일 없음: {file_name}", "error")

                except PermissionError:
                    fail_count += 1
                    self.signals.file_completed.emit(file_path, False)
                    self.signals.log_message.emit(f"권한 없음: {file_name}", "error")

                except Exception as e:
                    fail_count += 1
                    self.signals.file_completed.emit(file_path, False)
                    self.signals.log_message.emit(f"삭제 오류 {file_name}: {str(e)}", "error")

            # 최종 진행률 100%
            self.signals.progress_updated.emit(100, "", total_files, total_files)

            # 완료 메시지
            if fail_count == 0:
                message = f"성공적으로 {success_count}개 파일을 삭제했습니다."
                self.signals.log_message.emit(message, "success")
                self.signals.delete_completed.emit(True, message)
            else:
                message = f"{success_count}개 삭제 성공, {fail_count}개 실패"
                self.signals.log_message.emit(message, "error")
                self.signals.delete_completed.emit(False, message)

        except Exception as e:
            logger.error(f"Delete worker error: {e}")
            self.signals.delete_completed.emit(False, f"삭제 중 오류 발생: {str(e)}")

        finally:
            self._is_running = False


class DeleteDialog(ThemedDialog):
    """
    비동기 파일 삭제 다이얼로그
    """

    # 삭제 완료 시그널
    delete_completed = pyqtSignal(bool)  # success

    def __init__(self, file_paths: List[str], parent=None):
        """
        초기화

        Args:
            file_paths: 삭제할 파일 경로 리스트
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.file_paths = file_paths
        self.worker = None
        self._is_deleting = False

        self._setup_ui()
        self._update_info()

    def _setup_ui(self):
        """UI 구성"""
        self.setWindowTitle("녹화 파일 삭제")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # 삭제 정보 그룹
        info_group = QGroupBox("삭제 정보")
        info_layout = QVBoxLayout()

        self.file_count_label = QLabel("파일 개수: 0")
        self.total_size_label = QLabel("전체 크기: 0 MB")

        info_layout.addWidget(self.file_count_label)
        info_layout.addWidget(self.total_size_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 진행 상태 그룹
        progress_group = QGroupBox("진행 상태")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.current_file_label = QLabel("삭제 준비 중")
        self.progress_detail_label = QLabel("0 / 0")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.current_file_label)
        progress_layout.addWidget(self.progress_detail_label)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # 삭제 로그 그룹
        log_group = QGroupBox("삭제 로그")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)

        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("삭제 시작")
        self.start_button.clicked.connect(self._on_start_delete)

        self.stop_button = QPushButton("중지")
        self.stop_button.clicked.connect(self._on_stop_delete)
        self.stop_button.setEnabled(False)

        self.close_button = QPushButton("닫기")
        self.close_button.clicked.connect(self._on_close)

        # 버튼을 우측으로 정렬
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _update_info(self):
        """삭제 정보 업데이트"""
        file_count = len(self.file_paths)
        total_size = 0

        for file_path in self.file_paths:
            try:
                file = Path(file_path)
                if file.exists():
                    total_size += file.stat().st_size
            except:
                pass

        total_size_mb = total_size / (1024 * 1024)

        self.file_count_label.setText(f"파일 개수: {file_count}")
        self.total_size_label.setText(f"전체 크기: {total_size_mb:.2f} MB")

        # 초기 로그 메시지
        self._add_log(f"{file_count}개 파일 삭제 준비 완료 ({total_size_mb:.2f} MB)", "info")

    def _add_log(self, message: str, level: str = "info"):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 레벨에 따른 색상 설정
        if level == "success":
            color = "green"
        elif level == "error":
            color = "red"
        else:
            color = "white"

        formatted_message = f'<span style="color: gray;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'

        # 텍스트 추가
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.insertHtml(formatted_message + "<br>")

        # 스크롤을 맨 아래로
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_start_delete(self):
        """삭제 시작"""
        if self._is_deleting:
            return

        # 확인 대화상자
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"{len(self.file_paths)}개 파일을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self._is_deleting = True

        # UI 업데이트
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.close_button.setEnabled(False)

        # Worker 생성 및 시그널 연결
        self.worker = DeleteWorker(self.file_paths)
        self.worker.signals.progress_updated.connect(self._on_progress_updated)
        self.worker.signals.file_completed.connect(self._on_file_completed)
        self.worker.signals.delete_completed.connect(self._on_delete_completed)
        self.worker.signals.log_message.connect(self._add_log)

        # 삭제 시작
        self.worker.start()

    def _on_stop_delete(self):
        """삭제 중지"""
        if self.worker and self._is_deleting:
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self._add_log("삭제 작업을 중지하는 중...", "info")

    def _on_progress_updated(self, progress: int, current_file: str, current_idx: int, total: int):
        """진행 상태 업데이트"""
        self.progress_bar.setValue(progress)

        if current_file:
            self.current_file_label.setText(f"삭제 중: {current_file}")
        else:
            self.current_file_label.setText("완료됨")

        self.progress_detail_label.setText(f"{current_idx} / {total}")

    def _on_file_completed(self, file_path: str, success: bool):
        """파일 삭제 완료"""
        # 개별 파일 처리 완료 (로그는 worker에서 처리)
        pass

    def _on_delete_completed(self, success: bool, message: str):
        """전체 삭제 완료"""
        self._is_deleting = False

        # UI 업데이트
        self.start_button.setEnabled(False)  # 이미 삭제됨
        self.stop_button.setEnabled(False)
        self.close_button.setEnabled(True)

        # 완료 시그널 발생
        self.delete_completed.emit(success)

        # 완료 메시지
        if success:
            QMessageBox.information(self, "삭제 완료", message)
        else:
            QMessageBox.warning(self, "삭제 미완료", message)

    def _on_close(self):
        """다이얼로그 닫기"""
        if self._is_deleting:
            reply = QMessageBox.question(
                self,
                "확인",
                "삭제가 진행 중입니다. 중지하고 닫으시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                if self.worker:
                    self.worker.stop()
                self.close()
        else:
            self.close()

    def closeEvent(self, event):
        """창 닫기 이벤트"""
        if self._is_deleting:
            event.ignore()
            self._on_close()
        else:
            event.accept()