#!/usr/bin/env python3
# dummy_client.py

"""
HMI 더미 클라이언트 (단일 병원)

테스트용으로 중앙 서버에 더미 데이터 전송
포맷: [병원명3자리][전력량 가변길이] (ASCII 문자열)
"""

import socket
import time
import random
from datetime import datetime


# ==================== 설정 ====================
SERVER_HOST = "127.0.0.1"      # 중앙 서버 IP (로컬 테스트)
# SERVER_HOST = "14.42.209.171"  # 실제 서버 (포트포워딩 완료 시)
SERVER_PORT = 23000            # 중앙 서버 포트

HOSPITAL_NAME = "ICN"          # 병원명 3자리 (ICN, SEL, BUS 등)
SEND_INTERVAL = 10             # 전송 간격 (초) - HMI와 동일하게 10초


# ==================== 더미 데이터 생성 ====================
def generate_dummy_data(hospital_name: str, base_value: float = 7584.55) -> bytes:
    """
    HMI 포맷 더미 데이터 생성
    
    포맷: [병원명3자리][전력량 숫자]
    예: ICN00758455 → 병원: ICN, 전력: 7584.55 kWh
    
    Args:
        hospital_name: 병원명 (3자리)
        base_value: 기준 전력량 (소수점 포함)
    
    Returns:
        bytes: 전송할 ASCII 바이트 데이터
    """
    # 1. 병원명 (3바이트, ASCII)
    name_part = hospital_name[:3].ljust(3, 'X')
    
    # 2. 전력량 (랜덤 변동 ±5%)
    variation = random.uniform(-0.05, 0.05)
    value = base_value * (1 + variation)
    
    # 소수점 제거 후 8자리로 포맷
    # 7584.55 → 758455 → "00758455"
    value_int = int(value * 100)
    value_str = f"{value_int:08d}"
    
    # 결합 (전체 ASCII)
    data_str = name_part + value_str
    
    return data_str.encode('ascii')


# ==================== TCP 클라이언트 ====================
def send_dummy_data():
    """중앙 서버로 더미 데이터 전송 (10초마다)"""
    print("\n" + "=" * 60)
    print("🧪 HMI 더미 클라이언트 (단일 병원)")
    print("=" * 60)
    print(f"서버: {SERVER_HOST}:{SERVER_PORT}")
    print(f"병원명: {HOSPITAL_NAME}")
    print(f"전송 간격: {SEND_INTERVAL}초")
    print("=" * 60 + "\n")
    
    # 기준 전력량 (누적 시뮬레이션)
    base_value = 7584.55
    
    while True:
        try:
            # TCP 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            # 서버 접속
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] 서버 접속 중...")
            sock.connect((SERVER_HOST, SERVER_PORT))
            print(f"✅ 접속 성공!")
            
            # 더미 데이터 생성
            data = generate_dummy_data(HOSPITAL_NAME, base_value)
            
            # HEX 출력 (디버깅용)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            print(f"📤 전송 (HEX): {hex_str}")
            
            # ASCII 출력
            ascii_str = data.decode('ascii')
            print(f"📤 전송 (ASCII): {ascii_str}")
            
            # 파싱 시뮬레이션
            name = ascii_str[0:3]
            value_str = ascii_str[3:]
            value_display = f"{int(value_str[:-2])}.{value_str[-2:]}"
            print(f"📤 전송 (파싱): 병원={name}, 전력={value_display} kWh")
            
            # 데이터 전송
            sock.sendall(data)
            
            # 응답 수신 (선택)
            try:
                sock.settimeout(2.0)
                response = sock.recv(1024)
                if response:
                    print(f"📥 서버 응답: {response.decode('utf-8', errors='replace').strip()}")
            except socket.timeout:
                print(f"⏱️ 응답 타임아웃 (무시)")
            
            # 소켓 닫기
            sock.close()
            print(f"✅ 전송 완료\n")
            
            # 다음 전송까지 대기
            time.sleep(SEND_INTERVAL)
            
            # 전력량 조금씩 증가 (누적 시뮬레이션)
            base_value += random.uniform(0.1, 1.0)
        
        except ConnectionRefusedError:
            print(f"❌ 연결 거부: 서버가 실행 중인지 확인하세요")
            time.sleep(10)
        
        except socket.timeout:
            print(f"⚠️ 연결 타임아웃")
            time.sleep(10)
        
        except KeyboardInterrupt:
            print("\n\n🛑 프로그램 종료")
            break
        
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
    send_dummy_data()
