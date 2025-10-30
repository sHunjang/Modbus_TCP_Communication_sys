#!/usr/bin/env python3
# core/data_aggregator.py
"""
데이터 집계기 (단순화 버전)
- 5초 주기 데이터를 메모리에 버퍼링
- 1분마다 유효전력량(kWh) 평균/최대/최소 계산
"""

from datetime import datetime
from collections import deque
import threading


class DataAggregator:
    """
    단순 데이터 집계기
    유효전력량(kWh) 1개 항목만 처리
    """
    
    def __init__(self, hospital_name):
        """
        초기화 함수
        
        Args:
            hospital_name (str): 병원명
        """
        self.hospital_name = hospital_name
        
        # 데이터 버퍼 (최대 12개 = 60초, 5초 주기)
        self.buffer = deque(maxlen=12)
        
        # 스레드 Lock
        self.lock = threading.Lock()
        
        # 마지막 집계 시간
        self.last_aggregation_time = None
    
    def add_data(self, energy_kwh):
        """
        5초 주기 데이터 추가
        
        Args:
            energy_kwh (float): 유효전력량 (kWh)
        """
        with self.lock:
            self.buffer.append({
                'timestamp': datetime.now(),
                'energy_kwh': energy_kwh
            })
    
    def should_aggregate(self):
        """
        집계 수행 여부 (1분 경과 체크)
        
        Returns:
            bool: True면 집계 필요
        """
        now = datetime.now()
        
        # 첫 실행
        if self.last_aggregation_time is None:
            return True
        
        # 1분 경과 체크
        elapsed_seconds = (now - self.last_aggregation_time).total_seconds()
        return elapsed_seconds >= 60
    
    def aggregate(self):
        """
        1분 평균 계산
        
        Returns:
            dict: 집계 데이터 또는 None
        """
        with self.lock:
            # 버퍼가 비어있으면 None
            if len(self.buffer) == 0:
                return None
            
            # 유효전력량 리스트 추출
            energy_values = [item['energy_kwh'] for item in self.buffer]
            
            # 평균, 최대, 최소 계산
            aggregated = {
                'time': datetime.now(),
                'energy_kwh_avg': sum(energy_values) / len(energy_values),
                'energy_kwh_max': max(energy_values),
                'energy_kwh_min': min(energy_values),
                'sample_count': len(self.buffer),
                'status': 'OK'
            }
            
            # 버퍼 초기화
            self.buffer.clear()
            
            # 마지막 집계 시간 업데이트
            self.last_aggregation_time = datetime.now()
            
            return aggregated
    
    def get_buffer_size(self):
        """현재 버퍼 크기"""
        with self.lock:
            return len(self.buffer)
    
    def get_latest_value(self):
        """최신 데이터 반환 (GUI 표시용)"""
        with self.lock:
            if len(self.buffer) > 0:
                return self.buffer[-1]['energy_kwh']
            return None
