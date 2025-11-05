#!/usr/bin/env python3

# core/db_writer.py

from PyQt6.QtCore import QThread, pyqtSignal
import time

class DBWriterThread(QThread):
    """3상 4선 데이터 DB 저장 스레드"""

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
                        self._save_to_database(aggregated_data)
                        self.db_saved.emit(self.hospital_name, aggregated_data)

                time.sleep(5)

            except Exception as e:
                self.log_message.emit(f"❌ {self.hospital_name} DB 저장 오류: {e}")
                time.sleep(5)

    def _save_to_database(self, aggregated_data):
        """
        DB에 저장 (L1, L2, L3, TOTAL 각각)
        
        ★ 개별 값을 extract해서 전달!
        """
        try:
            timestamp = aggregated_data['time']

            # ★ L1 저장
            self.database.insert_energy_data(
                table_name=self.table_name,
                timestamp=timestamp,
                phase='L1',
                power_avg=aggregated_data.get('power_l1_avg', 0),
                power_max=aggregated_data.get('power_l1_max', 0),
                power_min=aggregated_data.get('power_l1_min', 0),
                energy_kwh_avg=aggregated_data.get('energy_l1_avg', 0),
                energy_kwh_max=aggregated_data.get('energy_l1_max', 0),
                energy_kwh_min=aggregated_data.get('energy_l1_min', 0),
                sample_count=aggregated_data.get('sample_count', 0),
                status=aggregated_data.get('status', 'OK')
            )

            # ★ L2 저장
            self.database.insert_energy_data(
                table_name=self.table_name,
                timestamp=timestamp,
                phase='L2',
                power_avg=aggregated_data.get('power_l2_avg', 0),
                power_max=aggregated_data.get('power_l2_max', 0),
                power_min=aggregated_data.get('power_l2_min', 0),
                energy_kwh_avg=aggregated_data.get('energy_l2_avg', 0),
                energy_kwh_max=aggregated_data.get('energy_l2_max', 0),
                energy_kwh_min=aggregated_data.get('energy_l2_min', 0),
                sample_count=aggregated_data.get('sample_count', 0),
                status=aggregated_data.get('status', 'OK')
            )

            # ★ L3 저장
            self.database.insert_energy_data(
                table_name=self.table_name,
                timestamp=timestamp,
                phase='L3',
                power_avg=aggregated_data.get('power_l3_avg', 0),
                power_max=aggregated_data.get('power_l3_max', 0),
                power_min=aggregated_data.get('power_l3_min', 0),
                energy_kwh_avg=aggregated_data.get('energy_l3_avg', 0),
                energy_kwh_max=aggregated_data.get('energy_l3_max', 0),
                energy_kwh_min=aggregated_data.get('energy_l3_min', 0),
                sample_count=aggregated_data.get('sample_count', 0),
                status=aggregated_data.get('status', 'OK')
            )

            # ★ TOTAL 저장
            self.database.insert_energy_data(
                table_name=self.table_name,
                timestamp=timestamp,
                phase='TOTAL',
                power_avg=aggregated_data.get('power_total_avg', 0),
                energy_kwh_avg=aggregated_data.get('energy_total_avg', 0),
                sample_count=aggregated_data.get('sample_count', 0),
                status=aggregated_data.get('status', 'OK')
            )

            self.log_message.emit(f"✅ {self.hospital_name} DB 저장 완료")

        except Exception as e:
            self.log_message.emit(f"❌ DB 저장 오류: {e}")

    def stop(self):
        """스레드 중지"""
        self.running = False
