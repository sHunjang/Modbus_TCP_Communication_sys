#!/usr/bin/env python3
# central_monitor.py

"""
중앙 모니터링 시스템 v1.2 (통합 버전)

기능:
- TCP 서버 (포트 23000): HMI 데이터 수신
- 통신 모니터: 타임아웃 감지
- Flask 웹 서버 (포트 20000): 원격 접속용 대시보드
- PyQt UI: 로컬 관리자 화면
"""

import sys
import socket
import threading
import time
import os
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS

from core.database import DatabaseManager
from core.csv_exporter import CSVExporter
from UI.main_window import CentralMainWindow
from UI.styles import UIStyles


# ==================== 전역 설정 ====================
TCP_PORT = 23000
WEB_PORT = 20000
TIMEOUT_SECONDS = 30

# 공유 데이터
hospital_data = {}
data_lock = threading.Lock()

hospital_status = {}
status_lock = threading.Lock()

log_messages = []
log_lock = threading.Lock()

db = None


# ==================== Flask 웹 앱 ====================
web_app = Flask(__name__)
CORS(web_app)

@web_app.route('/')
def index():
    return render_template('dashboard.html')

@web_app.route('/api/hospitals')
def get_hospitals_api():
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    return jsonify(db.get_hospitals())

@web_app.route('/api/latest_data')
def get_latest_data():
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    hospitals = db.get_hospitals()
    result = {}
    
    for hospital in hospitals:
        hospital_key = hospital['hospital_key']
        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            query = f"SELECT timestamp, value FROM {table_name} ORDER BY timestamp DESC LIMIT 1"
            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()
            db.release_connection(conn)
            
            if row:
                result[hospital_key] = {
                    "value": float(row[1]),
                    "timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": hospital.get('ip_address', ''),
                    "port": hospital.get('port', 0)
                }
        except Exception as e:
            print(f"❌ {hospital_key} 데이터 조회 오류: {e}")
    
    return jsonify(result)

