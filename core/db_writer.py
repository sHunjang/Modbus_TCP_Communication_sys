#!/usr/bin/env python3
# core/db_writer.py

"""
DB 저장 - 전체전력량만
"""

from PyQt6.QtCore import QThread, pyqtSignal
import time


class DBWriterThread(QThread):
    """전체전력량 DB 저장 스레드"""
    
    log_message = pyqtSignal(str)
    db_saved = pyqtSignal(str, dict)
    
    def __init__(self, database, aggregator, table_name, hospital_name):
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
                if self.aggregator.should_aggregate():
                    aggregated_data = self.aggregator.aggregate()
                    
                    if aggregated_data:
                        if self.database.db_available:
                            self._save_to_database(aggregated_data)
                        
                        self.db_saved.emit(self.hospital_name, aggregated_data)
                
                time.sleep(5)
            
            except Exception as e:
                self.log_message.emit(f"❌ {self.hospital_name} DB 저장 오류: {e}")
                time.sleep(5)
    
    def _save_to_database(self, aggregated_data):
        """DB에 저장 (전체전력량만)"""
        try:
            timestamp = aggregated_data['time']
            
            self.database.insert_energy_data(
                table_name=self.table_name,
                timestamp=timestamp,
                phase="TOTAL",
                energy_kwh_avg=aggregated_data.get('total_energy_avg', 0),
                energy_kwh_max=aggregated_data.get('total_energy_max', 0),
                energy_kwh_min=aggregated_data.get('total_energy_min', 0),
                sample_count=aggregated_data.get('sample_count', 0),
                status="OK"
            )
            
            self.log_message.emit(f"✅ {self.hospital_name} DB 저장 완료")
        
        except Exception as e:
            self.log_message.emit(f"❌ DB 저장 오류: {e}")
    
    def stop(self):
        """스레드 중지"""
        self.running = False
