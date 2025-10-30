#!/usr/bin/env python3
# core/db_writer.py
"""
DB 저장 전용 스레드
1분마다 집계된 데이터를 PostgreSQL에 저장
"""

from PyQt6.QtCore import QThread, pyqtSignal
import time


class DBWriterThread(QThread):
    """
    DB 저장 스레드
    1분마다 집계된 데이터를 DB에 저장
    """
    
    # PyQt Signal
    log_message = pyqtSignal(str)
    db_saved = pyqtSignal(str, dict)  # (병원명, 저장된 데이터)
    
    def __init__(self, database, aggregator, table_name, hospital_name):
        """
        초기화 함수
        
        Args:
            database: DatabaseManager 인스턴스
            aggregator: DataAggregator 인스턴스
            table_name (str): DB 테이블명
            hospital_name (str): 병원명
        """
        super().__init__()
        
        self.database = database
        self.aggregator = aggregator
        self.table_name = table_name
        self.hospital_name = hospital_name
        
        self.running = False
    
    def run(self):
        """스레드 메인 루프"""
        self.running = True
        
        self.log_message.emit(f"💾 {self.hospital_name} DB 저장 시작")
        
        while self.running:
            try:
                # 1분 경과 체크
                if self.aggregator.should_aggregate():
                    # 데이터 집계
                    aggregated_data = self.aggregator.aggregate()
                    
                    if aggregated_data:
                        # DB에 저장
                        success = self.database.insert_energy_data(
                            self.table_name,
                            aggregated_data
                        )
                        
                        if success:
                            self.log_message.emit(
                                f"💾 {self.hospital_name} DB 저장 완료 "
                                f"(평균: {aggregated_data['energy_kwh_avg']:.2f} kWh)"
                            )
                            self.db_saved.emit(self.hospital_name, aggregated_data)
                        else:
                            self.log_message.emit(f"❌ {self.hospital_name} DB 저장 실패")
                
                # 10초마다 체크 (1분이 안 되면 skip)
                time.sleep(10)
            
            except Exception as e:
                self.log_message.emit(f"❌ {self.hospital_name} DB 저장 오류: {e}")
                time.sleep(10)
        
        self.log_message.emit(f"🛑 {self.hospital_name} DB 저장 종료")
    
    def stop(self):
        """스레드 중지"""
        self.running = False
