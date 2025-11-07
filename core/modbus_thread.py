#!/usr/bin/env python3
# core/modbus_thread.py

"""
Modbus TCP 통신 스레드 - 전체전력량만 읽기
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pyModbusTCP.client import ModbusClient
import time
from datetime import datetime

# 더미 서버
try:
    from core.dummy_modbus_server import get_dummy_server, DummyModbusServer
except ImportError:
    def get_dummy_server(name):
        return None


class ModbusThread(QThread):
    """Modbus TCP 통신 - 전체전력량만 읽기"""
    
    data_received = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self, hospital_name, hmi_ip, port=502, unit_id=128,
                 meter_type="3P4W", use_dummy=False):
        """
        초기화
        Args:
            hospital_name: 병원명
            hmi_ip: HMI IP 주소
            port: Modbus TCP 포트
            unit_id: Unit ID (기본: 128 = 0x80)
            meter_type: 미터 타입
            use_dummy: 더미 모드
        """
        super().__init__()
        self.hospital_name = hospital_name
        self.hmi_ip = hmi_ip
        self.port = port
        self.unit_id = unit_id
        self.meter_type = meter_type
        self.use_dummy = use_dummy
        self.running = False
        
        # 실제 모드 또는 더미 모드
        if not use_dummy:
            self.client = ModbusClient(
                host=hmi_ip,
                port=port,
                unit_id=unit_id,
                timeout=2.0
            )
        else:
            self.client = None
    
    def run(self):
        """스레드 메인 루프"""
        self.running = True
        
        mode_str = "🔌 더미 모드" if self.use_dummy else f"📡 실제 통신 ({self.hmi_ip}:{self.port})"
        self.log_message.emit(f"✅ {self.hospital_name} 시작 ({mode_str})")
        self.connection_status.emit(True)
        
        while self.running:
            try:
                data = self.read_total_energy()
                
                if data is not None:
                    self.data_received.emit(data)
                else:
                    self.log_message.emit(f"⚠️ {self.hospital_name} 전체전력량 읽기 실패")
                
                time.sleep(5)  # 5초 주기
                
            except Exception as e:
                self.log_message.emit(f"❌ {self.hospital_name} 오류: {e}")
                time.sleep(5)
        
        self.connection_status.emit(False)
        self.log_message.emit(f"🛑 {self.hospital_name} 중지")
    
    def read_total_energy(self):
        """
        전체전력량만 읽기 (32비트)
        
        Returns:
            dict: {
                "total_energy": 123456,
                "timestamp": "2025-11-07 17:05:00"
            }
        """
        try:
            if self.use_dummy:
                # 더미 모드: 가상 데이터
                import random
                return {
                    "total_energy": random.randint(100000, 999999),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            else:
                # 실제 모드: Modbus TCP 통신
                # 전체전력량 주소: 0x0404 (2개 레지스터, 32비트)
                total_energy_addr = 0x0404
                
                # 32비트 읽기
                regs = self.client.read_holding_registers(
                    reg_addr=total_energy_addr,
                    reg_nb=2  # 2개 레지스터
                )
                
                if not regs or len(regs) < 2:
                    return None
                
                # 32비트 Big-Endian 조합
                high_word = regs[0]
                low_word = regs[1]
                total_energy = (high_word << 16) | low_word
                
                return {
                    "total_energy": total_energy,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
        except Exception as e:
            self.log_message.emit(f"❌ {self.hospital_name} 전체전력량 읽기 오류: {e}")
            return None
    
    def stop(self):
        """스레드 중지"""
        self.running = False
