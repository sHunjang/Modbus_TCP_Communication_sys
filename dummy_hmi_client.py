#!/usr/bin/env python3
# dummy_hmi_client.py

"""
HMI 더미 클라이언트 (단일 병원)

실제 HMI처럼 10초마다 전력량 데이터를 중앙 서버로 전송
"""

import socket
import time
import random
from datetime import datetime


class DummyHMI:
    """HMI 시뮬레이터"""
    
    def __init__(self, hospital_name: str, server_host: str, server_port: int):
        """
        Args:
            hospital_name: 병원명 (3자리, 예: ICN, SEL, BUS)
            server_host: 중앙 서버 IP
            server_port: 중앙 서버 포트
        """
        self.hospital_name = hospital_name[:3].upper()  # 3자리만
        self.server_host = server_host
        self.server_port = server_port
        
        # 초기 전력량 (kWh)
        self.current_power = random.uniform(5000.0, 10000.0)
        
        print(f"✅ HMI 시뮬레이터 시작")
        print(f"   병원명: {self.hospital_name}")
        print(f"   서버: {self.server_host}:{self.server_port}")
        print(f"   초기 전력량: {self.current_power:,.2f} kWh")
        print(f"{'='*60}\n")
    
    def generate_power_data(self) -> str:
        """
        전력량 데이터 생성
        
        Returns:
            str: ASCII 형식 데이터 (예: "ICN0000654321")
        """
        # 전력량 증가 (시간당 10~50 kWh 증가 시뮬레이션)
        increase = random.uniform(10.0, 50.0) / 360  # 10초당 증가량
        self.current_power += increase
        
        # 소수점 2자리를 정수로 변환 (6543.21 → 654321)
        power_int = int(self.current_power * 100)
        
        # 10자리로 패딩 (앞에 0 채움)
        power_str = str(power_int).zfill(10)
        
        # 병원명 + 전력량
        data = f"{self.hospital_name}{power_str}"
        
        return data
    
    def send_data(self):
        """중앙 서버로 데이터 전송"""
        data_str = self.generate_power_data()
        data_bytes = data_str.encode('ascii')
        
        try:
            # TCP 연결
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.server_host, self.server_port))
            
            # 데이터 전송
            sock.sendall(data_bytes)
            
            # 응답 대기 (선택)
            try:
                response = sock.recv(1024)
                response_str = response.decode('ascii').strip()
            except:
                response_str = "NO_RESPONSE"
            
            sock.close()
            
            # 로그
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 📤 전송: {data_str} ({self.current_power:,.2f} kWh) | 응답: {response_str}")
            
            return True
            
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] ❌ 전송 오류: {e}")
            return False
    
    def run(self, interval: int = 10):
        """
        지속적으로 데이터 전송
        
        Args:
            interval: 전송 간격 (초)
        """
        print(f"🚀 {interval}초마다 데이터 전송 시작...\n")
        
        try:
            while True:
                self.send_data()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 사용자에 의해 중지됨")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🏥 HMI 더미 클라이언트")
    print("="*60 + "\n")
    
    # 설정
    HOSPITAL_NAME = "TST"        # 병원명 (3자리)
    SERVER_HOST = "127.0.0.1"    # 중앙 서버 IP (로컬 테스트)
    SERVER_PORT = 23000          # 중앙 서버 포트
    INTERVAL = 3                # 전송 간격 (초)
    
    # HMI 시작
    hmi = DummyHMI(HOSPITAL_NAME, SERVER_HOST, SERVER_PORT)
    hmi.run(INTERVAL)


if __name__ == "__main__":
    main()
