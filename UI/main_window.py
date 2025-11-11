"""
메인 윈도우 UI
"""

import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from datetime import datetime, timedelta

from core.hospital_monitor import HospitalMonitor
from core.csv_exporter import CSVExporter
from core.database import DatabaseManager
from core.dummy_modbus_server import stop_all_dummy_servers
from .styles import UIStyles


class MainWindow(QMainWindow):
    """메인 윈도우"""
    
    def __init__(self, database, use_dummy=False):
        super().__init__()
        self.use_dummy = use_dummy
        self.database = database
        self.hospital_monitors = {}
        
        self.init_ui()
        
        # 테이블 초기화
        self.hospital_table.setRowCount(0)
        self.load_hospitals()
        
        # 시간 갱신 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()
        
        # UI 갱신 타이머
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("🏥 병원 전체전력량 모니터링 시스템")
        self.setGeometry(100, 50, 1200, 900)
        
        # 흰색 배경
        self.setStyleSheet("QMainWindow { background-color: white; }")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("QWidget { background-color: white; }")
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # ===== 상단: 제목 + 시간 =====
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🏥 병원 전체전력량 모니터링 시스템")
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        self.time_label = QLabel()
        time_font = self.time_label.font()
        time_font.setPointSize(14)
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.time_label)
        
        main_layout.addLayout(header_layout)
        
        # ===== CSV 내보내기 섹션 =====
        main_layout.addWidget(self.create_export_section())
        
        # ===== 병원 추가 섹션 =====
        main_layout.addWidget(self.create_add_hospital_section())
        
        # ===== 중단: 테이블 =====
        main_layout.addWidget(self.create_hospital_table(), stretch=3)
        
        # ===== 하단: 로그 =====
        main_layout.addWidget(self.create_log_section(), stretch=1)
        
        self.statusBar().showMessage("준비")
        status_font = self.statusBar().font()
        status_font.setPointSize(12)
        self.statusBar().setFont(status_font)
    
    def create_export_section(self):
        """CSV 내보내기 섹션"""
        group = QGroupBox("📥 데이터 저장 (CSV)")
        group.setStyleSheet(UIStyles.group_box_style())
        
        layout = QHBoxLayout()
        
        # 시작 날짜/시간
        layout.addWidget(self.create_label("시작:"))
        self.start_datetime = QDateTimeEdit()
        self.start_datetime.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.start_datetime.setCalendarPopup(True)
        self.start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_datetime.setMinimumHeight(35)
        font = self.start_datetime.font()
        font.setPointSize(11)
        self.start_datetime.setFont(font)
        layout.addWidget(self.start_datetime)
        
        # 종료 날짜/시간
        layout.addWidget(self.create_label("종료:"))
        self.end_datetime = QDateTimeEdit()
        self.end_datetime.setDateTime(QDateTime.currentDateTime())
        self.end_datetime.setCalendarPopup(True)
        self.end_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_datetime.setMinimumHeight(35)
        self.end_datetime.setFont(font)
        layout.addWidget(self.end_datetime)
        
        # 내보내기 버튼
        export_btn = QPushButton("📥 CSV 저장")
        export_btn.clicked.connect(self.export_to_csv)
        export_btn.setMinimumHeight(35)
        export_btn.setFont(font)
        export_btn.setStyleSheet(UIStyles.export_button_style())
        layout.addWidget(export_btn)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def create_add_hospital_section(self):
        """병원 추가 섹션"""
        group = QGroupBox("➕ 병원 추가")
        group.setStyleSheet(UIStyles.group_box_style())
        
        layout = QHBoxLayout()
        
        # 병원명
        layout.addWidget(self.create_label("병원명:"))
        self.hospital_name_input = QLineEdit()
        self.hospital_name_input.setPlaceholderText("지역+병원 입력")
        self.hospital_name_input.setMinimumHeight(35)
        font = self.hospital_name_input.font()
        font.setPointSize(11)
        self.hospital_name_input.setFont(font)
        layout.addWidget(self.hospital_name_input)
        
        # HMI IP
        layout.addWidget(self.create_label("HMI IP:"))
        self.hmi_ip_input = QLineEdit()
        self.hmi_ip_input.setPlaceholderText("ex: 192.168.0.6")
        self.hmi_ip_input.setMinimumHeight(35)
        self.hmi_ip_input.setFont(font)
        layout.addWidget(self.hmi_ip_input)
        
        # 포트
        layout.addWidget(self.create_label("포트:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8000)
        self.port_input.setMinimumHeight(35)
        self.port_input.setFont(font)
        self.port_input.setMinimumWidth(80)
        layout.addWidget(self.port_input)
        
        # 추가 버튼
        add_btn = QPushButton("➕ 추가")
        add_btn.clicked.connect(self.add_hospital)
        add_btn.setMinimumHeight(35)
        add_btn.setFont(font)
        add_btn.setStyleSheet(UIStyles.add_button_style())
        layout.addWidget(add_btn)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def create_label(self, text):
        """라벨 생성"""
        label = QLabel(text)
        font = label.font()
        font.setPointSize(11)
        label.setFont(font)
        return label
    
    def create_hospital_table(self):
        """병원 테이블"""
        group = QGroupBox("📊 실시간 모니터링")
        group.setStyleSheet(UIStyles.group_box_style())
        
        layout = QVBoxLayout()
        
        self.hospital_table = QTableWidget()
        self.hospital_table.setColumnCount(4)
        self.hospital_table.setHorizontalHeaderLabels([
            "순서", "병원명", "전체전력량 (kWh)", "액션"
        ])
        
        header = self.hospital_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        table_font = self.hospital_table.font()
        table_font.setPointSize(12)
        self.hospital_table.setFont(table_font)
        
        header_font = header.font()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        
        self.hospital_table.setAlternatingRowColors(True)
        self.hospital_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hospital_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.hospital_table.setMinimumHeight(300)
        
        layout.addWidget(self.hospital_table)
        group.setLayout(layout)
        return group
    
    def create_log_section(self):
        """로그 섹션"""
        group = QGroupBox("📝 시스템 로그")
        group.setStyleSheet(UIStyles.group_box_style())
        
        layout = QVBoxLayout()
        
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_font = self.log_text.font()
        log_font.setPointSize(10)
        self.log_text.setFont(log_font)
        self.log_text.setStyleSheet(UIStyles.log_text_style())
        
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group
    
    def export_to_csv(self):
        """CSV로 내보내기"""
        start_dt = self.start_datetime.dateTime().toPyDateTime()
        end_dt = self.end_datetime.dateTime().toPyDateTime()
        
        if start_dt >= end_dt:
            QMessageBox.warning(self, "입력 오류", "시작 시간이 종료 시간보다 먼저여야 합니다")
            return
        
        if (end_dt - start_dt).total_seconds() > 90 * 24 * 3600:
            QMessageBox.warning(self, "입력 오류", "최대 90일까지만 내보낼 수 있습니다")
            return
        
        download_folder = os.path.expanduser("~/Downloads")
        export_dir = os.path.join(download_folder, "병원전력량데이터")
        
        self.statusBar().showMessage("CSV 내보내기 중...")
        
        try:
            exporter = CSVExporter(export_dir=export_dir)
            hospitals = self.database.get_hospitals()
            
            results, filepaths = exporter.export_all_hospitals(
                self.database,
                hospitals,
                start_dt,
                end_dt
            )
            
            success_count = sum(1 for success, _ in results if success)
            total_count = len(results)
            
            message = f"CSV 내보내기 완료!\n\n"
            message += f"성공: {success_count}/{total_count}\n\n"
            
            for (success, msg) in results:
                if success:
                    message += f"✅ {msg}\n"
                else:
                    message += f"❌ {msg}\n"
            
            if success_count > 0:
                message += f"\n저장 위치:\n{os.path.abspath(export_dir)}"
                self.add_log(f"✅ CSV 내보내기 완료 ({success_count}개 파일)")
                self.add_log(f"📁 저장 위치: {export_dir}")
            else:
                self.add_log(f"⚠️ CSV 내보내기: 저장할 데이터 없음")
            
            QMessageBox.information(self, "내보내기 완료", message)
        
        except Exception as e:
            self.add_log(f"❌ CSV 내보내기 오류: {e}")
            QMessageBox.critical(self, "오류", f"CSV 내보내기 중 오류 발생:\n{e}")
        
        finally:
            self.statusBar().showMessage("준비")
    
    def add_hospital(self):
        """병원 추가"""
        hospital_name = self.hospital_name_input.text().strip()
        hmi_ip = self.hmi_ip_input.text().strip()
        port = self.port_input.value()
        
        if not hospital_name:
            QMessageBox.warning(self, "입력 오류", "병원명을 입력하세요")
            return
        
        if not hmi_ip:
            QMessageBox.warning(self, "입력 오류", "HMI IP를 입력하세요")
            return
        
        if hospital_name in self.hospital_monitors:
            QMessageBox.warning(self, "중복 오류", f"{hospital_name}은(는) 이미 등록되어 있습니다")
            return
        
        table_name = f"{hospital_name.replace(' ', '_').lower()}_1min"
        
        # DB에 병원 등록
        success = self.database.register_hospital(
            hospital_name=hospital_name,
            table_name=table_name,
            hmi_ip=hmi_ip,
            port=port,
            unit_id=128,
            meter_type='3P4W'
        )
        
        if not success:
            self.add_log("⚠️ DB 등록 실패 (DB 없이 실행)")
        
        # 병원 정보
        hospital_info = {
            'hospital_name': hospital_name,
            'table_name': table_name,
            'hmi_ip': hmi_ip,
            'port': port,
            'unit_id': 128,
            'meter_type': '3P4W'
        }
        
        # 모니터 생성 및 시작
        monitor = HospitalMonitor(hospital_info, self.database, use_dummy=self.use_dummy)
        monitor.modbus_thread.log_message.connect(self.add_log)
        monitor.db_writer.log_message.connect(self.add_log)
        monitor.start()
        
        self.hospital_monitors[hospital_name] = monitor
        
        # 테이블에 추가
        self.add_hospital_to_table(hospital_name)
        
        # 입력 필드 초기화
        self.hospital_name_input.clear()
        self.hmi_ip_input.clear()
        
        self.add_log(f"✅ {hospital_name} 추가 완료")
    
    def add_hospital_to_table(self, hospital_name):
        """테이블에 병원 행 추가"""
        row = self.hospital_table.rowCount()
        
        # 중복 체크
        for r in range(row):
            existing_name = self.hospital_table.item(r, 1).text()
            if existing_name == hospital_name:
                self.add_log(f"⚠️ {hospital_name}은 이미 테이블에 있습니다.")
                return
        
        self.hospital_table.insertRow(row)
        self.hospital_table.setRowHeight(row, 35)
        
        # 순서
        order_item = QTableWidgetItem(str(row + 1))
        order_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 0, order_item)
        
        # 병원명
        name_item = QTableWidgetItem(hospital_name)
        name_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 1, name_item)
        
        # 전체전력량
        energy_item = QTableWidgetItem("0")
        energy_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 2, energy_item)
        
        # 삭제 버튼
        btn_layout = QHBoxLayout()
        delete_btn = QPushButton("🗑️ 삭제")
        delete_btn.setFont(self.get_table_font())
        delete_btn.clicked.connect(lambda: self.delete_hospital(hospital_name, row))
        delete_btn.setStyleSheet(UIStyles.delete_button_style())
        btn_layout.addWidget(delete_btn)
        
        btn_widget = QWidget()
        btn_widget.setLayout(btn_layout)
        self.hospital_table.setCellWidget(row, 3, btn_widget)
    
    def delete_hospital(self, hospital_name, row):
        """병원 삭제"""
        reply = QMessageBox.question(
            self,
            "확인",
            f"{hospital_name} 모니터링을 중지하고 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            monitor = self.hospital_monitors.get(hospital_name)
            if monitor:
                monitor.stop()
                del self.hospital_monitors[hospital_name]
            
            self.hospital_table.removeRow(row)
            self.add_log(f"🗑️ {hospital_name} 삭제됨")
    
    def load_hospitals(self):
        """DB에서 병원 목록 로드"""
        hospitals = self.database.get_hospitals()
        
        # 중복 방지
        if len(self.hospital_monitors) > 0:
            self.add_log("⚠️ 이미 로드된 병원이 있습니다.")
            return
        
        # DB가 비어있으면
        if len(hospitals) == 0:
            self.add_log("📝 DB가 비어있습니다. UI에서 병원을 추가해주세요.")
            return
        
        # 각 병원 모니터 생성
        for hospital in hospitals:
            if hospital['hospital_name'] in self.hospital_monitors:
                continue
            
            monitor = HospitalMonitor(hospital, self.database, use_dummy=self.use_dummy)
            monitor.modbus_thread.log_message.connect(self.add_log)
            monitor.db_writer.log_message.connect(self.add_log)
            monitor.start()
            
            self.hospital_monitors[hospital['hospital_name']] = monitor
            self.add_hospital_to_table(hospital['hospital_name'])
            self.add_log(f"✅ {hospital['hospital_name']} 모니터링 시작")
    
    def update_display(self):
        """화면 갱신"""
        for row in range(self.hospital_table.rowCount()):
            hospital_name = self.hospital_table.item(row, 1).text()
            monitor = self.hospital_monitors.get(hospital_name)
            
            if monitor and monitor.latest_total_energy is not None:
                energy_item = QTableWidgetItem(f"{monitor.latest_total_energy:,}")
                energy_item.setFont(self.get_table_font())
                energy_item.setForeground(QColor(0, 120, 215))
                energy_font = energy_item.font()
                energy_font.setBold(True)
                energy_item.setFont(energy_font)
                self.hospital_table.setItem(row, 2, energy_item)
    
    def update_time(self):
        """현재 시간 업데이트"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(f"⏰ {current_time}")
    
    def get_table_font(self):
        """테이블 글자 스타일"""
        font = QFont()
        font.setPointSize(12)
        return font
    
    def add_log(self, message):
        """로그 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """종료"""
        reply = QMessageBox.question(
            self,
            "종료 확인",
            "모니터링을 중지하고 종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            stop_all_dummy_servers()
            for monitor in self.hospital_monitors.values():
                monitor.stop()
            self.database.close()
            event.accept()
        else:
            event.ignore()
