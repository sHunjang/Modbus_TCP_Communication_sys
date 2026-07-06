#!/usr/bin/env python3
# central_monitor.py

"""
중앙 모니터링 시스템 v1.5 (통합 버전)

기능:
- TCP 서버 (포트 23000): HMI 데이터 수신
- 통신 모니터: 타임아웃 감지
- Flask 웹 서버 (포트 20000): 원격 접속용 대시보드
- PyQt UI: 로컬 관리자 화면

[v1.5 변경사항]
- (구조) /api/* 라우트를 core/web_routes.py 공통 Blueprint로 이전.
  web_dashboard.py와 중복되던 코드 제거. 이 파일에는 TCP 서버와
  web_logs를 쓰는 /api/logs만 남긴다.
"""

import sys
import os

# [배포 수정] 두 가지 문제를 한 번에 방어한다.
# 1) console=False(창 없음) 빌드에서 sys.stdout/stderr가 None이 되는 문제
# 2) 한글 Windows 콘솔 기본 인코딩(cp949)이 이모지(✅⚠️❌ 등)를 인코딩 못 해
#    print() 호출 시 UnicodeEncodeError로 크래시하는 문제
# → stdout/stderr를 UTF-8로 강제 재설정(콘솔 있는 경우) 또는 UTF-8 devnull로 대체(없는 경우)
def _safe_stream(stream):
    if stream is None:
        return open(os.devnull, "w", encoding="utf-8", errors="replace")
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    except Exception:
        return open(os.devnull, "w", encoding="utf-8", errors="replace")

sys.stdout = _safe_stream(sys.stdout)
sys.stderr = _safe_stream(sys.stderr)

import re
import socket
import threading
import time
import json
# import secrets
from collections import deque
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from flask import Flask, jsonify
from flask_cors import CORS

from core.database import DatabaseManager
from core.web_routes import dashboard_bp
from UI.main_window import CentralMainWindow
from UI.styles import UIStyles

# ==================== 전역 설정 ====================
TCP_PORT = 23000
WEB_PORT = 20000
TIMEOUT_SECONDS = 3
DB_SAVE_INTERVAL = 5
TCP_RESTART_BASE_DELAY = 5     # TCP 서버 재시작 시도 간격 (초, 초기값)
TCP_RESTART_MAX_DELAY = 60     # 재시작 간격 최대치 (반복 실패 시 이 값까지 2배씩 증가)

HMI_DATA_PATTERN = re.compile(r'^[A-Z]{3}\d{10}$')
HMI_DATA_LENGTH = 13

