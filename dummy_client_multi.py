#!/usr/bin/env python3
# dummy_client_multi.py

"""
HMI 더미 클라이언트 (다중 병원)

여러 병원을 동시에 시뮬레이션하여 중앙 서버 테스트
각 병원마다 별도 스레드에서 10초마다 데이터 전송
"""

import socket
import time
import random
import threading
from datetime import datetime


# ==================== 설정 ====================
SERVER_HOST = "127.0.0.1"      # 중앙 서버 IP
# SERVER_HOST = "14.42.209.171"  # 실제 서버
SERVER_PORT = 23000            # 중앙 서버 포트
SEND_INTERVAL = 10             # 전송 간격 (초)

# 여러 병원 설정
HOSPITALS = [
    {"name": "ICN", "base": 7584.55},   # 인천
    {"name": "SEL", "base": 8765.43},   # 서울
    {"name": "BUS", "base": 5432.10},   # 부산
    {"name": "DAE", "base": 6789.22},   # 대전
]


# ==================== 데이터 생성 ====================
def generate_data(name: str, base: float) -> bytes:
    """
    더미 데이터 생성
    
    Args:
        name: 병원명 (3자리)
        base: 기준 전력량
    
    Returns:
        bytes: ASCII 인코딩된 데이터
    """
    name_part = name[:3].ljust(3, 'X')
    
    # 랜덤 변동
    variation = random.uniform(-0.05, 0.05)
    value = base * (1 + variation)
    value_int = int(value * 100)
    value_str = f"{value_int:08d}"
    
    data_str = name_part + value_str
    return data_str.encode('ascii')


# ==================== 병원별 전송 스레드 ====================
def send_hospital_data(hospital: dict):
    """
    병원별 전송 스레드
    
    각 병원이 독립적으로 10초마다 데이터 전송
    
    Args:
        hospital: {"name": str, "base": float}
    """
    name = hospital["name"]
    base = hospital["base"]
    
    print(f"🏥 [{name}] 스레드 시작")
    
    while True:
        try:
            # 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            # 접속
            sock.connect((SERVER_HOST, SERVER_PORT))
            
            # 데이터 생성 및 전송
            data = generate_data(name, base)
            sock.sendall(data)
            
            # 파싱 정보 표시
            ascii_str = data.decode('ascii')
            value_str = ascii_str[3:]
            value = f"{int(value_str[:-2])}.{value_str[-2:]}"
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {name}: {value} kWh ✅")
            
            # 응답 수신 (선택)
            try:
                sock.settimeout(1.0)
                response = sock.recv(1024)
            except:
                pass
            
            sock.close()
            
            # 대기
            time.sleep(SEND_INTERVAL)
            
            # 전력량 증가
            base += random.uniform(0.1, 1.0)
        
        except ConnectionRefusedError:
            print(f"❌ [{name}] 연결 거부")
            time.sleep(10)
        
        except Exception as e:
            print(f"❌ [{name}] 오류: {e}")
            time.sleep(10)


# ==================== 메인 ====================
def main():
    """메인 함수 - 여러 병원 스레드 시작"""
    print("\n" + "=" * 60)
    print("🧪 다중 병원 더미 클라이언트")
    print("=" * 60)
    print(f"서버: {SERVER_HOST}:{SERVER_PORT}")
    print(f"병원 수: {len(HOSPITALS)}")
    print(f"전송 간격: {SEND_INTERVAL}초")
    print("=" * 60 + "\n")
    
    # 각 병원마다 스레드 생성
    threads = []
    for hospital in HOSPITALS:
        t = threading.Thread(
            target=send_hospital_data,
            args=(hospital,),
            daemon=True
        )
        t.start()
        threads.append(t)
        
        # 시작 시간 분산 (1초 간격)
        time.sleep(1)
    
    print(f"\n✅ {len(HOSPITALS)}개 병원 스레드 실행 중...")
    print("종료하려면 Ctrl+C\n")
    
    try:
        # 메인 스레드 유지
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 프로그램 종료")


if __name__ == "__main__":
    main()
