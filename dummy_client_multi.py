#!/usr/bin/env python3
# dummy_client_multi.py

"""
여러 병원 더미 클라이언트 (동시 전송)
"""

import socket
import time
import random
import threading
from datetime import datetime


SERVER_HOST = "14.42.209.171"
SERVER_PORT = 23000
SEND_INTERVAL = 5

# 여러 병원 설정
HOSPITALS = [
    {"name": "ICN", "base": 6543.21},  # 인천
    {"name": "SEL", "base": 8765.43},  # 서울
    {"name": "BUS", "base": 5432.10},  # 부산
]


def generate_data(name: str, base: float) -> bytes:
    """데이터 생성"""
    name_bytes = name[:3].ljust(3, 'X').encode('ascii')
    separator = b'\x00\x00'
    
    variation = random.uniform(-0.05, 0.05)
    value = base * (1 + variation)
    value_int = int(value * 100)
    value_str = f"{value_int:010d}"
    value_bytes = value_str.encode('ascii')
    
    return name_bytes + separator + value_bytes


def send_hospital_data(hospital: dict):
    """병원별 전송 스레드"""
    name = hospital["name"]
    base = hospital["base"]
    
    print(f"🏥 [{name}] 시작")
    
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((SERVER_HOST, SERVER_PORT))
            
            data = generate_data(name, base)
            sock.sendall(data)
            
            value_str = data[5:15].decode('ascii')
            value = f"{int(value_str[:-2])}.{value_str[-2:]}"
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {name}: {value} kWh ✅")
            
            sock.close()
            time.sleep(SEND_INTERVAL)
            
            base += random.uniform(0.5, 2.0)
        
        except Exception as e:
            print(f"❌ [{name}] 오류: {e}")
            time.sleep(10)


def main():
    print("\n" + "=" * 60)
    print("🧪 다중 병원 더미 클라이언트")
    print("=" * 60)
    print(f"서버: {SERVER_HOST}:{SERVER_PORT}")
    print(f"병원 수: {len(HOSPITALS)}")
    print("=" * 60 + "\n")
    
    threads = []
    for hospital in HOSPITALS:
        t = threading.Thread(
            target=send_hospital_data,
            args=(hospital,),
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(1)  # 시작 시간 분산
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 프로그램 종료")


if __name__ == "__main__":
    main()
