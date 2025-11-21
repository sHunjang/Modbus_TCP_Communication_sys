#!/usr/bin/env python3
# central_monitor.py

"""
중앙 모니터링 시스템 v1.0

HMI 직접 전송 방식:
- HMI: 10초마다 데이터 전송 (포맷: [병원명3자리][00][00][전력량10자리])
- 서버: TCP 23000 포트 Listen
- UI: 실시간 표시 (10초 갱신)
- DB: PostgreSQL에 10초 단위 저장
"""

import sys
import socket
import threading
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QPlainTextEdit, QGroupBox, QMessageBox,
    QDialog, QComboBox, QDateTimeEdit
)
from PyQt6.QtCore import QTimer, Qt, QDateTime
from PyQt6.QtGui import QFont, QColor, QPalette

from core.database import DatabaseManager
from core.csv_exporter import CSVExporter
from UI.styles import UIStyles


# ==================== 전역 설정 ====================
HOST = "0.0.0.0"  # 모든 IP에서 접속 허용
PORT = 23000      # 서버 포트 (포트포워딩 필요)

# UI용 최신 데이터 (병원명 → 데이터)
hospital_data = {}
data_lock = threading.Lock()

# 로그 메시지 큐
log_messages = []
log_lock = threading.Lock()

# DB 인스턴스 (전역)
db = None


# ==================== 데이터 파싱 ====================
def parse_hmi_data(data: bytes) -> tuple:
    """
    HMI 데이터 파싱 (유연한 포맷)
    
    포맷 1: [병원명3자리][00][00][전력량10자리] (바이너리 구분자)
    포맷 2: [병원명3자리][전력량 가변] (ASCII 전체)
    
    Args:
        data: HMI에서 받은 바이트 데이터
    
    Returns:
        (hospital_name: str, power_value: float, hex_str: str)
    """
    hex_str = ' '.join(f'{b:02X}' for b in data)
    
    try:
        # 최소 길이 체크 (병원명 3자리 이상)
        if len(data) < 3:
            log(f"⚠️ 데이터 길이 부족: {len(data)}바이트")
            return None, None, hex_str
        
        # 전체를 ASCII로 디코드 시도
        try:
            full_str = data.decode('ascii', errors='strict')
        except:
            log(f"⚠️ ASCII 디코딩 실패")
            return None, None, hex_str
        
        # 1. 병원명 (처음 3자리)
        hospital_name = full_str[0:3]
        
        # 2. 나머지를 전력량으로 처리
        power_str = full_str[3:].strip()
        
        # 숫자만 추출
        power_digits = ''.join(c for c in power_str if c.isdigit())
        
        if len(power_digits) < 2:
            log(f"⚠️ 전력량 데이터 부족: {power_str}")
            return None, None, hex_str
        
        # 마지막 2자리를 소수점으로 처리
        if len(power_digits) >= 2:
            integer_part = power_digits[:-2] or "0"
            decimal_part = power_digits[-2:]
        else:
            integer_part = "0"
            decimal_part = power_digits.ljust(2, '0')
        
        power_value = float(f"{integer_part}.{decimal_part}")
        
        log(f"✅ 파싱 성공 - 병원: {hospital_name}, 전력: {power_value}")
        
        return hospital_name, power_value, hex_str
    
    except Exception as e:
        log(f"❌ 파싱 오류: {e}")
        return None, None, hex_str


# ==================== TCP 서버 ====================
def handle_client(conn, addr):
    """
    클라이언트(HMI) 처리
    
    - 데이터 수신
    - 파싱
    - UI 갱신 (메모리)
    - DB 저장
    """
    ip, port = addr
    client_key = f"{ip}:{port}"

    log(f"[접속] {client_key}")

    try:
        while True:
            # 데이터 수신 (최대 1024바이트)
            data = conn.recv(1024)
            if not data:
                # 클라이언트 연결 종료
                break

            # HMI 데이터 파싱
            hospital_name, power_value, hex_str = parse_hmi_data(data)
            
            # HEX 로그 (디버깅)
            log(f"[HEX {client_key}] {hex_str}")
            
            if hospital_name is None or power_value is None:
                log(f"⚠️ {client_key} 파싱 실패")
                continue
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # UI용 최신 데이터 저장 (메모리)
            with data_lock:
                hospital_data[hospital_name] = {
                    "value": f"{power_value:,.2f}",  # 천단위 콤마, 소수점 2자리
                    "ip": ip,
                    "port": port,
                    "hex": hex_str,
                    "last_time": current_time,
                }
            
            # DB에 병원 등록 (처음 접속 시 자동)
            if db and db.db_available:
                db.register_hospital(hospital_name, ip, port)
                
                # DB에 최신 데이터 저장 (10초마다)
                db.insert_data(
                    hospital_key=hospital_name,
                    timestamp=current_time,
                    value=power_value,
                    hex_data=hex_str
                )
            
            log(f"[{hospital_name}] {power_value:,.2f} kWh → DB 저장")
            
            # 수신 확인 응답 (선택)
            try:
                conn.sendall(b"OK\n")
            except:
                pass

    except ConnectionResetError:
        log(f"[오류] {client_key} 연결 끊김")
    except Exception as e:
        log(f"[오류] {client_key} 예외: {e}")
    finally:
        conn.close()
        log(f"[종료] {client_key}")