@web_app.route('/api/status')
def get_status():
    return jsonify({
        "db_connected": db.db_available,
        "hospital_count": len(db.get_hospitals()) if db.db_available else 0,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@web_app.route('/api/export_csv/<hospital_key>')
def export_csv(hospital_key):
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    
    if not start_time or not end_time:
        return jsonify({"error": "시작/종료 시간이 필요합니다"}), 400
    
    try:
        start_dt = datetime.fromisoformat(start_time.replace('T', ' ').replace('Z', ''))
        end_dt = datetime.fromisoformat(end_time.replace('T', ' ').replace('Z', ''))
    except Exception as e:
        return jsonify({"error": f"시간 형식 오류: {e}"}), 400
    
    exporter = CSVExporter()
    success, filepath, message = exporter.export_hospital_data(db, hospital_key, start_dt, end_dt)
    
    if not success:
        return jsonify({"error": message}), 500
    
    return send_file(filepath, mimetype='text/csv', as_attachment=True, download_name=os.path.basename(filepath))


# ==================== 데이터 파싱 ====================
def parse_hmi_data(data: bytes) -> tuple:
    hex_str = ' '.join(f'{b:02X}' for b in data)
    
    try:
        if len(data) < 3:
            log(f"⚠️ 데이터 길이 부족: {len(data)}바이트")
            return None, None, hex_str
        
        try:
            full_str = data.decode('ascii', errors='strict')
        except:
            log(f"⚠️ ASCII 디코딩 실패")
            return None, None, hex_str
        
        hospital_name = full_str[0:3]
        power_str = full_str[3:].strip()
        power_digits = ''.join(c for c in power_str if c.isdigit())
        
        if len(power_digits) < 2:
            log(f"⚠️ 전력량 데이터 부족: {power_str}")
            return None, None, hex_str
        
        integer_part = power_digits[:-2] or "0"
        decimal_part = power_digits[-2:]
        power_value = float(f"{integer_part}.{decimal_part}")
        
        return hospital_name, power_value, hex_str
    
    except Exception as e:
        log(f"❌ 파싱 오류: {e}")
        return None, None, hex_str


# ==================== TCP 서버 ====================
def handle_client(conn, addr):
    ip, port = addr
    client_key = f"{ip}:{port}"
    log(f"[접속] {client_key}")

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            hospital_name, power_value, hex_str = parse_hmi_data(data)
            log(f"[HEX {client_key}] {hex_str}")
            
            if hospital_name is None or power_value is None:
                log(f"⚠️ {client_key} 파싱 실패")
                continue
            
            current_time = datetime.now()
            current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            with data_lock:
                hospital_data[hospital_name] = {
                    "value": f"{power_value:,.2f}",
                    "ip": ip,
                    "port": port,
                    "hex": hex_str,
                    "last_time": current_time_str,
                }
            
            with status_lock:
                if hospital_name not in hospital_status:
                    hospital_status[hospital_name] = {"last_received": current_time, "alerted": False}
                else:
                    was_alerted = hospital_status[hospital_name]["alerted"]
                    hospital_status[hospital_name]["last_received"] = current_time
                    hospital_status[hospital_name]["alerted"] = False
                    if was_alerted:
                        log(f"✅ [{hospital_name}] 통신 복구됨")
            
            if db and db.db_available:
                db.register_hospital(hospital_name, ip, port)
                db.insert_data(hospital_key=hospital_name, timestamp=current_time_str, value=power_value, hex_data=hex_str)
            
            log(f"[{hospital_name}] {power_value:,.2f} kWh → DB 저장")
            
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
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(("0.0.0.0", TCP_PORT))
        server.listen(10)
        log(f"✅ TCP 서버 시작 - 포트 {TCP_PORT}")
    except OSError as e:
        log(f"❌ 서버 시작 실패: {e}")
        return

    while True:
        try:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
        except Exception as e:
            log(f"❌ Accept 오류: {e}")
            break


def monitor_communication():
    log("✅ 통신 모니터 시작")
    
    while True:
        try:
            current_time = datetime.now()
            
            with status_lock:
                for hospital_name, status in list(hospital_status.items()):
                    last_received = status["last_received"]
                    alerted = status["alerted"]
                    elapsed = (current_time - last_received).total_seconds()
                    
                    if elapsed > TIMEOUT_SECONDS and not alerted:
                        log(f"⚠️⚠️⚠️ [{hospital_name}] 통신 두절! (마지막 수신: {int(elapsed)}초 전)")
                        hospital_status[hospital_name]["alerted"] = True
                        
                        alert_msg = f"병원: {hospital_name}\n상태: 통신 두절\n마지막 수신: {int(elapsed)}초 전"
                        with log_lock:
                            log_messages.append(f"ALERT:{alert_msg}")
            
            time.sleep(5)
        except Exception as e:
            log(f"❌ 통신 모니터 오류: {e}")
            time.sleep(5)


def start_web_server():
    log(f"✅ 웹 서버 시작 - 포트 {WEB_PORT}")
    log(f"   로컬 접속: http://192.168.0.13:{WEB_PORT}")
    log(f"   외부 접속: http://Soluwins IP 주소:{WEB_PORT}")
    
    from waitress import serve
    serve(web_app, host='0.0.0.0', port=WEB_PORT, threads=4)


def log(message):
    with log_lock:
        log_messages.append(message)
    print(message)


# ==================== 메인 ====================
def main():
    global db

    print("\n" + "=" * 70)
    print("🏥 중앙 모니터링 시스템 v1.2 (통합 버전)")
    print("=" * 70)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"TCP 포트: {TCP_PORT} (HMI 데이터 수신)")
    print(f"WEB 포트: {WEB_PORT} (원격 대시보드)")
    print(f"타임아웃: {TIMEOUT_SECONDS}초")
    print("=" * 70 + "\n")

    db = DatabaseManager()

    # 스레드 시작
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=monitor_communication, daemon=True).start()
    threading.Thread(target=start_web_server, daemon=True).start()

    # PyQt UI
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(UIStyles.get_palette())

    window = CentralMainWindow(
        hospital_data=hospital_data,
        data_lock=data_lock,
        hospital_status=hospital_status,
        status_lock=status_lock,
        log_messages=log_messages,
        log_lock=log_lock,
        db=db,
        tcp_port=TCP_PORT,
        web_port=WEB_PORT,
        timeout_seconds=TIMEOUT_SECONDS
    )
    window.show()

    print("✅ 프로그램 실행 완료!\n")
    print(f"원격 접속: http://Soluwins IP 주소:{WEB_PORT}\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