# [신규] DB 끊김 중 데이터 유실 방지용 로컬 버퍼
def _get_base_path():
    """exe 옆 폴더(배포 환경) 또는 스크립트 위치(개발 환경)를 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BUFFER_DIR = os.path.join(_get_base_path(), "buffer")
BUFFER_FILE = os.path.join(BUFFER_DIR, "pending_data.jsonl")
MAX_BUFFER_LINES = 50000   # 이 이상 쌓이면 새 데이터는 버림 (디스크 무한 증가 방지)
buffer_lock = threading.Lock()

# API_KEY = os.environ.get("DASHBOARD_API_KEY")
# if not API_KEY:
#     API_KEY = secrets.token_hex(16)
#     print("⚠️  DASHBOARD_API_KEY 환경변수가 설정되지 않아 임시 API 키를 생성했습니다.")
#     print(f"⚠️  임시 API 키: {API_KEY}")
#     print("⚠️  운영 환경에서는 반드시 환경변수로 고정 키를 지정하세요 (재시작마다 값이 바뀝니다).")

# 공유 데이터
hospital_data = {}
data_lock = threading.Lock()

hospital_status = {}
status_lock = threading.Lock()

last_db_save = {}
save_time_lock = threading.Lock()

log_messages = []
log_lock = threading.Lock()

web_logs = deque(maxlen=100)
web_log_lock = threading.Lock()

db = None


# ==================== Flask 웹 앱 ====================
web_app = Flask(__name__)
CORS(web_app)
web_app.register_blueprint(dashboard_bp)


def append_to_buffer(record: dict):
    """
    DB 저장 실패 시 데이터를 로컬 파일에 임시 저장한다.
    JSON Lines 형식(줄마다 레코드 하나)이라, 파일 읽기 중간에 프로그램이
    죽어도 이미 기록된 줄까지는 안전하게 보존된다.
    """
    with buffer_lock:
        try:
            os.makedirs(BUFFER_DIR, exist_ok=True)

            if os.path.exists(BUFFER_FILE):
                with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                    line_count = sum(1 for _ in f)
                if line_count >= MAX_BUFFER_LINES:
                    log(f"⚠️ 버퍼 파일이 최대 용량({MAX_BUFFER_LINES}건)에 도달하여 이 데이터는 유실됩니다.")
                    return

            with open(BUFFER_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            log(f"❌ 버퍼 파일 기록 오류: {e}")


def flush_buffer(db_instance):
    """
    DatabaseManager의 on_reconnect 콜백으로 등록되어, DB 재연결 성공 시 호출된다.
    버퍼 파일에 쌓인 데이터를 순서대로 다시 DB에 저장한다.

    재전송 도중 다시 DB가 끊기는 등 실패가 나면, 그 지점부터 남은 레코드를
    파일에 그대로 남겨두고 중단한다 (다음 재연결 때 이어서 처리됨).
    """
    with buffer_lock:
        if not os.path.exists(BUFFER_FILE):
            return

        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            log(f"❌ 버퍼 파일 읽기 오류: {e}")
            return

        if not lines:
            return

        log(f"🔄 버퍼에 저장된 {len(lines)}건의 데이터를 DB로 재전송합니다...")

        registered_hospitals = set()
        remaining_lines = []
        flushed_count = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log(f"⚠️ 버퍼 파일의 손상된 줄을 건너뜁니다: {line[:50]}...")
                continue

            hospital_key = record.get("hospital_key")

            if hospital_key not in registered_hospitals:
                db_instance.register_hospital(
                    hospital_key, record.get("ip", ""), record.get("port", 0)
                )
                registered_hospitals.add(hospital_key)

            success = db_instance.insert_data(
                hospital_key=hospital_key,
                timestamp=record.get("timestamp"),
                value=record.get("value"),
                hex_data=record.get("hex_data"),
            )

            if success:
                flushed_count += 1
            else:
                remaining_lines = lines[i:]
                log(f"⚠️ 버퍼 재전송 도중 DB 오류 발생 — {len(remaining_lines)}건은 다음 기회에 재시도합니다.")
                break

        try:
            if remaining_lines:
                with open(BUFFER_FILE, "w", encoding="utf-8") as f:
                    f.writelines(remaining_lines)
            else:
                os.remove(BUFFER_FILE)
        except Exception as e:
            log(f"❌ 버퍼 파일 정리 오류: {e}")

        log(f"✅ 버퍼 재전송 완료: {flushed_count}건 저장, {len(remaining_lines)}건 남음")


# ==================== 데이터 파싱 ====================
def parse_hmi_data(data: bytes) -> tuple:
    hex_str = ' '.join(f'{b:02X}' for b in data)

    if len(data) != HMI_DATA_LENGTH:
        log(f"⛔ 포맷 거부 — 길이 불일치: {len(data)}바이트 (기대: {HMI_DATA_LENGTH}) | HEX: {hex_str}")
        return None, None, hex_str

    try:
        full_str = data.decode('ascii')
    except UnicodeDecodeError:
        log(f"⛔ 포맷 거부 — ASCII 비ASCII 문자 포함 | HEX: {hex_str}")
        return None, None, hex_str

    if not HMI_DATA_PATTERN.match(full_str):
        log(f"⛔ 포맷 거부 — 패턴 불일치: '{full_str}' (기대: [A-Z]{{3}}\\d{{10}})")
        return None, None, hex_str

    hospital_name = full_str[0:3]
    power_digits = full_str[3:]
    integer_part = power_digits[:-2].lstrip('0') or "0"
    decimal_part = power_digits[-2:]
    power_value = float(f"{integer_part}.{decimal_part}")

    return hospital_name, power_value, hex_str


# ==================== TCP 서버 ====================
def handle_client(conn, addr):
    ip, port = addr
    client_key = f"{ip}:{port}"
    buffer = b""   # [버그 수정] 여러 메시지가 하나의 recv에 뭉쳐 들어오는 경우를 대비한 버퍼

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            buffer += data

            # [버그 수정] 버퍼에 13바이트 이상 쌓일 때마다 13바이트씩 정확히 잘라서 처리.
            # 기존에는 recv()로 받은 바이트 뭉치를 검증 없이 통째로 넘겨서,
            # 두 메시지가 짧은 시간차로 도착해 하나로 뭉쳐 들어오면(예: 26바이트)
            # 그대로 DB에 잘못된 값이 저장되는 문제가 있었다.
            while len(buffer) >= HMI_DATA_LENGTH:
                chunk = buffer[:HMI_DATA_LENGTH]
                buffer = buffer[HMI_DATA_LENGTH:]

                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                print(f"[HEX {client_key}] {hex_str}")

                hospital_name, power_value, _ = parse_hmi_data(chunk)

                if hospital_name is None or power_value is None:
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
                    hospital_status[hospital_name] = {
                        "last_received": current_time,
                        "alerted": False
                    }
                else:
                    was_alerted = hospital_status[hospital_name]["alerted"]
                    hospital_status[hospital_name]["last_received"] = current_time
                    hospital_status[hospital_name]["alerted"] = False
                    if was_alerted:
                        log(f"✅ [{hospital_name}] 통신 복구됨")

            should_save = False
            with save_time_lock:
                if hospital_name not in last_db_save:
                    should_save = True
                    last_db_save[hospital_name] = current_time
                else:
                    elapsed = (current_time - last_db_save[hospital_name]).total_seconds()
                    if elapsed >= DB_SAVE_INTERVAL:
                        should_save = True
                        last_db_save[hospital_name] = current_time

            if should_save:
                if db and db.db_available:
                    db.register_hospital(hospital_name, ip, port)
                    success = db.insert_data(
                        hospital_key=hospital_name,
                        timestamp=current_time_str,
                        value=power_value,
                        hex_data=hex_str
                    )
                    if success:
                        log(f"💾 [{hospital_name}] {power_value:,.2f} kWh → DB 저장")

                        with web_log_lock:
                            web_logs.append({
                                "timestamp": current_time_str,
                                "hospital": hospital_name,
                                "value": f"{power_value:,.2f}",
                                "message": f"[{hospital_name}] {power_value:,.2f} kWh"
                            })
                    else:
                        # [신규] db_available이 True였는데도 insert가 실패한 경우
                        # (체크와 실제 실행 사이에 DB가 끊긴 경우 등) — 버퍼에 저장
                        append_to_buffer({
                            "hospital_key": hospital_name,
                            "ip": ip,
                            "port": port,
                            "timestamp": current_time_str,
                            "value": power_value,
                            "hex_data": hex_str,
                        })
                        log(f"⚠️ [{hospital_name}] DB 저장 실패 → 로컬 버퍼에 임시 저장")
                else:
                    # [신규] DB 자체가 끊긴 상태 — 바로 버퍼에 저장
                    append_to_buffer({
                        "hospital_key": hospital_name,
                        "ip": ip,
                        "port": port,
                        "timestamp": current_time_str,
                        "value": power_value,
                        "hex_data": hex_str,
                    })
                    log(f"⚠️ [{hospital_name}] DB 연결 끊김 → 로컬 버퍼에 임시 저장")

            try:
                conn.sendall(b"OK\n")
            except Exception:
                pass

    except ConnectionResetError:
        log(f"[오류] {client_key} 연결 끊김")
    except Exception as e:
        log(f"[오류] {client_key} 예외: {e}")
    finally:
        conn.close()


def start_server():
    """
    TCP 서버 실행.

    [신규] 기존에는 bind() 실패나 accept() 도중 예외가 나면 이 스레드가
    조용히 종료되어, HMI가 아무리 재접속을 시도해도 서버가 영원히 응답하지
    않는 상태가 됐다. 바깥쪽에 무한 재시도 루프를 씌워서, 어떤 이유로든
    서버가 죽으면 지수 백오프(5초 → 10초 → ... → 최대 60초) 간격으로
    스스로 재시작을 시도하도록 수정했다.
    """
    restart_delay = TCP_RESTART_BASE_DELAY

    while True:
        server = None
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", TCP_PORT))
            server.listen(20)
            log(f"✅ TCP 서버 시작 - 포트 {TCP_PORT}")

            # [신규] 정상적으로 bind+listen까지 성공했으므로 백오프를 초기화한다.
            # (실패가 반복되다가 한 번 성공하면, 다음에 또 실패하더라도
            #  누적된 지연 시간을 이어받지 않고 5초부터 다시 시작해야 함)
            restart_delay = TCP_RESTART_BASE_DELAY

            while True:
                conn, addr = server.accept()
                threading.Thread(
                    target=handle_client, args=(conn, addr), daemon=True
                ).start()

        except Exception as e:
            log(f"❌ TCP 서버 오류: {e}")
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass

        log(f"🔄 {restart_delay}초 후 TCP 서버 재시작을 시도합니다...")
        time.sleep(restart_delay)
        restart_delay = min(restart_delay * 2, TCP_RESTART_MAX_DELAY)


def monitor_communication():
    log("✅ 통신 모니터 시작")

    while True:
        try:
            current_time = datetime.now()

            with status_lock:
                for hospital_name, status in list(hospital_status.items()):
                    elapsed = (current_time - status["last_received"]).total_seconds()

                    if elapsed > TIMEOUT_SECONDS and not status["alerted"]:
                        log(f"⚠️⚠️⚠️ [{hospital_name}] 통신 두절! (마지막 수신: {int(elapsed)}초 전)")
                        hospital_status[hospital_name]["alerted"] = True

                        alert_msg = (
                            f"병원: {hospital_name}\n"
                            f"상태: 통신 두절\n"
                            f"마지막 수신: {int(elapsed)}초 전"
                        )
                        with log_lock:
                            log_messages.append(f"ALERT:{alert_msg}")

            time.sleep(5)
        except Exception as e:
            log(f"❌ 통신 모니터 오류: {e}")
            time.sleep(5)


def start_web_server():
    log(f"✅ Waitress 웹 서버 시작 - 포트 {WEB_PORT}")

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
    print("🏥 중앙 모니터링 시스템 v1.5 (통합 버전)")
    print("=" * 70)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"TCP 포트:  {TCP_PORT} (HMI 데이터 수신)")
    print(f"WEB 포트:  {WEB_PORT} (원격 대시보드)")
    print(f"타임아웃:  {TIMEOUT_SECONDS}초")
    print(f"HMI 포맷:  [A-Z]{{3}}\\d{{10}} (총 {HMI_DATA_LENGTH}바이트)")
    print("=" * 70 + "\n")

    db = DatabaseManager(on_reconnect=flush_buffer)
    web_app.config["DB"] = db

    def get_web_logs():
        with web_log_lock:
            return list(web_logs)

    web_app.config["GET_LOGS_FUNC"] = get_web_logs

    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=monitor_communication, daemon=True).start()
    threading.Thread(target=start_web_server, daemon=True).start()

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()