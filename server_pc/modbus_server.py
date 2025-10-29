#!/usr/bin/env python3
# modbus_server.py
"""
PC 1: Modbus TCP 서버 (HMI 시뮬레이터)
pymodbus 3.6+ 최신 버전 호환
"""

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartTcpServer
import struct
import random
import threading
import time
from datetime import datetime

# ============================================================
# 유틸리티 함수
# ============================================================

def float_to_registers(value):
    """
    Float 값을 2개의 16비트 레지스터로 변환
    
    Args:
        value: float 값 (예: 12.5)
    
    Returns:
        [high_word, low_word]
    """
    # Float → 32비트 정수
    packed = struct.pack('>f', value)
    high_word, low_word = struct.unpack('>HH', packed)
    return [high_word, low_word]


# ============================================================
# 전력 데이터 생성 및 업데이트
# ============================================================

class PowerDataGenerator:
    """전력 데이터 생성기"""
    
    def __init__(self, context):
        """
        Args:
            context: Modbus 서버 컨텍스트
        """
        self.context = context
        self.running = True
        
        # 초기 전력량
        self.accumulated_energy = 150.0
    
    def generate_power_data(self):
        """랜덤 전력 데이터 생성"""
        
        # 전력 (kW): 10~15 kW 사이 랜덤
        power_kw = random.uniform(10.0, 15.0)
        
        # 전력량 (kWh): 계속 증가
        self.accumulated_energy += (power_kw / 3600) * 5  # 5초마다 증가
        
        # 역률: 0.90 ~ 0.99
        power_factor = random.uniform(0.90, 0.99)
        
        # 전압 (V): 220 ± 5V
        voltage = random.uniform(215.0, 225.0)
        
        # 전류 (A): 전력 / 전압
        current = power_kw * 1000 / voltage
        
        return {
            "power_kw": power_kw,
            "energy_kwh": self.accumulated_energy,
            "power_factor": power_factor,
            "voltage": voltage,
            "current": current
        }
    
    def update_registers(self):
        """Modbus 레지스터 업데이트 (5초마다)"""
        
        print("=" * 70)
        print("🖥️ Modbus TCP 서버 시작 (HMI 시뮬레이터)")
        print("=" * 70)
        print(f"📍 IP 주소를 확인하세요!")
        print(f"   Windows: ipconfig")
        print(f"   Mac/Linux: ifconfig")
        print(f"🔌 포트: 502")
        print(f"⏱️ 데이터 갱신 주기: 5초")
        print(f"🛑 종료하려면 Ctrl+C를 누르세요")
        print("=" * 70)
        print()
        
        count = 0
        
        while self.running:
            try:
                count += 1
                
                # 전력 데이터 생성
                data = self.generate_power_data()
                
                # Slave Context 가져오기 (Device ID 1)
                slave_context = self.context[1]
                
                # 레지스터 값 설정
                # fx = 3 (Holding Registers), address, values
                slave_context.setValues(3, 0, float_to_registers(data["power_kw"]))
                slave_context.setValues(3, 2, float_to_registers(data["energy_kwh"]))
                slave_context.setValues(3, 4, float_to_registers(data["power_factor"]))
                slave_context.setValues(3, 6, float_to_registers(data["voltage"]))
                slave_context.setValues(3, 8, float_to_registers(data["current"]))
                
                # 화면 출력
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] 📊 데이터 갱신 #{count}")
                print(f"  ⚡ 전력:   {data['power_kw']:>6.2f} kW")
                print(f"  📈 전력량: {data['energy_kwh']:>6.2f} kWh")
                print(f"  📊 역률:   {data['power_factor']:>6.3f}")
                print(f"  🔌 전압:   {data['voltage']:>6.1f} V")
                print(f"  ⚡ 전류:   {data['current']:>6.1f} A")
                print()
                
                # 5초 대기
                time.sleep(5)
            
            except Exception as e:
                print(f"❌ 오류 발생: {e}")
                time.sleep(5)
    
    def start(self):
        """백그라운드 스레드로 시작"""
        thread = threading.Thread(target=self.update_registers, daemon=True)
        thread.start()


# ============================================================
# Modbus 서버 시작
# ============================================================

def run_server():
    """Modbus TCP 서버 실행"""
    
    # Datastore 생성
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),
        co=ModbusSequentialDataBlock(0, [0] * 100),
        hr=ModbusSequentialDataBlock(0, [0] * 100),  # ← Holding Registers
        ir=ModbusSequentialDataBlock(0, [0] * 100)
    )
    
    # Server Context
    context = ModbusServerContext(slaves={1: store}, single=False)
    
    # 데이터 생성기 시작
    generator = PowerDataGenerator(context)
    generator.start()
    
    # 서버 시작
    try:
        print("\n💡 주의: 포트 502는 관리자 권한이 필요할 수 있습니다!")
        print("   Windows: 우클릭 → '관리자 권한으로 실행'")
        print("   Linux/Mac: sudo python modbus_server.py\n")
        
        StartTcpServer(
            context=context,
            address=("0.0.0.0", 502)
        )
    except PermissionError:
        print("\n❌ 권한 오류!")
        print("   해결 방법:")
        print("   1. 관리자 권한으로 실행")
        print("   2. 또는 다른 포트 사용 (예: 5020)")
        print("\n   다른 포트로 재시도하시겠습니까? (y/n): ", end="")
        
        choice = input().strip().lower()
        if choice == 'y':
            port = 5020
            print(f"\n🔄 포트 {port}으로 재시도...\n")
            StartTcpServer(
                context=context,
                address=("0.0.0.0", port)
            )
    except KeyboardInterrupt:
        print("\n\n🛑 서버 종료 중...")
        generator.running = False
        print("✅ 서버 종료 완료")


if __name__ == "__main__":
    run_server()
