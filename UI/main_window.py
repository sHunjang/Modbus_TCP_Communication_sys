#!/usr/bin/env python3
# UI/main_window.py

"""
PyQt 메인 윈도우

중앙 모니터링 시스템의 로컬 관리자 UI
"""

import os
import subprocess
import platform
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QPlainTextEdit, QGroupBox, QMessageBox,
    QDialog, QComboBox, QDateTimeEdit
)
from PyQt6.QtCore import QTimer, Qt, QDateTime
from PyQt6.QtGui import QFont, QColor

from core.csv_exporter import CSVExporter
from UI.styles import UIStyles


class CentralMainWindow(QMainWindow):
    """중앙 모니터링 메인 윈도우"""

    def __init__(
        self, 
        hospital_data, 
        data_lock, 
        hospital_status, 
        status_lock,
        log_messages,
        log_lock,
        db,
        tcp_port,
        web_port,
        timeout_seconds
    ):
        """
        Args:
            hospital_data: 병원 데이터 딕셔너리 (공유)
            data_lock: 데이터 락
            hospital_status: 통신 상태 딕셔너리 (공유)
            status_lock: 상태 락
            log_messages: 로그 메시지 리스트 (공유)
            log_lock: 로그 락
            db: DatabaseManager 인스턴스
            tcp_port: TCP 포트 번호
            web_port: 웹 포트 번호
            timeout_seconds: 타임아웃 시간
        """
        super().__init__()
        
        # 공유 데이터
        self.hospital_data = hospital_data
        self.data_lock = data_lock
        self.hospital_status = hospital_status
        self.status_lock = status_lock
        self.log_messages = log_messages
        self.log_lock = log_lock
        self.db = db
        
        # 설정
        self.tcp_port = tcp_port
        self.web_port = web_port
        self.timeout_seconds = timeout_seconds
        
        # CSV 내보내기
        self.exporter = CSVExporter()
        
        # 알림 이력
        self.alert_shown = set()
        
        # UI 초기화
        self.init_ui()
        
        # 타이머 설정
        self.setup_timers()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("🏥 중앙 모니터링 시스템 v1.2 (통합)")
        self.setGeometry(100, 50, 1200, 750)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 헤더
        layout.addLayout(self.create_header())
        
        # 테이블
        layout.addWidget(self.create_table(), stretch=3)
        
        # 로그
        layout.addWidget(self.create_log(), stretch=1)

        # 상태바
        db_status = "✅ DB 연결" if (self.db and self.db.db_available) else "⚠️ DB 끊김"
        self.statusBar().showMessage(
            f"서버 시작 | {db_status} | 10초 단위 저장 | 타임아웃: {self.timeout_seconds}초"
        )

    def create_header(self):
        """헤더 생성"""
        header = QHBoxLayout()

        title = QLabel(f"🏥 중앙 모니터링 시스템 (TCP: {self.tcp_port} / WEB: {self.web_port})")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)

        self.time_label = QLabel()
        time_font = self.time_label.font()
        time_font.setPointSize(14)
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self.time_label)

        return header

    def create_table(self):
        """병원 테이블 생성"""
        group = QGroupBox("📊 실시간 전력량 (10초 갱신)")
        group.setStyleSheet(UIStyles.group_box_style())

        layout = QVBoxLayout()
        
        # CSV 버튼
        button_layout = QHBoxLayout()
        export_btn = QPushButton("📥 CSV 내보내기")
        export_btn.setFont(QFont("", 11))
        export_btn.setStyleSheet(UIStyles.primary_button_style())
        export_btn.clicked.connect(self.open_export_dialog)
        button_layout.addWidget(export_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 테이블
        self.hospital_table = QTableWidget()
        self.hospital_table.setColumnCount(4)
        self.hospital_table.setHorizontalHeaderLabels(
            ["순서", "병원명 (IP:포트)", "전체 전력량 (kWh)", "액션"]
        )

        header = self.hospital_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.hospital_table.setFont(QFont("", 12))
        header.setFont(QFont("", 13, QFont.Weight.Bold))
        self.hospital_table.setAlternatingRowColors(True)
        self.hospital_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hospital_table.setMinimumHeight(300)

        layout.addWidget(self.hospital_table)
        group.setLayout(layout)
        return group

    def create_log(self):
        """로그 섹션 생성"""
        group = QGroupBox("📝 시스템 로그")
        group.setStyleSheet(UIStyles.group_box_style())

        layout = QVBoxLayout()
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group

    def setup_timers(self):
        """타이머 설정"""
        # UI 갱신 타이머
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

        # 시계 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

    def update_display(self):
        """UI 갱신"""
        # 로그 처리
        with self.log_lock:
            while self.log_messages:
                msg = self.log_messages.pop(0)
                if msg.startswith("ALERT:"):
                    alert_text = msg[6:]
                    self.show_alert(alert_text)
                else:
                    self.add_log_to_ui(msg)

        # 테이블 갱신
        with self.data_lock:
            data_copy = dict(self.hospital_data)
        
        with self.status_lock:
            status_copy = dict(self.hospital_status)

        self.hospital_table.setRowCount(len(data_copy))

        for idx, (hospital_name, info) in enumerate(sorted(data_copy.items())):
            self.hospital_table.setRowHeight(idx, 40)

            # 순서
            order_item = QTableWidgetItem(str(idx + 1))
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hospital_table.setItem(idx, 0, order_item)

            # 병원명
            display_name = f"{hospital_name} ({info['ip']}:{info['port']})"
            name_item = QTableWidgetItem(display_name)
            
            # 통신 상태 색상
            if hospital_name in status_copy:
                status = status_copy[hospital_name]
                elapsed = (datetime.now() - status["last_received"]).total_seconds()
                
                if elapsed > self.timeout_seconds:
                    name_item.setForeground(QColor(200, 0, 0))
                else:
                    name_item.setForeground(QColor(0, 0, 0))
            
            self.hospital_table.setItem(idx, 1, name_item)

            # 전력량
            value_item = QTableWidgetItem(info["value"])
            value_font = QFont("", 12, QFont.Weight.Bold)
            value_item.setFont(value_font)
            value_item.setForeground(QColor(0, 120, 215))
            value_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.hospital_table.setItem(idx, 2, value_item)

            # 삭제 버튼
            delete_btn = QPushButton("🗑️ 삭제")
            delete_btn.setStyleSheet(UIStyles.delete_button_style())
            delete_btn.clicked.connect(lambda _, h=hospital_name: self.delete_hospital(h))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.addWidget(delete_btn)
            btn_layout.setContentsMargins(5, 5, 5, 5)
            self.hospital_table.setCellWidget(idx, 3, btn_widget)

    def show_alert(self, message: str):
        """알림창 표시"""
        if message in self.alert_shown:
            return
        
        self.alert_shown.add(message)
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("⚠️ 통신 경고")
        msg_box.setText("병원 통신 두절 감지!")
        msg_box.setInformativeText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.show()
        QTimer.singleShot(5000, msg_box.close)

    def delete_hospital(self, hospital_name: str):
        """병원 삭제"""
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"{hospital_name}을(를) 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            with self.data_lock:
                self.hospital_data.pop(hospital_name, None)
            with self.status_lock:
                self.hospital_status.pop(hospital_name, None)
            self.alert_shown = {msg for msg in self.alert_shown if hospital_name not in msg}
            self.log(f"🗑️ {hospital_name} 삭제")

    def open_export_dialog(self):
        """CSV 내보내기 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("CSV 내보내기")
        dialog.setFixedSize(500, 300)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("병원 선택:"))
        
        hospital_combo = QComboBox()
        with self.data_lock:
            hospital_list = list(self.hospital_data.keys())
        
        if not hospital_list:
            QMessageBox.warning(self, "경고", "등록된 병원이 없습니다.")
            return
        
        hospital_combo.addItems(hospital_list)
        layout.addWidget(hospital_combo)
        
        layout.addWidget(QLabel("시작 시간:"))
        start_datetime = QDateTimeEdit()
        start_datetime.setCalendarPopup(True)
        start_datetime.setDateTime(QDateTime.currentDateTime().addDays(-1))
        start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(start_datetime)
        
        layout.addWidget(QLabel("종료 시간:"))
        end_datetime = QDateTimeEdit()
        end_datetime.setCalendarPopup(True)
        end_datetime.setDateTime(QDateTime.currentDateTime())
        end_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(end_datetime)
        
        button_layout = QHBoxLayout()
        export_button = QPushButton("내보내기")
        export_button.clicked.connect(lambda: self.do_export(
            dialog,
            hospital_combo.currentText(),
            start_datetime.dateTime().toPyDateTime(),
            end_datetime.dateTime().toPyDateTime()
        ))
        
        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(export_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        dialog.exec()

    def do_export(self, dialog, hospital_name, start_dt, end_dt):
        """CSV 내보내기 수행"""
        success, filepath, message = self.exporter.export_hospital_data(
            self.db, hospital_name, start_dt, end_dt
        )
        
        dialog.accept()
        
        if success:
            reply = QMessageBox.question(
                self, "내보내기 완료",
                f"{message}\n\n파일: {filepath}\n\n폴더를 여시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                folder = os.path.dirname(filepath)
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
        else:
            QMessageBox.critical(self, "오류", message)

    def update_time(self):
        """시계 갱신"""
        self.time_label.setText(
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def add_log_to_ui(self, message: str):
        """로그 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def log(self, message: str):
        """로그 메시지 추가 (공유 리스트에)"""
        with self.log_lock:
            self.log_messages.append(message)
        print(message)

    def closeEvent(self, event):
        """종료 처리"""
        reply = QMessageBox.question(
            self, "종료 확인", "종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.db:
                self.db.close()
            event.accept()
        else:
            event.ignore()
