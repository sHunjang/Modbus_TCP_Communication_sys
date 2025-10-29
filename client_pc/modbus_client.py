#!/usr/bin/env python3
# modbus_client.py
"""
PC 2: Modbus TCP 클라이언트 (회사 서버 시뮬레이터)
pymodbus 3.6+ 최신 버전 호환
"""

from pymodbus.client import ModbusTcpClient
import struct
import time
import csv
from datetime import datetime
from pathlib import Path

# ============================================================
# 유틸리티 함수
# ============================================================

def registers_to_float(registers):
    """
    2개의 16비트 레지스터를 Float로 변환
    
    Args:
        registers: [high_word, low_word]
    
    Returns:
        float 값
    """
    if len(registers) != 2:
        return 0.0
    
    high_word = registers[0]
    low_word = registers[1]
    
    # 32비트 정수로 결합
    combined = (high_word << 16) | low_word
    
    # Float로 변환
    try:
        value = struct.unpack('>f', struct.pack('>I', combined))[0]
        return value
    except:
        return 0.0


# ============================================================
# Modbus TCP 클라이언트
# ============================================================

class PowerDataCollector:
    """전력 데이터 수집기"""
    
    def __init__(self, host, port=502, device_id=1):
        """
        Args:
            host: 서버 IP 주소 (PC 1의 IP)
            port: Modbus TCP 포트 (기본 502)
            device_id: Device ID (Slave ID)
        """
        self.host = host
        self.port = port
        self.device_id = device_id
        self.client = ModbusTcpClient(host, port=port, timeout=5)
        
        # CSV 파일 설정
        self.csv_file = Path("power_data.csv")
        self._init_csv()
    
    def _init_csv(self):
        """CSV 파일 초기화"""
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp",
                    "Power (kW)",
                    "Energy (kWh)",
                    "Power Factor",
                    "Voltage (V)",
                    "Current (A)",
                    "Status"
                ])
            print(f"📁 CSV 파일 생성: {self.csv_file.absolute()}\n")
    
    def connect(self):
        """서버 연결"""
        print(f"🔌 {self.host}:{self.port} 연결 시도...")
        
        if self.client.connect():
            print(f"✅ 연결 성공!\n")
            return True
        else:
            print(f"❌ 연결 실패!")
            print(f"💡 확인사항:")
            print(f"   1. PC 1 서버가 실행 중인가?")
            print(f"   2. IP 주소가 맞는가? ({self.host})")
            print(f"   3. 포트 번호가 맞는가? ({self.port})")
            print(f"   4. 방화벽이 열려있는가?")
            print(f"   5. 같은 네트워크에 연결되어 있는가?")
            return False
    
    def read_power_data(self):
        """전력 데이터 읽기"""
        try:
            # 주소 0~9 (총 10개 레지스터) 읽기
            response = self.client.read_holding_registers(
                address=0,
                count=10,
                slave=self.device_id
            )
            
            if response.isError():
                return None
            
            registers = response.registers
            
            # Float 변환
            data = {
                "power_kw": registers_to_float(registers[0:2]),
                "energy_kwh": registers_to_float(registers[2:4]),
                "power_factor": registers_to_float(registers[4:6]),
                "voltage": registers_to_float(registers[6:8]),
                "current": registers_to_float(registers[8:10]),
                "status": "online"
            }
            
            return data
        
        except Exception as e:
            print(f"❌ 읽기 오류: {e}")
            return None
    
    def save_to_csv(self, data):
        """CSV 파일에 저장"""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    f"{data['power_kw']:.2f}",
                    f"{data['energy_kwh']:.2f}",
                    f"{data['power_factor']:.3f}",
                    f"{data['voltage']:.1f}",
                    f"{data['current']:.1f}",
                    data['status']
                ])
        except Exception as e:
            print(f"❌ CSV 저장 오류: {e}")
    
    def start_monitoring(self, interval=5, duration=60):
        """
        실시간 모니터링 시작
        
        Args:
            interval: 수집 주기 (초)
            duration: 총 실행 시간 (초, 0이면 무한)
        """
        if not self.connect():
            return
        
        print("=" * 70)
        print("📊 실시간 전력 데이터 수집 시작")
        print("=" * 70)
        print(f"⏱️ 수집 주기: {interval}초")
        print(f"📁 저장 위치: {self.csv_file.absolute()}")
        print(f"🛑 종료하려면 Ctrl+C를 누르세요")
        print("=" * 70)
        print()
        
        start_time = time.time()
        count = 0
        
        try:
            while True:
                # 데이터 읽기
                data = self.read_power_data()
                
                if data:
                    count += 1
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # 화면 출력
                    print(f"[{timestamp}] 📥 데이터 수신 #{count}")
                    print(f"  ⚡ 전력:   {data['power_kw']:>6.2f} kW")
                    print(f"  📈 전력량: {data['energy_kwh']:>6.2f} kWh")
                    print(f"  📊 역률:   {data['power_factor']:>6.3f}")
                    print(f"  🔌 전압:   {data['voltage']:>6.1f} V")
                    print(f"  ⚡ 전류:   {data['current']:>6.1f} A")
                    print()
                    
                    # CSV 저장
                    self.save_to_csv(data)
                else:
                    print(f"⚠️ 데이터 없음 (서버 응답 없음)")
                
                # 종료 조건
                if duration > 0 and (time.time() - start_time) >= duration:
                    print(f"\n✅ {duration}초 경과, 수집 종료")
                    break
                
                # 대기
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n\n🛑 사용자가 중지했습니다")
        
        finally:
            self.client.close()
            print(f"📴 연결 종료")
            print(f"📊 총 {count}개 데이터 수집 완료")
            print(f"📁 파일 확인: {self.csv_file.absolute()}")


# ============================================================
# 메인 실행
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("💻 Modbus TCP 클라이언트 (전력 데이터 수집기)")
    print("=" * 70)
    
    # 서버 IP 주소 입력
    print("\n📍 PC 1 (서버)의 IP 주소를 입력하세요")
    print("   예: 192.168.0.10")
    print("   (같은 PC에서 테스트: localhost 또는 127.0.0.1)")
    
    host = input("\n서버 IP 주소: ").strip()
    
    if not host:
        host = "localhost"  # 기본값
        print(f"기본값 사용: {host}")
    
    # 포트 번호 확인
    print("\n🔌 서버 포트 번호를 입력하세요")
    print("   기본값: 502 (Enter만 누르면 기본값 사용)")
    
    port_input = input("포트 번호: ").strip()
    port = int(port_input) if port_input else 502
    
    print()
    
    # 수집기 생성 및 시작
    collector = PowerDataCollector(host=host, port=port, device_id=1)
    
    # 5초마다 데이터 수집, 무한 실행 (duration=0)
    collector.start_monitoring(interval=5, duration=0)
