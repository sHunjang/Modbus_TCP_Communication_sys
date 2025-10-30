#!/usr/bin/env python3
# core/modbus_thread.py
"""
Modbus TCP 통신 스레드 (더미 모드 지원)
- 실제 통신 또는 시뮬레이션
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pyModbusTCP.client import ModbusClient
import time
from datetime import datetime

# 더미 서버 임포트
try:
    from core.dummy_modbus_server import get_dummy_server
except ImportError:
    def get_dummy_server(name):
        return None


class ModbusThread(QThread):
    """Modbus TCP 통신 스레드 (실제 또는 시뮬레이션)"""
    
    data_received = pyqtSignal(float)      # 유효전력량 수신 시그널
    log_message = pyqtSignal(str)          # 로그 메시지
    connection_status = pyqtSignal(bool)   # 연결 상태
    
    def __init__(self, hospital_name, hmi_ip, port=502, unit_id=1, 
                 meter_type="3P4W", use_dummy=False):
        """
        초기화
        
        Args:
            hospital_name (str): 병원명
            hmi_ip (str): HMI IP 주소
            port (int): Modbus TCP 포트
            unit_id (int): Unit ID
            meter_type (str): 미터 타입
            use_dummy (bool): 더미 모드 사용 여부 ✨ NEW
        """
        super().__init__()
        
        self.hospital_name = hospital_name
        self.hmi_ip = hmi_ip
        self.port = port
        self.unit_id = unit_id
        self.meter_type = meter_type
        self.use_dummy = use_dummy  # ✨ 더미 모드 플래그
        
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
            self.client = None  # 더미 모드에서는 client 불필요
        
        # 레지스터 위치
        self.energy_register_map = {
            "1P2W": (3, 4),
            "3P3W": (9, 10),
            "3P4W": (10, 11)
        }
        
        # 통계
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0
        }
    
    def run(self):
        """스레드 메인 루프"""
        self.running = True
        
        if self.use_dummy:
            mode_str = "🔌 더미 모드"
        else:
            mode_str = f"📡 실제 통신 ({self.hmi_ip})"
        
        self.log_message.emit(f"✅ {self.hospital_name} 시작 ({mode_str})")
        self.connection_status.emit(True)
        
        while self.running:
            try:
                energy_kwh = self.read_energy()
                
                if energy_kwh is not None:
                    self.stats['success'] += 1
                    self.data_received.emit(energy_kwh)
                else:
                    self.stats['failed'] += 1
                    self.log_message.emit(f"⚠️ {self.hospital_name} 데이터 읽기 실패")
                
                time.sleep(5)  # 5초 주기
            
            except Exception as e:
                self.stats['failed'] += 1
                self.log_message.emit(f"❌ {self.hospital_name} 오류: {e}")
                time.sleep(5)
        
        self.connection_status.emit(False)
        self.log_message.emit(f"🛑 {self.hospital_name} 중지")
    
    def read_energy(self):
        """유효전력량 읽기"""
        self.stats['total'] += 1
        
        try:
            if self.use_dummy:
                # ✨ 더미 모드: 가상 데이터 반환
                dummy_server = get_dummy_server(self.hospital_name)
                if dummy_server:
                    energy_kwh = dummy_server.get_energy_value()
                    return energy_kwh
                else:
                    return None
            else:
                # 실제 모드: Modbus 통신
                reg_start, reg_end = self.energy_register_map.get(
                    self.meter_type,
                    (10, 11)
                )
                
                data = self.client.read_holding_registers(
                    reg_addr=reg_start,
                    reg_nb=2
                )
                
                if not data or len(data) < 2:
                    return None
                
                high_word = data[0]
                low_word = data[1]
                
                energy_raw = int.from_bytes(
                    high_word.to_bytes(2, 'big') + low_word.to_bytes(2, 'big'),
                    'big'
                )
                
                energy_kwh = float(energy_raw)
                return energy_kwh
        
        except Exception as e:
            self.log_message.emit(f"❌ {self.hospital_name} 읽기 오류: {e}")
            return None
    
    def stop(self):
        """스레드 중지"""
        self.running = False
    
    def get_statistics(self):
        """통계 반환"""
        return self.stats.copy()
