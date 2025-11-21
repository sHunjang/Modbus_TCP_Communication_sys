#!/usr/bin/env python3
# core/csv_exporter.py

"""
CSV 내보내기 기능

기능:
- 지정된 기간의 병원별 10초 단위 데이터를 CSV로 저장
- 간단한 통계 계산 (평균/최대/최소)
- 내보낸 파일 목록 조회
- 파일 삭제
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
            export_dir (str): CSV 파일을 저장할 디렉토리 경로
        """
        self.export_dir = export_dir
        # 디렉토리가 없으면 생성
        Path(self.export_dir).mkdir(exist_ok=True)

    def export_hospital_data(
        self,
        database,
        hospital_name,
        start_datetime,
        end_datetime,
    ):
        """
        특정 병원의 기간 내 데이터를 CSV로 내보내기
        
        Args:
            database: DatabaseManager 인스턴스
            hospital_name (str): 병원명 (예: "ICN")
            start_datetime (datetime): 시작 시각
            end_datetime (datetime): 종료 시각
        
        Returns:
            tuple: (성공 여부(bool), 파일경로(str 또는 None), 메시지(str))
        """
        try:
            # 테이블명 생성
            table_name = f"hospital_{hospital_name.replace('.', '_').replace(':', '_')}"
            
            # DB에서 데이터 조회
            conn = database.get_connection()
            if not conn:
                return False, None, "DB 연결 실패"
            
            cursor = conn.cursor()

            # 기간 내 데이터 조회 쿼리 (10초 단위)
            query = f"""
                SELECT
                    timestamp,
                    value,
                    hex_data
                FROM {table_name}
                WHERE timestamp >= %s AND timestamp <= %s
                ORDER BY timestamp ASC
            """
            cursor.execute(query, (start_datetime, end_datetime))
            rows = cursor.fetchall()
            cursor.close()
            database.release_connection(conn)

            # 데이터가 없는 경우
            if not rows:
                return False, None, "해당 기간에 데이터가 없습니다."

            # CSV 파일명 생성
            # 예: ICN_20251121_160000_to_20251121_170000.csv
            start_str = start_datetime.strftime("%Y%m%d_%H%M%S")
            end_str = end_datetime.strftime("%Y%m%d_%H%M%S")
            filename = f"{hospital_name}_{start_str}_to_{end_str}.csv"
            filepath = os.path.join(self.export_dir, filename)

            # CSV 파일 생성
            with open(filepath, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)

                # 헤더 (컬럼명)
                writer.writerow(
                    ["시간", "전력량 (kWh)", "HEX 데이터"]
                )

                # 데이터 행 작성
                for row in rows:
                    timestamp = row[0]
                    value = row[1]
                    hex_data = row[2] if row[2] else ""
                    
                    # 시간 포맷팅
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
                    
                    # 전력량 포맷팅 (소수점 2자리)
                    value_str = f"{float(value):.2f}" if value else ""
                    
                    writer.writerow([time_str, value_str, hex_data])

            # 간단 통계 계산
            data_count = len(rows)
            total_energy = sum(float(row[1]) for row in rows if row[1])
            avg_energy = total_energy / data_count if data_count > 0 else 0
            max_energy = max(float(row[1]) for row in rows if row[1]) if data_count > 0 else 0
            min_energy = min(float(row[1]) for row in rows if row[1]) if data_count > 0 else 0

            # 결과 메시지
            message = (
                f"{hospital_name} 데이터 {data_count}건 내보냄\n"
                f"평균: {avg_energy:.2f} kWh, "
                f"최대: {max_energy:.2f} kWh, "
                f"최소: {min_energy:.2f} kWh"
            )

            return True, filepath, message

        except Exception as e:
            return False, None, f"CSV 내보내기 오류: {e}"

    def export_all_hospitals(
        self, 
        database, 
        hospital_names: list, 
        start_datetime, 
        end_datetime
    ):
        """
        모든 병원 데이터를 한 번에 CSV로 내보내기
        
        Args:
            database: DatabaseManager 인스턴스
            hospital_names (list[str]): 병원명 리스트 (예: ["ICN", "SEL", "BUS"])
            start_datetime (datetime): 시작 시간
            end_datetime (datetime): 종료 시간
        
        Returns:
            tuple: (결과 리스트[(bool, msg)], 파일경로 리스트[str])
        """
        results = []
        filepaths = []

        for hospital_name in hospital_names:
            success, filepath, message = self.export_hospital_data(
                database,
                hospital_name,
                start_datetime,
                end_datetime,
            )
            results.append((success, message))
            if success:
                filepaths.append(filepath)

        return results, filepaths

    def get_export_files(self):
        """
        내보낸 CSV 파일 목록 조회
        
        Returns:
            list[dict]: 파일 정보 리스트
                - name: 파일명
                - path: 전체 경로
                - size: 바이트 크기
                - size_mb: MB 크기
                - time: 수정 시각
        """
        if not os.path.exists(self.export_dir):
            return []

        files = []
        for file in os.listdir(self.export_dir):
            if file.endswith(".csv"):
                filepath = os.path.join(self.export_dir, file)
                
                # 파일 정보 가져오기
                file_size = os.path.getsize(filepath)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                files.append(
                    {
                        "name": file,
                        "path": filepath,
                        "size": file_size,
                        "size_mb": f"{file_size / 1024 / 1024:.2f} MB",
                        "time": file_time,
                    }
                )

        # 시간 기준 내림차순 정렬 (최신 파일 먼저)
        return sorted(files, key=lambda x: x["time"], reverse=True)

    def delete_export_file(self, filepath: str) -> bool:
        """
        CSV 파일 삭제
        
        Args:
            filepath: 삭제할 파일 경로
        
        Returns:
            bool: 성공 여부
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            print(f"❌ 파일 삭제 오류: {e}")
            return False

    def get_file_info(self, filepath: str) -> dict:
        """
        특정 CSV 파일의 정보 조회
        
        Args:
            filepath: 파일 경로
        
        Returns:
            dict: 파일 정보 또는 None
        """
        try:
            if not os.path.exists(filepath):
                return None
            
            file_size = os.path.getsize(filepath)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            # CSV 파일 행 수 세기
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                row_count = sum(1 for _ in f) - 1  # 헤더 제외
            
            return {
                "name": os.path.basename(filepath),
                "path": filepath,
                "size": file_size,
                "size_mb": f"{file_size / 1024 / 1024:.2f} MB",
                "time": file_time,
                "row_count": row_count,
            }
        except Exception as e:
            print(f"❌ 파일 정보 조회 오류: {e}")
            return None
