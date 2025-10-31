#!/usr/bin/env python3
# main.py
"""
병원 전력량 모니터링 시스템 (CSV 내보내기 기능 포함)
- 병원 추가/삭제 기능
- 큰 글자 (16pt~)
- 흰색 배경
- 현재 시간 표시 (우측 상단)
- CSV 데이터 내보내기
"""

import sys
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from datetime import datetime, timedelta

from core.database import DatabaseManager
from core.modbus_thread import ModbusThread
from core.data_aggregator import DataAggregator
from core.db_writer import DBWriterThread
from core.dummy_modbus_server import create_dummy_server, stop_all_dummy_servers


# ============================================================
# 병원 모니터 클래스
# ============================================================

class HospitalMonitor:
    """병원 모니터링"""
    
    def __init__(self, hospital_info, database, use_dummy=False):
        """초기화"""
        self.hospital_info = hospital_info
        self.database = database
        self.hospital_name = hospital_info['hospital_name']
        self.table_name = hospital_info['table_name']
        
        # 더미 서버 생성
        if use_dummy:
            try:
                create_dummy_server(self.hospital_name, port=5020 + hash(self.hospital_name) % 100)
            except:
                pass
        
        self.aggregator = DataAggregator(self.hospital_name)
        
        # Modbus 스레드
        self.modbus_thread = ModbusThread(
            hospital_name=self.hospital_name,
            hmi_ip=hospital_info['hmi_ip'],
            port=hospital_info['port'],
            unit_id=hospital_info['unit_id'],
            meter_type=hospital_info.get('meter_type', '3P4W'),
            use_dummy=use_dummy
        )
        
        # DB 저장 스레드
        self.db_writer = DBWriterThread(
            database=self.database,
            aggregator=self.aggregator,
            table_name=self.table_name,
            hospital_name=self.hospital_name
        )
        
        self.latest_energy = None
    
    def start(self):
        """모니터링 시작"""
        self.modbus_thread.data_received.connect(self.on_data_received)
        self.modbus_thread.start()
        self.db_writer.start()
    
    def stop(self):
        """모니터링 중지"""
        self.modbus_thread.stop()
        self.modbus_thread.wait()
        self.db_writer.stop()
        self.db_writer.wait()
    
    def on_data_received(self, energy_kwh):
        """데이터 수신"""
        self.latest_energy = energy_kwh
        self.aggregator.add_data(energy_kwh)


# ============================================================
# CSV 내보내기 클래스
# ============================================================

class CSVExporter:
    """CSV 내보내기"""
    
    def __init__(self, export_dir="exports"):
        """초기화"""
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)
    
    def export_hospital_data(self, database, table_name, hospital_name, 
                            start_datetime, end_datetime):
        """병원 데이터를 CSV로 내보내기"""
        try:
            # DB에서 데이터 조회
            conn = database.get_connection()
            cursor = conn.cursor()
            
            query = f"""
                SELECT 
                    time,
                    energy_kwh_avg,
                    energy_kwh_max,
                    energy_kwh_min,
                    sample_count,
                    status
                FROM {table_name}
                WHERE time >= %s AND time <= %s
                ORDER BY time ASC
            """
            
            cursor.execute(query, (start_datetime, end_datetime))
            rows = cursor.fetchall()
            
            cursor.close()
            database.release_connection(conn)
            
            if not rows:
                return False, None, f"해당 기간에 데이터가 없습니다."
            
            # CSV 파일명 생성
            start_str = start_datetime.strftime("%Y%m%d_%H%M%S")
            end_str = end_datetime.strftime("%Y%m%d_%H%M%S")
            filename = f"{hospital_name}_{start_str}_to_{end_str}.csv"
            filepath = os.path.join(self.export_dir, filename)
            
            # CSV 파일 생성
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # 헤더
                writer.writerow([
                    "시간",
                    "평균 전력량 (kWh)",
                    "최대 전력량 (kWh)",
                    "최소 전력량 (kWh)",
                    "샘플 수",
                    "상태"
                ])
                
                # 데이터
                for row in rows:
                    time_str = row[0].strftime("%Y-%m-%d %H:%M:%S") if row[0] else ""
                    writer.writerow([
                        time_str,
                        f"{row[1]:.2f}" if row[1] else "",
                        f"{row[2]:.2f}" if row[2] else "",
                        f"{row[3]:.2f}" if row[3] else "",
                        row[4] if row[4] else "",
                        row[5] if row[5] else ""
                    ])
            
            # 통계
            data_count = len(rows)
            total_energy = sum(row[1] for row in rows if row[1])
            avg_energy = total_energy / data_count if data_count > 0 else 0
            
            message = f"{hospital_name} 데이터 {data_count}건 내보냄 (평균: {avg_energy:.2f} kWh)"
            
            return True, filepath, message
        
        except Exception as e:
            return False, None, f"CSV 내보내기 오류: {e}"
    
    def export_all_hospitals(self, database, hospitals_info, 
                            start_datetime, end_datetime):
        """모든 병원 데이터를 CSV로 내보내기"""
        
        results = []
        filepaths = []
        
        for hospital in hospitals_info:
            success, filepath, message = self.export_hospital_data(
                database,
                hospital['table_name'],
                hospital['hospital_name'],
                start_datetime,
                end_datetime
            )
            
            results.append((success, message))
            if success:
                filepaths.append(filepath)
        
        return results, filepaths


