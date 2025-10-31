#!/usr/bin/env python3
# core/dummy_modbus_server.py
"""
더미 Modbus 서버
가상 전력량 데이터 생성 및 Modbus 통신 시뮬레이션
"""

import threading
import time
from datetime import datetime
import random


class DummyModbusServer:
    """
    가상 Modbus 서버
    - TCP 소켓으로 Modbus 요청 처리
    - 시뮬레이션 전력량 데이터 생성
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
        
        # 시뮬레이션 데이터
        self.energy_value = 1000.0  # 초기 전력량 (kWh)
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
        5초마다 랜덤 값 증가
        """
        while self.running:
            try:
                with self.lock:
                    # 0 ~ 50 사이의 랜덤값 증가 (시뮬레이션)
                    increment = random.uniform(0.5, 50.0)
                    self.energy_value += increment
                    
                    # 로그 출력 (선택사항)
                    print(f"  [{self.hospital_name}] 전력량: {self.energy_value:.2f} kWh")
                
                time.sleep(5)  # 5초마다 업데이트
            
            except Exception as e:
                print(f"❌ [{self.hospital_name}] 데이터 업데이트 오류: {e}")
    
    def get_energy_value(self):
        """
        현재 전력량 값 반환
        
        Returns:
            float: 유효전력량 (kWh)
        """
        with self.lock:
            return self.energy_value
    
    def stop(self):
        """서버 중지"""
        self.running = False
        print(f"🛑 [{self.hospital_name}] 가상 Modbus 서버 중지")


# 글로벌 더미 서버 딕셔너리
_dummy_servers = {}


def create_dummy_server(hospital_name, port=502):
    """
    더미 서버 생성
    
    Args:
        hospital_name (str): 병원명
        port (int): 포트
    
    Returns:
        DummyModbusServer: 더미 서버 인스턴스
    """
    server = DummyModbusServer(port=port, hospital_name=hospital_name)
    server.start()
    _dummy_servers[hospital_name] = server
    return server


def get_dummy_server(hospital_name):
    """
    더미 서버 조회
    
    Args:
        hospital_name (str): 병원명
    
    Returns:
        DummyModbusServer: 더미 서버 인스턴스 또는 None
    """
    return _dummy_servers.get(hospital_name)


def stop_all_dummy_servers():
    """모든 더미 서버 중지"""
    for server in _dummy_servers.values():
        server.stop()
    _dummy_servers.clear()
