#!/usr/bin/env python3
"""
simulate_hmi_servers.py (pymodbus 3.5.0 - 소켓 기반)

간단한 Modbus TCP 서버 - 저수준 구현
"""

import json
import time
import random
import threading
import socket
import struct
from pathlib import Path
from datetime import datetime


class PowerMeterSimulator:
    """전력량계 시뮬레이터"""
    
    def __init__(self, hospital_name):
        self.hospital_name = hospital_name
        self.current_power = random.uniform(1000, 2000)
        self.power_variance = 50
        self.lock = threading.Lock()
    
    def get_power_data(self):
        """현재 전력량 반환 (x100)"""
        with self.lock:
            change = random.uniform(-self.power_variance, self.power_variance)
            self.current_power = max(1000, min(2000, self.current_power + change))
            return int(self.current_power * 100)


class SimpleModbusServer:
    """간단한 Modbus TCP 서버"""
    
    def __init__(self, hospital_name, host, port):
        self.hospital_name = hospital_name
        self.host = host
        self.port = port
        self.running = False
        self.simulator = PowerMeterSimulator(hospital_name)
        self.power_value = 0
    
    def start(self):
        """서버 시작"""
        print(f"\n🔌 {self.hospital_name} Modbus TCP 서버 시작")
        print(f"   📍 {self.host}:{self.port}")
        print(f"   ⚙️ 모델: EM480 (3P4W)\n")
        
        self.running = True
        
        # 데이터 업데이트 스레드
        update_thread = threading.Thread(target=self._update_data, daemon=True)
        update_thread.start()
        
        # 서버 스레드
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()
    
    def _update_data(self):
        """1초마다 데이터 업데이트"""
        while self.running:
            try:
                self.power_value = self.simulator.get_power_data()
                print(f"   📊 {self.hospital_name}: {self.power_value/100:.2f} kWh")
                time.sleep(1)
            except Exception as e:
                print(f"   ❌ {self.hospital_name} 오류: {e}")
    
    def _run_server(self):
        """Modbus TCP 서버 실행"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)
            
            while self.running:
                try:
                    client_socket, client_addr = server_socket.accept()
                    
                    # 클라이언트 처리 스레드
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket,),
                        daemon=True
                    )
                    thread.start()
                
                except socket.timeout:
                    continue
        
        except Exception as e:
            print(f"❌ {self.hospital_name} 서버 오류: {e}")
        finally:
            server_socket.close()
    
    def _handle_client(self, client_socket):
        """클라이언트 요청 처리"""
        try:
            data = client_socket.recv(1024)
            
            if len(data) >= 8:
                # Modbus TCP 요청 파싱
                transaction_id = struct.unpack('>H', data[0:2])[0]
                protocol_id = struct.unpack('>H', data[2:4])[0]
                
                if protocol_id == 0x0000:  # Modbus TCP
                    # 응답 만들기
                    response = self._build_response(transaction_id)
                    client_socket.send(response)
        
        except Exception as e:
            pass
        finally:
            client_socket.close()
    
    def _build_response(self, transaction_id):
        """Modbus TCP 응답 구성"""
        # 32bit 데이터를 두 개의 16bit로 분할
        high_word = (self.power_value >> 16) & 0xFFFF
        low_word = self.power_value & 0xFFFF
        
        # Modbus TCP 응답
        response = struct.pack('>H', transaction_id)          # Transaction ID
        response += struct.pack('>H', 0x0000)                 # Protocol ID
        response += struct.pack('>H', 7)                      # Length
        response += struct.pack('B', 1)                       # Unit ID
        response += struct.pack('B', 0x03)                    # Function Code (Read Holding Registers)
        response += struct.pack('B', 4)                       # Byte Count
        response += struct.pack('>H', high_word)              # Register 0
        response += struct.pack('>H', low_word)               # Register 1
        
        return response


def load_hospital_config():
    """병원 설정 로드"""
    config_path = Path(__file__).parent / 'config' / 'hospital.json'
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('hospitals', [])
    except Exception as e:
        print(f"❌ 설정 파일 로드 실패: {e}")
        return []


def main():
    """메인 함수"""
    
    print("\n" + "="*60)
    print("🏥 HMI 서버 시뮬레이터 (소켓 기반)")
    print("="*60)
    print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    hospitals = load_hospital_config()
    
    if not hospitals:
        print("\n❌ 병원 설정을 찾을 수 없습니다!")
        print("📁 경로: config/hospital.json")
        return
    
    print(f"\n✅ {len(hospitals)}개의 병원 설정을 로드했습니다.\n")
    
    # 모든 서버 시작
    servers = []
    for hospital in hospitals:
        server = SimpleModbusServer(
            hospital['hospital_name'],
            '0.0.0.0',
            hospital['port']
        )
        server.start()
        servers.append(server)
        time.sleep(0.5)
    
    print("="*60)
    print("✅ 모든 서버가 시작되었습니다!")
    print("="*60)
    print("\n📍 접속 정보:")
    for hospital in hospitals:
        print(f"   - {hospital['hospital_name']:15} 127.0.0.1:{hospital['port']}")
    print("\n💡 Ctrl+C를 눌러 종료합니다.\n")
    
    try:
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 모든 서버를 종료합니다...\n")
        for server in servers:
            server.running = False


if __name__ == "__main__":
    main()
