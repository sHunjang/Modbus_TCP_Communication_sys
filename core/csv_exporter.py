#!/usr/bin/env python3
# core/csv_exporter.py
"""
CSV 내보내기 기능
지정된 기간의 데이터를 CSV로 저장
"""

import csv
import os
from datetime import datetime
from pathlib import Path


class CSVExporter:
    """CSV 내보내기 클래스"""
    
    def __init__(self, export_dir="exports"):
        """
        초기화
        
        Args:
            export_dir (str): 내보내기 디렉토리
        """
        self.export_dir = export_dir
        
        # 디렉토리 생성
        Path(self.export_dir).mkdir(exist_ok=True)
    
    def export_hospital_data(self, database, table_name, hospital_name, 
                            start_datetime, end_datetime):
        """
        병원 데이터를 CSV로 내보내기
        
        Args:
            database: DatabaseManager 인스턴스
            table_name (str): 테이블명
            hospital_name (str): 병원명
            start_datetime (datetime): 시작 시간
            end_datetime (datetime): 종료 시간
        
        Returns:
            tuple: (성공 여부, 파일경로, 메시지)
        """
        
        try:
            # DB에서 데이터 조회
            conn = database.get_connection()
            cursor = conn.cursor()
            
            # ✨ 기간 내 데이터 조회
            query = f"""
                SELECT 
                    time,
                    energy_kwh_avg,
                    energy_kwh_max,
                    energy_kwh_min,
                    sample_count,
                    status
                FROM {table_name}
                WHERE time >= %s AND time <= %s
                ORDER BY time ASC
            """
            
            cursor.execute(query, (start_datetime, end_datetime))
            rows = cursor.fetchall()
            
            cursor.close()
            database.release_connection(conn)
            
            if not rows:
                return False, None, f"해당 기간에 데이터가 없습니다."
            
            # CSV 파일명 생성
            start_str = start_datetime.strftime("%Y%m%d_%H%M%S")
            end_str = end_datetime.strftime("%Y%m%d_%H%M%S")
            filename = f"{hospital_name}_{start_str}_to_{end_str}.csv"
            filepath = os.path.join(self.export_dir, filename)
            
            # CSV 파일 생성
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # 헤더
                writer.writerow([
                    "시간",
                    "평균 전력량 (kWh)",
                    "최대 전력량 (kWh)",
                    "최소 전력량 (kWh)",
                    "샘플 수",
                    "상태"
                ])
                
                # 데이터
                for row in rows:
                    time_str = row[0].strftime("%Y-%m-%d %H:%M:%S") if row[0] else ""
                    writer.writerow([
                        time_str,
                        f"{row[1]:.2f}" if row[1] else "",
                        f"{row[2]:.2f}" if row[2] else "",
                        f"{row[3]:.2f}" if row[3] else "",
                        row[4] if row[4] else "",
                        row[5] if row[5] else ""
                    ])
            
            # 통계
            data_count = len(rows)
            total_energy = sum(row[1] for row in rows if row[1])
            avg_energy = total_energy / data_count if data_count > 0 else 0
            
            message = f"{hospital_name} 데이터 {data_count}건 내보냄 (평균: {avg_energy:.2f} kWh)"
            
            return True, filepath, message
        
        except Exception as e:
            return False, None, f"CSV 내보내기 오류: {e}"
    
    def export_all_hospitals(self, database, hospitals_info, 
                            start_datetime, end_datetime):
        """
        모든 병원 데이터를 CSV로 내보내기
        
        Args:
            database: DatabaseManager 인스턴스
            hospitals_info (list): 병원 정보 리스트
            start_datetime (datetime): 시작 시간
            end_datetime (datetime): 종료 시간
        
        Returns:
            tuple: (성공 여부, 파일경로 리스트, 메시지 리스트)
        """
        
        results = []
        filepaths = []
        
        for hospital in hospitals_info:
            success, filepath, message = self.export_hospital_data(
                database,
                hospital['table_name'],
                hospital['hospital_name'],
                start_datetime,
                end_datetime
            )
            
            results.append((success, message))
            if success:
                filepaths.append(filepath)
        
        return results, filepaths
    
    def get_export_files(self):
        """
        내보낸 파일 목록 조회
        
        Returns:
            list: CSV 파일 목록
        """
        
        if not os.path.exists(self.export_dir):
            return []
        
        files = []
        for file in os.listdir(self.export_dir):
            if file.endswith('.csv'):
                filepath = os.path.join(self.export_dir, file)
                file_size = os.path.getsize(filepath)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                files.append({
                    'name': file,
                    'path': filepath,
                    'size': file_size,
                    'time': file_time
                })
        
        return sorted(files, key=lambda x: x['time'], reverse=True)