def start_server():
    """
    TCP 서버 시작 (별도 스레드에서 실행)
    
    - 0.0.0.0:23000 바인드
    - 클라이언트 accept
    - 각 클라이언트마다 스레드 생성
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(10)  # 최대 10개 대기
        log(f"✅ TCP 서버 시작 - 포트 {PORT}")
    except OSError as e:
        log(f"❌ 서버 시작 실패: {e}")
        return

    while True:
        try:
            conn, addr = server.accept()
            # 클라이언트마다 별도 스레드 생성
            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
            )
            thread.start()
        except Exception as e:
            log(f"❌ Accept 오류: {e}")
            break


def log(message):
    """
    로그 메시지 추가 (스레드 안전)
    
    Args:
        message: 로그 메시지
    """
    with log_lock:
        log_messages.append(message)
    print(message)  # 콘솔에도 출력


# ==================== PyQt UI ====================
class CentralMainWindow(QMainWindow):
    """중앙 모니터링 메인 윈도우"""

    def __init__(self):
        super().__init__()
        
        # CSV 내보내기 인스턴스
        self.exporter = CSVExporter()
        
        # UI 초기화
        self.init_ui()

        # UI 갱신 타이머 (1초마다)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

        # 시계 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("🏥 중앙 모니터링 시스템 v1.0 (251121)")
        self.setGeometry(100, 50, 1200, 750)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 상단 헤더
        header = QHBoxLayout()

        title = QLabel(f"🏥 중앙 모니터링 시스템 (포트 {PORT})")
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

        layout.addLayout(header)
        
        # 병원 테이블
        layout.addWidget(self.create_table(), stretch=3)
        
        # 로그
        layout.addWidget(self.create_log(), stretch=1)

        # 상태바
        db_status = "✅ DB 연결" if (db and db.db_available) else "⚠️ DB 끊김"
        self.statusBar().showMessage(f"서버 시작 | {db_status} | 10초 단위 저장")

    def create_table(self):
        """병원 테이블 생성"""
        group = QGroupBox("📊 실시간 전력량 (10초 갱신)")
        group.setStyleSheet(UIStyles.group_box_style())

        layout = QVBoxLayout()
        
        # CSV 내보내기 버튼
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("📥 CSV 내보내기")
        export_btn.setFont(QFont("", 11))
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005A9E; }
            QPushButton:pressed { background-color: #004578; }
        """)
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

    def update_display(self):
        """UI 갱신 (1초마다)"""
        # 로그 처리
        with log_lock:
            while log_messages:
                self.add_log_to_ui(log_messages.pop(0))

        # 테이블 갱신
        with data_lock:
            data_copy = dict(hospital_data)

        self.hospital_table.setRowCount(len(data_copy))

        for idx, (hospital_name, info) in enumerate(sorted(data_copy.items())):
            self.hospital_table.setRowHeight(idx, 40)

            # 순서
            order_item = QTableWidgetItem(str(idx + 1))
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hospital_table.setItem(idx, 0, order_item)

            # 병원명 (IP:포트)
            display_name = f"{hospital_name} ({info['ip']}:{info['port']})"
            name_item = QTableWidgetItem(display_name)
            self.hospital_table.setItem(idx, 1, name_item)

            # 전체 전력량
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

    def delete_hospital(self, hospital_name: str):
        """병원 삭제"""
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"{hospital_name}을(를) 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            with data_lock:
                hospital_data.pop(hospital_name, None)
            log(f"🗑️ {hospital_name} 삭제")

    def open_export_dialog(self):
        """CSV 내보내기 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("CSV 내보내기")
        dialog.setFixedSize(500, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 병원 선택
        layout.addWidget(QLabel("병원 선택:"))
        
        hospital_combo = QComboBox()
        with data_lock:
            hospital_list = list(hospital_data.keys())
        
        if not hospital_list:
            QMessageBox.warning(self, "경고", "등록된 병원이 없습니다.")
            return
        
        hospital_combo.addItems(hospital_list)
        layout.addWidget(hospital_combo)
        
        # 시작 시간
        layout.addWidget(QLabel("시작 시간:"))
        start_datetime = QDateTimeEdit()
        start_datetime.setCalendarPopup(True)
        start_datetime.setDateTime(QDateTime.currentDateTime().addDays(-1))
        start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(start_datetime)
        
        # 종료 시간
        layout.addWidget(QLabel("종료 시간:"))
        end_datetime = QDateTimeEdit()
        end_datetime.setCalendarPopup(True)
        end_datetime.setDateTime(QDateTime.currentDateTime())
        end_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(end_datetime)
        
        # 버튼
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
            db,
            hospital_name,
            start_dt,
            end_dt
        )
        
        dialog.accept()
        
        if success:
            reply = QMessageBox.question(
                self,
                "내보내기 완료",
                f"{message}\n\n파일: {filepath}\n\n폴더를 여시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                import os
                import subprocess
                import platform
                
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

    def closeEvent(self, event):
        """종료 처리"""
        reply = QMessageBox.question(
            self, "종료 확인", "종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if db:
                db.close()
            event.accept()
        else:
            event.ignore()


# ==================== 메인 ====================
def main():
    """메인 함수"""
    global db

    print("\n" + "=" * 70)
    print("🏥 중앙 모니터링 시스템 v1.0")
    print("=" * 70)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"서버 포트: {PORT}")
    print("데이터: 10초 수신 → UI 갱신 + DB 저장")
    print("=" * 70 + "\n")

    # DB 초기화
    db = DatabaseManager()

    # TCP 서버 시작 (백그라운드 스레드)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # PyQt 애플리케이션 실행
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(UIStyles.get_palette())

    window = CentralMainWindow()
    window.show()

    print("✅ 프로그램 실행 완료!\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