# ============================================================
# 메인 윈도우
# ============================================================

class MainWindow(QMainWindow):
    """메인 윈도우"""
    
    def __init__(self, use_dummy=False):
        super().__init__()
        
        self.use_dummy = use_dummy
        self.database = DatabaseManager()
        self.hospital_monitors = {}
        
        self.init_ui()
        
        # ✨ 테이블 초기화
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
        self.setWindowTitle("🏥 병원 전력량 모니터링 시스템")
        self.setGeometry(100, 50, 1200, 1000)
        
        # ✨ 흰색 배경
        self.setStyleSheet("QMainWindow { background-color: white; }")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("QWidget { background-color: white; }")
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # ===== 상단: 제목 + 시간 =====
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🏥 병원 전력량 모니터링 시스템")
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
        """CSV 저장 섹션"""
        group = QGroupBox("📥 데이터 저장 (CSV)")
        group.setStyleSheet("QGroupBox { font-size: 13pt; font-weight: bold; }")
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
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        group.setLayout(layout)
        
        return group
    
    def create_add_hospital_section(self):
        """병원 추가 섹션"""
        group = QGroupBox("➕ 병원 추가")
        group.setStyleSheet("QGroupBox { font-size: 13pt; font-weight: bold; }")
        layout = QHBoxLayout()
        
        # 병원명
        layout.addWidget(self.create_label("병원명:"))
        self.hospital_name_input = QLineEdit()
        self.hospital_name_input.setPlaceholderText("지역+병원 입력하시오.")
        self.hospital_name_input.setMinimumHeight(35)
        font = self.hospital_name_input.font()
        font.setPointSize(11)
        self.hospital_name_input.setFont(font)
        layout.addWidget(self.hospital_name_input)
        
        # HMI IP
        layout.addWidget(self.create_label("HMI IP:"))
        self.hmi_ip_input = QLineEdit()
        self.hmi_ip_input.setPlaceholderText("ex: 192.168.1.100")
        self.hmi_ip_input.setMinimumHeight(35)
        self.hmi_ip_input.setFont(font)
        layout.addWidget(self.hmi_ip_input)
        
        # 포트
        layout.addWidget(self.create_label("포트:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(502)  # ✨ 기본값 추가!
        self.port_input.setMinimumHeight(35)
        self.port_input.setFont(font)
        self.port_input.setMinimumWidth(80)
        layout.addWidget(self.port_input)
        
        # 추가 버튼
        add_btn = QPushButton("➕ 추가")
        add_btn.clicked.connect(self.add_hospital)
        add_btn.setMinimumHeight(35)
        add_btn.setFont(font)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
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
        group.setStyleSheet("QGroupBox { font-size: 13pt; font-weight: bold; }")
        layout = QVBoxLayout()
        
        self.hospital_table = QTableWidget()
        self.hospital_table.setColumnCount(4)
        self.hospital_table.setHorizontalHeaderLabels([
            "순서", "병원명", "전력량 (kWh)", " "
        ])
        
        header = self.hospital_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        table_font = self.hospital_table.font()
        table_font.setPointSize(12)
        self.hospital_table.setFont(table_font)
        self.hospital_table.setRowHeight(0, 40)
        
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
        group.setStyleSheet("QGroupBox { font-size: 13pt; font-weight: bold; }")
        layout = QVBoxLayout()
        
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
        log_font = self.log_text.font()
        log_font.setPointSize(10)
        self.log_text.setFont(log_font)
        
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
            }
        """)
        
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
        
        success = self.database.register_hospital(
            hospital_name=hospital_name,
            table_name=table_name,
            hmi_ip=hmi_ip,
            port=port,
            unit_id=1,
            meter_type='3P4W'
        )
        
        if not success:
            QMessageBox.critical(self, "DB 오류", "병원 등록에 실패했습니다")
            return
        
        hospital_info = {
            'hospital_name': hospital_name,
            'table_name': table_name,
            'hmi_ip': hmi_ip,
            'port': port,
            'unit_id': 1,
            'meter_type': '3P4W'
        }
        
        monitor = HospitalMonitor(hospital_info, self.database, use_dummy=self.use_dummy)
        monitor.modbus_thread.log_message.connect(self.add_log)
        monitor.db_writer.log_message.connect(self.add_log)
        monitor.start()
        
        self.hospital_monitors[hospital_name] = monitor
        
        self.add_hospital_to_table(hospital_name)
        
        self.hospital_name_input.clear()
        self.hmi_ip_input.clear()
        
        self.add_log(f"✅ {hospital_name} 추가 완료")
        QMessageBox.information(self, "성공", f"{hospital_name}이(가) 추가되었습니다")
    
    def add_hospital_to_table(self, hospital_name):
        """테이블에 병원 행 추가"""
        row = self.hospital_table.rowCount()
        
        # ✨ 중복 체크
        for r in range(row):
            existing_name = self.hospital_table.item(r, 1).text()
            if existing_name == hospital_name:
                self.add_log(f"⚠️ {hospital_name}은 이미 테이블에 있습니다.")
                return
        
        self.hospital_table.insertRow(row)
        self.hospital_table.setRowHeight(row, 35)
        
        monitor = self.hospital_monitors[hospital_name]
        
        # 순서
        order_item = QTableWidgetItem(str(row + 1))
        order_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 0, order_item)
        
        # 병원명
        name_item = QTableWidgetItem(hospital_name)
        name_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 1, name_item)
        
        # 전력량
        energy_item = QTableWidgetItem("0.00")
        energy_item.setFont(self.get_table_font())
        self.hospital_table.setItem(row, 2, energy_item)
        
        # 액션 버튼
        btn_layout = QHBoxLayout()
        
        delete_btn = QPushButton("🗑️ 삭제")
        delete_btn.setFont(self.get_table_font())
        delete_btn.clicked.connect(lambda: self.delete_hospital(hospital_name, row))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
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
        
        # ✨ 중복 방지
        if len(self.hospital_monitors) > 0:
            self.add_log("⚠️ 이미 로드된 병원이 있습니다. 건너뜁니다.")
            return
        
        # ✨ DB가 비어있으면
        if len(hospitals) == 0:
            self.add_log("📝 DB가 비어있습니다. UI에서 병원을 추가해주세요.")
            return
        
        # 각 병원 모니터 생성
        for hospital in hospitals:
            
            # 중복 체크
            if hospital['hospital_name'] in self.hospital_monitors:
                self.add_log(f"⚠️ {hospital['hospital_name']}은 이미 로드되었습니다.")
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
            
            if monitor and monitor.latest_energy is not None:
                energy_item = QTableWidgetItem(f"{monitor.latest_energy:.2f}")
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


# ============================================================
# 메인 실행
# ============================================================

def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🏥 병원 전력량 모니터링 시스템 v1.0")
    print("="*60)
    print("📅 시작 시간:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60 + "\n")
    
    USE_DUMMY_MODE = True
    
    if USE_DUMMY_MODE:
        print("🔌 더미 모드 실행 중... (가상 데이터)\n")
    else:
        print("📡 실제 모드 실행 중... (HMI 통신)\n")
    
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(200, 220, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    window = MainWindow(use_dummy=USE_DUMMY_MODE)
    window.show()
    
    print("✅ 프로그램 실행 완료!")
    print("="*60 + "\n")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()