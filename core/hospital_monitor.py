"""
병원 모니터링 클래스
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .modbus_thread import ModbusThread
from .data_aggregator import DataAggregator
from .db_writer import DBWriterThread
from .dummy_modbus_server import create_dummy_server


class HospitalMonitor(QObject):
    """병원 모니터링 (전체전력량만)"""
    
    data_updated = pyqtSignal(str, dict)
    
    def __init__(self, hospital_info, database, use_dummy=False):
        """초기화"""
        super().__init__()
        self.hospital_info = hospital_info
        self.database = database
        self.hospital_name = hospital_info['hospital_name']
        self.table_name = hospital_info['table_name']
        
        # 더미 서버 생성 (더미 모드일 때)
        if use_dummy:
            try:
                create_dummy_server(self.hospital_name, port=5020 + hash(self.hospital_name) % 100)
            except:
                pass
        
        # 데이터 집계기
        self.aggregator = DataAggregator(self.hospital_name)
        
        # Modbus TCP 통신 스레드
        self.modbus_thread = ModbusThread(
            hospital_name=self.hospital_name,
            hmi_ip=hospital_info['hmi_ip'],
            port=hospital_info['port'],
            unit_id=hospital_info.get('unit_id', 128),
            meter_type=hospital_info.get('meter_type', '3P4W'),
            use_dummy=use_dummy
        )
        
        # DB 저장 스레드
        self.db_writer = DBWriterThread(
            database=self.database,
            aggregator=self.aggregator,
            table_name=self.table_name,
            hospital_name=self.hospital_name
        )
        
        # 최신 전체전력량
        self.latest_total_energy = None
    
    def start(self):
        """모니터링 시작"""
        self.modbus_thread.data_received.connect(self.on_data_received)
        self.modbus_thread.start()
        self.db_writer.start()
    
    def stop(self):
        """모니터링 중지"""
        self.modbus_thread.stop()
        self.modbus_thread.wait()
        self.db_writer.stop()
        self.db_writer.wait()
    
    @pyqtSlot(dict)
    def on_data_received(self, data_dict):
        """
        데이터 수신 (전체전력량만)
        Args:
            data_dict: {
                "total_energy": 654321,
                "timestamp": "2025-11-07 17:05:00"
            }
        """
        try:
            if isinstance(data_dict, dict):
                # 집계기에 데이터 전달
                self.aggregator.add_data(data_dict)
                
                # 최신 전체전력량 저장
                if 'energy_total' in data_dict:
                    self.latest_total_energy = data_dict['energy_total']
                elif 'total_energy' in data_dict:
                    self.latest_total_energy = data_dict['total_energy']
        
        except Exception as e:
            print(f"❌ on_data_received 오류: {e}")
