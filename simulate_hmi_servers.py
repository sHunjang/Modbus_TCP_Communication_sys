#!/usr/bin/env python3
"""
simulate_hmi_servers.py
실제 HMI를 대체하는 가상 Modbus 서버 (3개)

인천병원:   192.168.1.100:5020
안산병원:   192.168.1.101:5021
대구병원:   192.168.1.102:5022

에러 시뮬레이션:
- 장치 읽기 불가 (Device Read Error)
- CRC 에러 (CRC Error)
- 타이밍 에러 (Timeout)
"""

import socket
import struct
import threading
import time
import random
from datetime import datetime


class ModbusSimulatedDevice:
    """
    Modbus TCP 프로토콜을 시뮬레이션하는 가상 장치
    """
    
    def __init__(self, hospital_name, ip_address, port, device_id=1):
        """
        초기화
        
        Args:
            hospital_name (str): 병원명
            ip_address (str): 바인딩할 IP
            port (int): 바인딩할 포트
            device_id (int): Modbus Device ID
        """
        self.hospital_name = hospital_name
        self.ip_address = ip_address
        self.port = port
        self.device_id = device_id
        
        # 소켓
        self.socket = None
        self.running = False
        
        # 시뮬레이션 데이터
        self.energy_value = random.uniform(1000, 2000)  # kWh
        self.lock = threading.Lock()
        
        # 에러 시뮬레이션
        self.error_probability = 10  # 10% 확률로 에러 발생
        self.error_types = [
            "device_read_error",      # 장치 읽기 불가
            "crc_error",              # CRC 에러
            "timeout_error",          # 타이밍 에러
            "none"                    # 정상 (70%)
        ]
        
        # 통계
        self.stats = {
            "requests": 0,
            "success": 0,
            "errors": 0
        }
    
    def start(self):
        """서버 시작"""
        print(f"\n🔌 {self.hospital_name} 가상 HMI 서버 시작")
        print(f"   📍 {self.ip_address}:{self.port}")
        print(f"   ⚙️ Modbus Device ID: {self.device_id}\n")
        
        self.running = True
        
        # 소켓 바인드
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.ip_address, self.port))
        self.socket.listen(5)
        self.socket.settimeout(1.0)
        
        # 데이터 업데이트 스레드
        update_thread = threading.Thread(
            target=self._update_energy_data,
            daemon=True
        )
        update_thread.start()
        
        # 통신 수락 스레드
        accept_thread = threading.Thread(
            target=self._accept_connections,
            daemon=True
        )
        accept_thread.start()
    
    def _update_energy_data(self):
        """에너지 데이터 업데이트 (시뮬레이션)"""
        while self.running:
            try:
                with self.lock:
                    # 0 ~ 50 범위의 랜덤 증가
                    increment = random.uniform(0.5, 50.0)
                    self.energy_value += increment
                
                time.sleep(5)  # 5초마다 업데이트
            
            except Exception as e:
                print(f"❌ {self.hospital_name} 데이터 업데이트 오류: {e}")
    
    def _accept_connections(self):
        """클라이언트 연결 수락"""
        while self.running:
            try:
                client_socket, client_address = self.socket.accept()
                
                # 각 클라이언트마다 스레드 생성
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ {self.hospital_name} 연결 수락 오류: {e}")
    
    def _handle_client(self, client_socket, client_address):
        """클라이언트 요청 처리"""
        try:
            # 데이터 수신
            data = client_socket.recv(1024)
            
            if len(data) < 8:
                client_socket.close()
                return
            
            # Modbus TCP 요청 파싱
            response = self._process_modbus_request(data)
            
            # 응답 송신
            if response:
                client_socket.send(response)
            
            self.stats['requests'] += 1
        
        except Exception as e:
            print(f"⚠️ {self.hospital_name} 클라이언트 처리 오류: {e}")
        
        finally:
            client_socket.close()
    
    def _process_modbus_request(self, data):
        """
        Modbus TCP 요청 처리
        
        요청 구조:
        - Transaction ID (2 bytes)
        - Protocol ID (2 bytes) = 0x0000
        - Length (2 bytes)
        - Unit ID (1 byte)
        - Function Code (1 byte)
        - Starting Address (2 bytes)
        - Quantity (2 bytes)
        """
        
        try:
            # Modbus TCP 헤더 파싱
            transaction_id = struct.unpack('>H', data[0:2])[0]
            protocol_id = struct.unpack('>H', data[2:4])[0]
            length = struct.unpack('>H', data[4:6])[0]
            unit_id = data[6]
            function_code = data[7]
            
            # 프로토콜 ID 검증
            if protocol_id != 0x0000:
                return None
            
            # Function Code 03H: Read Holding Registers
            if function_code == 0x03:
                return self._read_holding_registers(
                    transaction_id, unit_id, data[8:]
                )
            
            return None
        
        except Exception as e:
            print(f"❌ {self.hospital_name} 요청 처리 오류: {e}")
            return None
    
    def _read_holding_registers(self, transaction_id, unit_id, payload):
        """
        레지스터 읽기 요청 처리
        레지스터 10-11: 유효전력량 (32비트)
        """
        
        try:
            # 시작 주소, 수량 파싱
            start_addr = struct.unpack('>H', payload[0:2])[0]
            quantity = struct.unpack('>H', payload[2:4])[0]
            
            # ✨ 에러 시뮬레이션
            error_type = self._simulate_error()
            
            if error_type == "device_read_error":
                # 장치 읽기 불가 에러 (Exception Code 0x03)
                return self._build_error_response(
                    transaction_id, unit_id, 0x03, 0x03
                )
            
            elif error_type == "crc_error":
                # CRC 에러 시뮬레이션 (데이터 손상)
                return self._build_error_response(
                    transaction_id, unit_id, 0x03, 0x04
                )
            
            elif error_type == "timeout_error":
                # 타이밍 에러 - 응답 지연 또는 미응답
                time.sleep(3)  # 3초 지연
                return None
            
            # ✅ 정상 응답
            registers = self._get_energy_registers()
            return self._build_read_response(
                transaction_id, unit_id, registers
            )
        
        except Exception as e:
            print(f"❌ {self.hospital_name} 레지스터 읽기 오류: {e}")
            return None
    
    def _simulate_error(self):
        """
        에러 시뮬레이션
        10% 확률로 에러 발생 (device_read, crc, timeout)
        """
        rand = random.randint(1, 100)
        
        if rand <= self.error_probability:
            # 에러 발생 (10%)
            error = random.choice(self.error_types[:-1])  # "none" 제외
            if error == "device_read_error":
                print(f"   ⚠️ {self.hospital_name}: 장치 읽기 불가")
            elif error == "crc_error":
                print(f"   ⚠️ {self.hospital_name}: CRC 에러")
            elif error == "timeout_error":
                print(f"   ⚠️ {self.hospital_name}: 타이밍 에러")
            self.stats['errors'] += 1
            return error
        else:
            # 정상 (90%)
            self.stats['success'] += 1
            return "none"
    
    def _get_energy_registers(self):
        """
        현재 에너지 값을 Modbus 레지스터로 변환
        
        Returns:
            list: [high_word, low_word]
        """
        with self.lock:
            # 정수값으로 변환
            energy_int = int(self.energy_value * 100)  # 센트 단위
            
            # 32비트를 두 개의 16비트 레지스터로 분할
            high_word = (energy_int >> 16) & 0xFFFF
            low_word = energy_int & 0xFFFF
            
            return [high_word, low_word]
    
    def _build_read_response(self, transaction_id, unit_id, registers):
        """
        Modbus 읽기 응답 구성
        
        구조:
        - Transaction ID (2 bytes)
        - Protocol ID (2 bytes) = 0x0000
        - Length (2 bytes)
        - Unit ID (1 byte)
        - Function Code (1 byte)
        - Byte Count (1 byte)
        - Register Data (2 bytes each)
        """
        
        # 데이터 부분
        byte_count = len(registers) * 2
        function_code = 0x03
        
        # 응답 구성
        response = struct.pack('>HH', transaction_id, 0x0000)  # Transaction, Protocol
        response += struct.pack('>H', byte_count + 3)          # Length (data + unit + func + count)
        response += struct.pack('B', unit_id)                   # Unit ID
        response += struct.pack('B', function_code)             # Function Code
        response += struct.pack('B', byte_count)                # Byte Count
        
        # 레지스터 추가
        for register in registers:
            response += struct.pack('>H', register)
        
        return response
    
    def _build_error_response(self, transaction_id, unit_id, function_code, exception_code):
        """
        Modbus 에러 응답 구성
        """
        
        response = struct.pack('>HH', transaction_id, 0x0000)  # Transaction, Protocol
        response += struct.pack('>H', 3)                        # Length (unit + func + exception)
        response += struct.pack('B', unit_id)                   # Unit ID
        response += struct.pack('B', function_code | 0x80)      # Function Code + Error Bit
        response += struct.pack('B', exception_code)            # Exception Code
        
        return response
    
    def stop(self):
        """서버 중지"""
        self.running = False
        if self.socket:
            self.socket.close()
        print(f"🛑 {self.hospital_name} 서버 중지\n")
    
    def print_statistics(self):
        """통계 출력"""
        print(f"\n{'='*60}")
        print(f"📊 {self.hospital_name} 통계")
        print(f"{'='*60}")
        print(f"총 요청 수:     {self.stats['requests']}")
        print(f"성공:          {self.stats['success']}")
        print(f"에러:          {self.stats['errors']}")
        if self.stats['requests'] > 0:
            success_rate = (self.stats['success'] / self.stats['requests']) * 100
            print(f"성공률:        {success_rate:.1f}%")
        print(f"현재 전력량:    {self.energy_value:.2f} kWh")
        print(f"{'='*60}\n")


