#!/usr/bin/env python3

# core/modbus_thread.py

"""
Modbus TCP 통신 스레드 (더미 모드 지원)
- 실제 통신 또는 시뮬레이션
- 3상4선 전체 데이터 지원 (전압, 전류, 유효전력, 전력량)
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pyModbusTCP.client import ModbusClient
import time
from datetime import datetime

from core.dummy_modbus_server import DummyModbusServer

# 더미 서버 임포트
try:
    from core.dummy_modbus_server import get_dummy_server
except ImportError:
    def get_dummy_server(name):
        return None

class ModbusThread(QThread):
    """Modbus TCP 통신 스레드 (실제 또는 시뮬레이션)"""
    
    data_received = pyqtSignal(dict)  # 전체 데이터 수신 시그널 (딕셔너리)
    log_message = pyqtSignal(str)      # 로그 메시지
    connection_status = pyqtSignal(bool)  # 연결 상태

    def __init__(self, hospital_name, hmi_ip, port=502, unit_id=1,
                 meter_type="3P4W", use_dummy=False):
        """
        초기화
        
        Args:
            hospital_name (str): 병원명
            hmi_ip (str): HMI IP 주소
            port (int): Modbus TCP 포트
            unit_id (int): Unit ID
            meter_type (str): 미터 타입 ("1P2W", "3P3W", "3P4W")
            use_dummy (bool): 더미 모드 사용 여부
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

        # 3상4선(TAC4300) 레지스터 맵 - 완전 버전
        self.register_map = {
            # # 1P2W (단상 2선)
            # "1P2W": {
            #     "voltage": (0x0000, 0x0002),        # L1 전압
            #     "current": (0x0006, 0x0008),        # L1 전류
            #     "power": (0x000C, 0x000E),          # L1 유효전력
            #     "energy": (0x0420, 0x0422),         # L1 전력량
            # },
            # # 3P3W (3상 3선)
            # "3P3W": {
            #     "voltage_l1": (0x0000, 0x0002),     # L1 전압
            #     "voltage_l2": (0x0004, 0x0006),     # L2 전압
            #     "voltage_l3": (0x0008, 0x000A),     # L3 전압
            #     "current_l1": (0x0006, 0x0008),     # L1 전류
            #     "current_l2": (0x000A, 0x000C),     # L2 전류
            #     "current_l3": (0x000E, 0x0010),     # L3 전류
            #     "power_l1": (0x000C, 0x000E),       # L1 유효전력
            #     "power_l2": (0x0010, 0x0012),       # L2 유효전력
            #     "power_l3": (0x0014, 0x0016),       # L3 유효전력
            #     "energy": (0x0420, 0x0422),         # 전력량
            # },
            # 3P4W (3상 4선) - TAC4300
            "3P4W": {
                # 전압 (L1, L2, L3)
                "voltage_l1": (0x0024, 0x0026),     # L1 전압: 0x0024
                "voltage_l2": (0x0026, 0x0028),     # L2 전압: 0x0026
                "voltage_l3": (0x0028, 0x002A),     # L3 전압: 0x0028
                
                # 전류 (L1, L2, L3)
                "current_l1": (0x0006, 0x0008),     # L1 전류: 0x0006
                "current_l2": (0x0008, 0x000A),     # L2 전류: 0x0008
                "current_l3": (0x000A, 0x000C),     # L3 전류: 0x000A
                
                # 유효전력 (L1, L2, L3)
                "power_l1": (0x000C, 0x000E),       # L1 유효전력: 0x000C
                "power_l2": (0x000E, 0x0010),       # L2 유효전력: 0x000E
                "power_l3": (0x0010, 0x0012),       # L3 유효전력: 0x0010
                
                # 전력량 (L1, L2, L3)
                "energy_l1": (0x0420, 0x0422),      # L1 전력량: 0x0420
                "energy_l2": (0x0422, 0x0424),      # L2 전력량: 0x0422
                "energy_l3": (0x0424, 0x0426),      # L3 전력량: 0x0424
                
                # 전체 전력량
                "total_energy": (0x0404, 0x0408),
            }
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
                data = self.read_all_data()
                
                if data is not None:
                    self.stats['success'] += 1
                    self.data_received.emit(data)
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

    def read_all_data(self):
        """
        모든 데이터 읽기 (전압, 전류, 유효전력, 전력량)
        
        Returns:
            dict: 미터별 데이터 딕셔너리
            {
                "meter_type": "3P4W",
                "voltage_l1": 230.5,
                "voltage_l2": 231.2,
                "voltage_l3": 229.8,
                "current_l1": 10.5,
                "current_l2": 11.2,
                "current_l3": 9.8,
                "power_l1": 2000,
                "power_l2": 2200,
                "power_l3": 1900,
                "energy_l1": 30000,
                "energy_l2": 30001,
                "energy_l3": 30002,
                "timestamp": "2025-11-05 14:23:45"
            }
        """
        self.stats['total'] += 1

        try:
            if self.use_dummy:
                dummy_server = get_dummy_server(self.hospital_name)
                if dummy_server:
                    # ★ 정적 메서드 호출
                    return DummyModbusServer.get_all_data()  # ★ 수정!
                else:
                    return None
            else:
                # 실제 모드: Modbus 통신
                register_map = self.register_map.get(self.meter_type)
                if not register_map:
                    self.log_message.emit(f"❌ 지원하지 않는 미터 타입: {self.meter_type}")
                    return None

                data = {
                    "meter_type": self.meter_type,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # 3상4선 데이터 읽기
                if self.meter_type == "3P4W":
                    # 전압 읽기
                    voltage_l1 = self._read_32bit_register(
                        register_map["voltage_l1"][0]
                    )
                    voltage_l2 = self._read_32bit_register(
                        register_map["voltage_l2"][0]
                    )
                    voltage_l3 = self._read_32bit_register(
                        register_map["voltage_l3"][0]
                    )

                    # 전류 읽기
                    current_l1 = self._read_32bit_register(
                        register_map["current_l1"][0]
                    )
                    current_l2 = self._read_32bit_register(
                        register_map["current_l2"][0]
                    )
                    current_l3 = self._read_32bit_register(
                        register_map["current_l3"][0]
                    )

                    # 유효전력 읽기
                    power_l1 = self._read_32bit_register(
                        register_map["power_l1"][0]
                    )
                    power_l2 = self._read_32bit_register(
                        register_map["power_l2"][0]
                    )
                    power_l3 = self._read_32bit_register(
                        register_map["power_l3"][0]
                    )

                    # 전력량 읽기
                    energy_l1 = self._read_32bit_register(
                        register_map["energy_l1"][0]
                    )
                    energy_l2 = self._read_32bit_register(
                        register_map["energy_l2"][0]
                    )
                    energy_l3 = self._read_32bit_register(
                        register_map["energy_l3"][0]
                    )

                    # 데이터 저장
                    data.update({
                        "voltage_l1": voltage_l1,
                        "voltage_l2": voltage_l2,
                        "voltage_l3": voltage_l3,
                        "current_l1": current_l1,
                        "current_l2": current_l2,
                        "current_l3": current_l3,
                        "power_l1": power_l1,
                        "power_l2": power_l2,
                        "power_l3": power_l3,
                        "energy_l1": energy_l1,
                        "energy_l2": energy_l2,
                        "energy_l3": energy_l3,
                    })

                    # 총합 계산
                    data.update({
                        "voltage_avg": (voltage_l1 + voltage_l2 + voltage_l3) / 3,
                        "current_total": current_l1 + current_l2 + current_l3,
                        "power_total": power_l1 + power_l2 + power_l3,
                        "energy_total": energy_l1 + energy_l2 + energy_l3,
                    })

                else:
                    # 기타 미터 타입 (1P2W, 3P3W)
                    for key, (reg_start, reg_end) in register_map.items():
                        value = self._read_32bit_register(reg_start)
                        data[key] = value

                return data

        except Exception as e:
            self.log_message.emit(f"❌ {self.hospital_name} 읽기 오류: {e}")
            return None

    def _read_32bit_register(self, reg_addr):
        """
        32비트 레지스터 읽기 (Big-Endian)
        
        Args:
            reg_addr (int): 시작 레지스터 주소
            
        Returns:
            int: 32비트 값
        """
        try:
            data = self.client.read_holding_registers(
                reg_addr=reg_addr,
                reg_nb=2
            )

            if not data or len(data) < 2:
                return None

            # 32비트 Big-Endian 처리
            high_word = data[0]
            low_word = data[1]

            # Big-Endian 순서: 상위 먼저
            value_32bit = (high_word << 16) | low_word

            return value_32bit

        except Exception as e:
            self.log_message.emit(f"❌ 레지스터 읽기 오류 (0x{reg_addr:04X}): {e}")
            return None

    def stop(self):
        """스레드 중지"""
        self.running = False

    def get_statistics(self):
        """통계 반환"""
        return self.stats.copy()
