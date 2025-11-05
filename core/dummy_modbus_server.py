#!/usr/bin/env python3

# core/dummy_modbus_server.py

"""
더미 Modbus 서버
가상 3상 4선 데이터 생성 및 Modbus 통신 시뮬레이션
"""

import threading
import time
from datetime import datetime
import random

class DummyModbusServer:
    """
    가상 Modbus 서버
    - 3상 데이터 시뮬레이션
    - L1, L2, L3 전압/전류/유효전력/전력량 생성
    """

    def __init__(self, port=502, hospital_name="Test"):
        """
        초기화

        Args:
            port (int): 바인딩할 포트
            hospital_name (str): 병원명
        """
        self.port = port
        self.hospital_name = hospital_name
        self.running = False

        # ★★★ 3상 데이터 시뮬레이션 ★★★
        self.energy_l1 = 30000.0  # L1 전력량 (kWh)
        self.energy_l2 = 30001.0  # L2 전력량 (kWh)
        self.energy_l3 = 30002.0  # L3 전력량 (kWh)
        
        self.lock = threading.Lock()

    def start(self):
        """서버 시작"""
        self.running = True
        print(f"🔌 [{self.hospital_name}] 가상 Modbus 서버 시작 (포트: {self.port})")

        # 데이터 업데이트 스레드 시작
        update_thread = threading.Thread(
            target=self._update_energy_data,
            daemon=True
        )
        update_thread.start()

    def _update_energy_data(self):
        """
        전력량 데이터 시뮬레이션
        5초마다 L1, L2, L3 값 증가
        """
        while self.running:
            try:
                with self.lock:
                    # 0 ~ 5 사이의 랜덤값 증가 (시뮬레이션)
                    increment = random.uniform(0.5, 5.0)
                    
                    self.energy_l1 += increment
                    self.energy_l2 += increment + random.uniform(-0.5, 0.5)
                    self.energy_l3 += increment + random.uniform(-0.5, 0.5)

                time.sleep(5)

            except Exception as e:
                print(f"❌ [{self.hospital_name}] 데이터 업데이트 오류: {e}")
                time.sleep(5)

    def get_energy_value(self):
        """단상용: 전력량 값 반환 (L1 기준)"""
        with self.lock:
            return self.energy_l1

    @staticmethod
    def get_all_data():
        """
        ★★★ 3상4선 전체 데이터 반환 ★★★
        
        Returns:
            dict: {
                "meter_type": "3P4W",
                "voltage_l1": float,
                "voltage_l2": float,
                "voltage_l3": float,
                "current_l1": float,
                "current_l2": float,
                "current_l3": float,
                "power_l1": float,
                "power_l2": float,
                "power_l3": float,
                "energy_l1": float,
                "energy_l2": float,
                "energy_l3": float,
                "timestamp": str
            }
        """
        return {
            "meter_type": "3P4W",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            # ★ 전압 (V) - 기준: 230V
            "voltage_l1": 230.0 + random.uniform(-5, 5),
            "voltage_l2": 231.0 + random.uniform(-5, 5),
            "voltage_l3": 229.0 + random.uniform(-5, 5),
            
            # ★ 전류 (A) - 기준: 10A
            "current_l1": 10.0 + random.uniform(-2, 2),
            "current_l2": 11.0 + random.uniform(-2, 2),
            "current_l3": 10.0 + random.uniform(-2, 2),
            
            # ★ 유효전력 (W)
            "power_l1": 20000 + random.randint(-1000, 1000),
            "power_l2": 21000 + random.randint(-1000, 1000),
            "power_l3": 19000 + random.randint(-1000, 1000),
            
            # ★ 전력량 (kWh) - 계속 증가
            "energy_l1": 30000 + random.uniform(-1, 1),
            "energy_l2": 30001 + random.uniform(-1, 1),
            "energy_l3": 30002 + random.uniform(-1, 1),
        }

    def stop(self):
        """서버 중지"""
        self.running = False
        print(f"🛑 [{self.hospital_name}] 가상 Modbus 서버 중지")


# ★ 전역 서버 관리
_dummy_servers = {}

def create_dummy_server(hospital_name, port=502):
    """
    더미 서버 생성

    Args:
        hospital_name (str): 병원명
        port (int): 포트

    Returns:
        DummyModbusServer: 생성된 서버 인스턴스
    """
    if hospital_name not in _dummy_servers:
        server = DummyModbusServer(port=port, hospital_name=hospital_name)
        server.start()
        _dummy_servers[hospital_name] = server
    return _dummy_servers[hospital_name]

def get_dummy_server(hospital_name):
    """
    더미 서버 가져오기

    Args:
        hospital_name (str): 병원명

    Returns:
        DummyModbusServer: 서버 인스턴스 또는 None
    """
    return _dummy_servers.get(hospital_name)

def stop_all_dummy_servers():
    """모든 더미 서버 중지"""
    for server in _dummy_servers.values():
        server.stop()
    _dummy_servers.clear()
    print("✅ 모든 더미 서버 중지됨")
