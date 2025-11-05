#!/usr/bin/env python3
# core/data_aggregator.py
"""
데이터 집계기 (3상 4선 완전 지원)  ★ 수정됨
- 5초 주기 데이터를 메모리에 버퍼링
- 1분마다 L1, L2, L3의 전력(kW)과 전력량(kWh) 각각 집계  ★ 수정됨
- 전체 유효전력과 전체 전력량 계산  ★ 수정됨
"""


from datetime import datetime
from collections import deque
import threading



class DataAggregator:
    """
    3상 4선 데이터 집계기  ★ 수정됨
    L1, L2, L3: 전력(power) + 전력량(energy)  ★ 수정됨
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
    
    def add_data(self, data_dict):  # ★ 수정: energy_kwh → data_dict
        """
        5초 주기 데이터 추가
        
        Args:
            data_dict (dict): {  # ★ 수정: 전체 dict 수신
                "power_l1": 20000, "power_l2": 21000, "power_l3": 19000,
                "energy_l1": 30000, "energy_l2": 30001, "energy_l3": 30002,
                ...
            }
        """
        with self.lock:
            # ★ 수정: 필요한 값만 추출해서 저장
            extracted_data = {
                'timestamp': datetime.now(),
                'power_l1': data_dict.get('power_l1', 0),  # ★ 수정
                'power_l2': data_dict.get('power_l2', 0),  # ★ 수정
                'power_l3': data_dict.get('power_l3', 0),  # ★ 수정
                'energy_l1': data_dict.get('energy_l1', 0),  # ★ 수정
                'energy_l2': data_dict.get('energy_l2', 0),  # ★ 수정
                'energy_l3': data_dict.get('energy_l3', 0),  # ★ 수정
            }
            self.buffer.append(extracted_data)
    
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
        1분 평균 계산 (3상 4선 완전 버전)  ★ 수정됨
        
        Returns:
            dict: 집계 데이터 또는 None
        """
        with self.lock:
            # 버퍼가 비어있으면 None
            if len(self.buffer) == 0:
                return None
            
            # ★ 수정: 각 상(phase)별 리스트 생성
            power_l1_list = []
            power_l2_list = []
            power_l3_list = []
            energy_l1_list = []
            energy_l2_list = []
            energy_l3_list = []

            for item in self.buffer:
                power_l1_list.append(item.get('power_l1', 0))  # ★ 수정
                power_l2_list.append(item.get('power_l2', 0))  # ★ 수정
                power_l3_list.append(item.get('power_l3', 0))  # ★ 수정
                energy_l1_list.append(item.get('energy_l1', 0))  # ★ 수정
                energy_l2_list.append(item.get('energy_l2', 0))  # ★ 수정
                energy_l3_list.append(item.get('energy_l3', 0))  # ★ 수정
            
            # ★ 수정: 3상 데이터 모두 집계
            aggregated = {
                'time': datetime.now(),
                'sample_count': len(self.buffer),
                'status': 'OK'
            }

            # ★ 수정: L1 전력 (W) 집계
            aggregated.update({
                'power_l1_avg': sum(power_l1_list) / len(power_l1_list),
                'power_l1_max': max(power_l1_list),
                'power_l1_min': min(power_l1_list),
            })

            # ★ 수정: L2 전력 (W) 집계
            aggregated.update({
                'power_l2_avg': sum(power_l2_list) / len(power_l2_list),
                'power_l2_max': max(power_l2_list),
                'power_l2_min': min(power_l2_list),
            })

            # ★ 수정: L3 전력 (W) 집계
            aggregated.update({
                'power_l3_avg': sum(power_l3_list) / len(power_l3_list),
                'power_l3_max': max(power_l3_list),
                'power_l3_min': min(power_l3_list),
            })

            # ★ 수정: 전체 전력 (3상 합계)
            aggregated.update({
                'power_total_avg': (
                    aggregated['power_l1_avg'] +
                    aggregated['power_l2_avg'] +
                    aggregated['power_l3_avg']
                ),
            })

            # ★ 수정: L1 전력량 (kWh) 집계
            aggregated.update({
                'energy_l1_avg': sum(energy_l1_list) / len(energy_l1_list),
                'energy_l1_max': max(energy_l1_list),
                'energy_l1_min': min(energy_l1_list),
            })

            # ★ 수정: L2 전력량 (kWh) 집계
            aggregated.update({
                'energy_l2_avg': sum(energy_l2_list) / len(energy_l2_list),
                'energy_l2_max': max(energy_l2_list),
                'energy_l2_min': min(energy_l2_list),
            })

            # ★ 수정: L3 전력량 (kWh) 집계
            aggregated.update({
                'energy_l3_avg': sum(energy_l3_list) / len(energy_l3_list),
                'energy_l3_max': max(energy_l3_list),
                'energy_l3_min': min(energy_l3_list),
            })

            # ★ 수정: 전체 전력량 (3상 합계)
            aggregated.update({
                'energy_total_avg': (
                    aggregated['energy_l1_avg'] +
                    aggregated['energy_l2_avg'] +
                    aggregated['energy_l3_avg']
                ),
            })
            
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
        """최신 데이터 반환 (GUI 표시용)"""  # ★ 수정 필요
        with self.lock:
            if len(self.buffer) > 0:
                # ★ 수정: energy_l1 반환 (단상용에서 3상용으로)
                return self.buffer[-1].get('energy_l1', 0)
            return None
