#!/usr/bin/env python3
# core/data_aggregator.py

"""
데이터 집계 - 전체전력량만
"""

from datetime import datetime
from collections import deque


class DataAggregator:
    """전체전력량 데이터 집계"""
    
    def __init__(self, hospital_name, interval_seconds=60):
        """
        초기화
        Args:
            hospital_name: 병원명
            interval_seconds: 집계 간격 (초, 기본 60초 = 1분)
        """
        self.hospital_name = hospital_name
        self.interval_seconds = interval_seconds
        self.data_buffer = deque(maxlen=1000)  # 최대 1000개
        self.last_aggregate_time = datetime.now()
    
    def add_data(self, data):
        """
        데이터 추가
        Args:
            data: {"total_energy": 123456, "timestamp": "..."}
        """
        self.data_buffer.append({
            "total_energy": data.get("total_energy", 0),
            "timestamp": data.get("timestamp", "")
        })
    
    def should_aggregate(self):
        """집계 시간인지 확인"""
        elapsed = (datetime.now() - self.last_aggregate_time).total_seconds()
        return elapsed >= self.interval_seconds and len(self.data_buffer) > 0
    
    def aggregate(self):
        """
        데이터 집계
        
        Returns:
            dict: {
                "time": "2025-11-07 17:05:00",
                "total_energy_avg": 123456,
                "total_energy_max": 123500,
                "total_energy_min": 123400,
                "sample_count": 12
            }
        """
        if len(self.data_buffer) == 0:
            return None
        
        # 전체전력량 추출
        energies = [d["total_energy"] for d in self.data_buffer]
        
        # 집계
        aggregated = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_energy_avg": sum(energies) / len(energies),
            "total_energy_max": max(energies),
            "total_energy_min": min(energies),
            "sample_count": len(energies)
        }
        
        # 버퍼 초기화
        self.data_buffer.clear()
        self.last_aggregate_time = datetime.now()
        
        return aggregated
    
    def get_latest_data(self):
        """최신 데이터 반환"""
        if len(self.data_buffer) > 0:
            return self.data_buffer[-1]
        return None
