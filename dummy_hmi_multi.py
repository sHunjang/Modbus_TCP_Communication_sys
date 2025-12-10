#!/usr/bin/env python3
# dummy_hmi_custom.py

"""
HMI 더미 클라이언트 (커스텀)

사용자가 병원명, 간격, 전력량 등을 직접 설정
"""

import socket
import time
import random
from datetime import datetime


def send_single_data(hospital: str, power: float, server_host: str, server_port: int):
    """
    한 번만 데이터 전송
    
    Args:
        hospital: 병원명 (3자리)
        power: 전력량 (kWh)
        server_host: 서버 IP
        server_port: 서버 포트
    """
    # 데이터 생성
    hospital = hospital[:3].upper()
    power_int = int(power * 100)
    power_str = str(power_int).zfill(10)
    data = f"{hospital}{power_str}"
    
    print(f"\n📤 전송 데이터: {data}")
    print(f"   병원: {hospital}")
    print(f"   전력량: {power:,.2f} kWh")
    print(f"   서버: {server_host}:{server_port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((server_host, server_port))
        sock.sendall(data.encode('ascii'))
        
        try:
            response = sock.recv(1024).decode('ascii').strip()
            print(f"   응답: {response}")
        except:
            print(f"   응답: (없음)")
        
        sock.close()
        print("✅ 전송 성공")
        return True
        
    except Exception as e:
        print(f"❌ 전송 실패: {e}")
        return False


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🏥 HMI 더미 클라이언트 (커스텀)")
    print("="*60 + "\n")
    
    # 사용자 입력
    hospital = input("병원명 (3자리, 예: ICN): ").strip() or "ICN"
    
    try:
        power = float(input("전력량 (kWh, 예: 6543.21): ").strip() or "6543.21")
    except:
        power = 6543.21
    
    server_host = input("서버 IP (기본: 127.0.0.1): ").strip() or "127.0.0.1"
    
    try:
        server_port = int(input("서버 포트 (기본: 23000): ").strip() or "23000")
    except:
        server_port = 23000
    
    # 전송
    send_single_data(hospital, power, server_host, server_port)
    
    # 연속 전송 옵션
    continuous = input("\n계속 전송하시겠습니까? (y/n): ").strip().lower()
    
    if continuous == 'y':
        try:
            interval = int(input("전송 간격 (초, 기본: 10): ").strip() or "10")
        except:
            interval = 3
        
        print(f"\n🚀 {interval}초마다 자동 전송 시작...\n")
        
        try:
            while True:
                # 전력량 증가
                power += random.uniform(1.0, 5.0)
                send_single_data(hospital, power, server_host, server_port)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 사용자에 의해 중지됨")


if __name__ == "__main__":
    main()
