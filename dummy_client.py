#!/usr/bin/env python3
# dummy_client.py

"""
HMI 더미 클라이언트 (테스트용)

중앙 서버(14.42.209.171:23000)에 더미 데이터 전송
포맷: [병원명3자리][00][00][전력량10자리]
"""

import socket
import time
import random
from datetime import datetime


# ==================== 설정 ====================
SERVER_HOST = "14.42.209.171"  # 중앙 서버 IP
SERVER_PORT = 23000            # 중앙 서버 포트

HOSPITAL_NAME = "ICN"          # 병원명 3자리 (예: ICN, SEL, BUS)
SEND_INTERVAL = 5              # 전송 간격 (초)


# ==================== 더미 데이터 생성 ====================
def generate_dummy_data(hospital_name: str, base_value: float = 6543.21) -> bytes:
    """
    HMI 포맷에 맞는 더미 데이터 생성
    
    포맷: [병원명3자리][00][00][전력량10자리]
    
    Args:
        hospital_name: 병원명 (3자리)
        base_value: 기준 전력량 (소수점 포함)
    
    Returns:
        bytes: 전송할 바이트 데이터
    """
    # 1. 병원명 (3바이트, ASCII)
    name_bytes = hospital_name[:3].ljust(3, 'X').encode('ascii')
    
    # 2. 구분자 (2바이트)
    separator = b'\x00\x00'
    
    # 3. 전력량 (10자리, 마지막 2자리는 소수점)
    # 예: 6543.21 → "0000654321"
    # 랜덤 변동 추가 (±5%)
    variation = random.uniform(-0.05, 0.05)
    value = base_value * (1 + variation)
    
    # 소수점 제거 후 10자리로 포맷
    value_int = int(value * 100)  # 6543.21 → 654321
    value_str = f"{value_int:010d}"  # "0000654321"
    value_bytes = value_str.encode('ascii')
    
    # 결합
    data = name_bytes + separator + value_bytes
    
    return data


# ==================== TCP 클라이언트 ====================
def send_dummy_data():
    """중앙 서버로 더미 데이터 전송"""
    print("\n" + "=" * 60)
    print("🧪 HMI 더미 클라이언트 시작")
    print("=" * 60)
    print(f"서버: {SERVER_HOST}:{SERVER_PORT}")
    print(f"병원명: {HOSPITAL_NAME}")
    print(f"전송 간격: {SEND_INTERVAL}초")
    print("=" * 60 + "\n")
    
    # 기준 전력량 (변동 기준)
    base_value = 6543.21
    
    while True:
        try:
            # TCP 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            # 서버 접속
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 서버 접속 중...")
            sock.connect((SERVER_HOST, SERVER_PORT))
            print(f"✅ 접속 성공!")
            
            # 더미 데이터 생성
            data = generate_dummy_data(HOSPITAL_NAME, base_value)
            
            # HEX 출력 (디버깅용)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            print(f"📤 전송 데이터 (HEX): {hex_str}")
            
            # ASCII 파싱 출력
            name = data[0:3].decode('ascii')
            value_str = data[5:15].decode('ascii')
            value_display = f"{int(value_str[:-2])}.{value_str[-2:]}"
            print(f"📤 전송 데이터 (파싱): {name} = {value_display} kWh")
            
            # 데이터 전송
            sock.sendall(data)
            
            # 응답 수신 (선택)
            try:
                response = sock.recv(1024)
                if response:
                    print(f"📥 서버 응답: {response.decode('utf-8', errors='replace').strip()}")
            except socket.timeout:
                pass
            
            # 소켓 닫기
            sock.close()
            print(f"✅ 전송 완료\n")
            
            # 다음 전송까지 대기
            time.sleep(SEND_INTERVAL)
            
            # 기준값 조금씩 증가 (누적 전력량 시뮬레이션)
            base_value += random.uniform(0.5, 2.0)
        
        except ConnectionRefusedError:
            print(f"❌ 연결 거부: 서버가 실행 중인지 확인하세요")
            time.sleep(10)
        
        except socket.timeout:
            print(f"⚠️ 연결 타임아웃")
            time.sleep(10)
        
        except Exception as e:
            print(f"❌ 오류: {e}")
            time.sleep(10)
        
        finally:
            try:
                sock.close()
            except:
                pass


# ==================== 메인 ====================
if __name__ == "__main__":
    try:
        send_dummy_data()
    except KeyboardInterrupt:
        print("\n\n🛑 프로그램 종료")