# ============================================================
# 메인 실행
# ============================================================

def main():
    """
    3개의 가상 HMI 서버 시작
    """
    
    print("\n" + "="*60)
    print("🏥 가상 HMI Modbus 서버 시뮬레이션")
    print("="*60)
    print("📡 실제 HMI를 대체하는 가상 Modbus 서버를 시작합니다.\n")
    
    # 3개의 가상 서버 설정
    servers_config = [
        {
            "name": "🏥 인천병원",
            "ip": "127.0.0.1",
            "port": 5020,
            "device_id": 1
        },
        {
            "name": "🏥 안산병원",
            "ip": "127.0.0.1",
            "port": 5021,
            "device_id": 2
        },
        {
            "name": "🏥 대구병원",
            "ip": "127.0.0.1",
            "port": 5022,
            "device_id": 3
        }
    ]
    
    servers = []
    
    # 서버 시작
    for config in servers_config:
        server = ModbusSimulatedDevice(
            hospital_name=config["name"],
            ip_address=config["ip"],
            port=config["port"],
            device_id=config["device_id"]
        )
        server.start()
        servers.append(server)
    
    print("\n✅ 모든 서버가 시작되었습니다.")
    print("\n💡 클라이언트 연결 대기 중...\n")
    print("📝 접속 정보:")
    print("   - 인천병원:   127.0.0.1:5020")
    print("   - 안산병원:   127.0.0.1:5021")
    print("   - 대구병원:   127.0.0.1:5022\n")
    print("⚠️ 에러 발생 확률: 10% (장치 읽기 불가, CRC 에러, 타이밍 에러)\n")
    
    try:
        # 계속 실행
        while True:
            time.sleep(10)
            
            # 10초마다 통계 출력
            for server in servers:
                server.print_statistics()
    
    except KeyboardInterrupt:
        print("\n\n🛑 서버 중지 중...\n")
        
        for server in servers:
            server.stop()
        
        # 최종 통계
        for server in servers:
            server.print_statistics()
        
        print("✅ 모든 서버가 중지되었습니다.\n")


if __name__ == "__main__":
    main()
