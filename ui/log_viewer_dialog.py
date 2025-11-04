"""
Log Viewer Dialog
로그 검색 및 조회 다이얼로그
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QDateEdit, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QCheckBox, QSpinBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QColor, QTextCursor, QFont
from pathlib import Path
from datetime import datetime, timedelta
import re
from loguru import logger

from ui.theme import ThemedDialog


class LogViewerDialog(ThemedDialog):
    """로그 검색 및 조회 다이얼로그"""

    # 로그 레벨 색상
    LEVEL_COLORS = {
        'DEBUG': QColor(150, 150, 150),
        'INFO': QColor(100, 200, 100),
        'SUCCESS': QColor(100, 255, 100),
        'WARNING': QColor(255, 200, 100),
        'ERROR': QColor(255, 100, 100),
        'CRITICAL': QColor(255, 50, 50),
    }

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.log_entries = []
        self.filtered_entries = []

        self.setWindowTitle("Log Viewer")
        self.setMinimumSize(1200, 700)

        self._setup_ui()
        self._load_log_files()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)

        # 필터 그룹
        filter_group = self._create_filter_group()
        layout.addWidget(filter_group)

        # 스플리터로 테이블과 상세 뷰 분리
        splitter = QSplitter(Qt.Vertical)

        # 로그 테이블
        self.log_table = self._create_log_table()
        splitter.addWidget(self.log_table)

        # 상세 뷰
        detail_group = QGroupBox("Log Detail")
        detail_layout = QVBoxLayout()
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 9))
        detail_layout.addWidget(self.detail_text)
        detail_group.setLayout(detail_layout)
        splitter.addWidget(detail_group)

        # 스플리터 비율 설정
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # 버튼
        button_layout = self._create_buttons()
        layout.addLayout(button_layout)

    def _create_filter_group(self):
        """필터 그룹 생성"""
        group = QGroupBox("Search Filters")
        layout = QVBoxLayout()

        # 첫 번째 행: 로그 타입, 날짜 범위
        row1 = QHBoxLayout()

        # 로그 타입 선택
        row1.addWidget(QLabel("Log Type:"))
        self.log_type_combo = QComboBox()
        self.log_type_combo.addItems([
            "All Logs",
            "General Log (pynvr_*.log)",
            "Error Log (pynvr_errors_*.log)",
            "JSON Log (pynvr_*.json)"
        ])
        self.log_type_combo.currentIndexChanged.connect(self._on_log_type_changed)
        row1.addWidget(self.log_type_combo, 1)

        row1.addSpacing(20)

        # 날짜 범위
        row1.addWidget(QLabel("From:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-7))
        self.from_date.dateChanged.connect(self._on_filter_changed)
        row1.addWidget(self.from_date)

        row1.addWidget(QLabel("To:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.dateChanged.connect(self._on_filter_changed)
        row1.addWidget(self.to_date)

        layout.addLayout(row1)

        # 두 번째 행: 로그 레벨, 검색어
        row2 = QHBoxLayout()

        # 로그 레벨 체크박스
        row2.addWidget(QLabel("Level:"))
        self.level_checkboxes = {}
        for level in ['DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']:
            cb = QCheckBox(level)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_filter_changed)
            self.level_checkboxes[level] = cb
            row2.addWidget(cb)

        layout.addLayout(row2)

        # 세 번째 행: 텍스트 검색
        row3 = QHBoxLayout()

        row3.addWidget(QLabel("Search Text:"))
        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText("Enter text to search in log messages...")
        self.search_text.textChanged.connect(self._on_search_text_changed)
        row3.addWidget(self.search_text, 1)

        self.case_sensitive_cb = QCheckBox("Case Sensitive")
        self.case_sensitive_cb.stateChanged.connect(self._on_filter_changed)
        row3.addWidget(self.case_sensitive_cb)

        self.regex_cb = QCheckBox("Regex")
        self.regex_cb.stateChanged.connect(self._on_filter_changed)
        row3.addWidget(self.regex_cb)

        layout.addLayout(row3)

        # 네 번째 행: 결과 개수, 새로고침
        row4 = QHBoxLayout()

        row4.addWidget(QLabel("Max Results:"))
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(100, 10000)
        self.max_results_spin.setValue(1000)
        self.max_results_spin.setSingleStep(100)
        self.max_results_spin.valueChanged.connect(self._on_filter_changed)
        row4.addWidget(self.max_results_spin)

        row4.addStretch()

        self.result_label = QLabel("Results: 0")
        row4.addWidget(self.result_label)

        row4.addSpacing(20)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_log_files)
        row4.addWidget(refresh_btn)

        apply_btn = QPushButton("Apply Filters")
        apply_btn.clicked.connect(self._apply_filters)
        row4.addWidget(apply_btn)

        layout.addLayout(row4)

        group.setLayout(layout)
        return group

    def _create_log_table(self):
        """로그 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Time", "Level", "Source", "Function", "Message"])

        # 컬럼 너비 설정
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Level
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Source
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Function
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Message

        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.itemSelectionChanged.connect(self._on_row_selected)

        return table

    def _create_buttons(self):
        """버튼 레이아웃 생성"""
        layout = QHBoxLayout()

        export_btn = QPushButton("Export to File")
        export_btn.clicked.connect(self._export_logs)
        layout.addWidget(export_btn)

        clear_btn = QPushButton("Clear Display")
        clear_btn.clicked.connect(self._clear_display)
        layout.addWidget(clear_btn)

        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        return layout

    def _on_log_type_changed(self):
        """로그 타입 변경 시"""
        self._load_log_files()

    def _on_filter_changed(self):
        """필터 변경 시 (자동 적용은 하지 않음)"""
        pass

    def _on_search_text_changed(self):
        """검색 텍스트 변경 시 (500ms 딜레이 후 자동 적용)"""
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filters)
        self._search_timer.start(500)

    def _load_log_files(self):
        """로그 파일 로드"""
        try:
            log_config = self.config_manager.config.get('logging', {})
            log_path = Path(log_config.get('log_path', './_logs'))

            if not log_path.exists():
                QMessageBox.warning(self, "Warning", f"Log directory not found: {log_path}")
                return

            # 로그 타입에 따라 파일 패턴 결정
            log_type = self.log_type_combo.currentText()
            if "General Log" in log_type:
                pattern = "pynvr_*.log"
            elif "Error Log" in log_type:
                pattern = "pynvr_errors_*.log"
            elif "JSON Log" in log_type:
                pattern = "pynvr_*.json"
            else:  # All Logs
                pattern = "pynvr_*"

            # 파일 목록 가져오기
            log_files = sorted(log_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

            if not log_files:
                QMessageBox.information(self, "Information", f"No log files found matching: {pattern}")
                self.log_entries = []
                self._apply_filters()
                return

            # 로그 파일 파싱
            self.log_entries = []
            parsed_files = 0
            for log_file in log_files[:20]:  # 최근 20개 파일만
                before_count = len(self.log_entries)
                self._parse_log_file(log_file)
                after_count = len(self.log_entries)
                if after_count > before_count:
                    parsed_files += 1
                    logger.debug(f"Parsed {after_count - before_count} entries from {log_file.name}")

            logger.info(f"Loaded {len(self.log_entries)} log entries from {parsed_files}/{len(log_files)} files")

            if len(self.log_entries) == 0:
                logger.warning("No log entries parsed - check log format")

            # 필터 적용
            self._apply_filters()

        except Exception as e:
            logger.error(f"Failed to load log files: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load log files:\n{e}")

    def _parse_log_file(self, log_file: Path):
        """로그 파일 파싱"""
        try:
            # JSON 로그는 별도 처리
            if log_file.suffix == '.json':
                self._parse_json_log(log_file)
                return

            # 일반 텍스트 로그 파싱
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = self._parse_log_line(line.strip(), log_file.name)
                    if entry:
                        self.log_entries.append(entry)

        except Exception as e:
            logger.error(f"Failed to parse log file {log_file}: {e}")

    def _parse_log_line(self, line: str, filename: str):
        """로그 라인 파싱"""
        if not line:
            return None

        # 로그 포맷: 2025-11-03 09:25:54 | INFO     | __main__:setup_logging:122 | message
        # 패턴: timestamp | level(공백 포함) | source:function:line | message
        pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\|\s+(\w+)\s+\|\s+([^:]+):([^:]+):(\d+)\s+\|\s+(.+)$'
        match = re.match(pattern, line)

        if match:
            timestamp, level, source, function, line_no, message = match.groups()
            return {
                'timestamp': timestamp,
                'level': level.strip(),
                'source': source.strip(),
                'function': function.strip(),
                'line': line_no.strip(),
                'message': message.strip(),
                'filename': filename,
                'raw': line
            }

        # 로그 라인이 파싱되지 않으면 None 반환 (멀티라인 로그 등)
        return None

    def _parse_json_log(self, log_file: Path):
        """JSON 로그 파싱 (구현 생략 - 필요시 추가)"""
        pass

    def _apply_filters(self):
        """필터 적용"""
        try:
            # 선택된 레벨
            selected_levels = [level for level, cb in self.level_checkboxes.items() if cb.isChecked()]

            # 날짜 범위
            from_date_qdate = self.from_date.date().toPyDate()
            to_date_qdate = self.to_date.date().toPyDate()

            # datetime으로 변환 (시작일 00:00:00, 종료일 23:59:59)
            from_date = datetime.combine(from_date_qdate, datetime.min.time())
            to_date = datetime.combine(to_date_qdate, datetime.max.time())

            # 검색 텍스트
            search_text = self.search_text.text()
            case_sensitive = self.case_sensitive_cb.isChecked()
            use_regex = self.regex_cb.isChecked()

            # 필터링
            self.filtered_entries = []
            for entry in self.log_entries:
                # 레벨 필터
                if entry['level'] not in selected_levels:
                    continue

                # 날짜 필터
                try:
                    entry_date = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S')
                    if entry_date < from_date or entry_date > to_date:
                        continue
                except:
                    continue

                # 텍스트 검색
                if search_text:
                    message = entry['message']
                    if use_regex:
                        try:
                            flags = 0 if case_sensitive else re.IGNORECASE
                            if not re.search(search_text, message, flags):
                                continue
                        except re.error:
                            # 잘못된 정규식
                            continue
                    else:
                        if case_sensitive:
                            if search_text not in message:
                                continue
                        else:
                            if search_text.lower() not in message.lower():
                                continue

                self.filtered_entries.append(entry)

            # 최대 결과 수 제한
            max_results = self.max_results_spin.value()
            self.filtered_entries = self.filtered_entries[:max_results]

            # 테이블 업데이트
            self._update_table()

            # 결과 레이블 업데이트
            self.result_label.setText(f"Results: {len(self.filtered_entries)}")

        except Exception as e:
            logger.error(f"Failed to apply filters: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply filters:\n{e}")

    def _update_table(self):
        """테이블 업데이트"""
        self.log_table.setRowCount(0)

        for entry in self.filtered_entries:
            row = self.log_table.rowCount()
            self.log_table.insertRow(row)

            # Time
            time_item = QTableWidgetItem(entry['timestamp'])
            self.log_table.setItem(row, 0, time_item)

            # Level
            level_item = QTableWidgetItem(entry['level'])
            level_color = self.LEVEL_COLORS.get(entry['level'], QColor(200, 200, 200))
            level_item.setForeground(level_color)
            self.log_table.setItem(row, 1, level_item)

            # Source
            source_item = QTableWidgetItem(entry['source'])
            self.log_table.setItem(row, 2, source_item)

            # Function
            function_item = QTableWidgetItem(f"{entry['function']}:{entry['line']}")
            self.log_table.setItem(row, 3, function_item)

            # Message
            message_item = QTableWidgetItem(entry['message'])
            self.log_table.setItem(row, 4, message_item)

    def _on_row_selected(self):
        """테이블 행 선택 시"""
        selected_rows = self.log_table.selectedItems()
        if not selected_rows:
            return

        row = self.log_table.currentRow()
        if 0 <= row < len(self.filtered_entries):
            entry = self.filtered_entries[row]

            # 상세 정보 표시
            detail = f"""Time: {entry['timestamp']}
Level: {entry['level']}
Source: {entry['source']}
Function: {entry['function']}:{entry['line']}
File: {entry['filename']}

Message:
{entry['message']}

Raw Log:
{entry['raw']}
"""
            self.detail_text.setPlainText(detail)

    def _export_logs(self):
        """로그 내보내기"""
        if not self.filtered_entries:
            QMessageBox.information(self, "Information", "No logs to export")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    for entry in self.filtered_entries:
                        f.write(f"{entry['raw']}\n")

                QMessageBox.information(self, "Success", f"Exported {len(self.filtered_entries)} logs to:\n{filename}")
                logger.info(f"Exported logs to {filename}")

            except Exception as e:
                logger.error(f"Failed to export logs: {e}")
                QMessageBox.critical(self, "Error", f"Failed to export logs:\n{e}")

    def _clear_display(self):
        """표시 내용 지우기"""
        reply = QMessageBox.question(
            self,
            "Clear Display",
            "Clear all displayed logs?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log_entries = []
            self.filtered_entries = []
            self._update_table()
            self.detail_text.clear()
            self.result_label.setText("Results: 0")
