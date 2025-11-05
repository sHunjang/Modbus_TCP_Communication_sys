#!/usr/bin/env python3

# core/database.py

"""
PostgreSQL + TimescaleDB 데이터베이스 관리
트랜잭션 오류 방지
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json

class DatabaseManager:
    """데이터베이스 관리자"""

    def __init__(self, config_file="config/database.json"):
        """초기화"""
        self.config = self.load_config(config_file)
        self.connection_pool = None
        self.initialize_pool()
        
        # ★ setup_base_tables()를 여러 번 시도
        for i in range(3):
            try:
                self.setup_base_tables()
                break
            except Exception as e:
                print(f"⚠️ 테이블 설정 재시도 {i+1}/3: {e}")

    def load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "host": "localhost",
                "port": 5432,
                "dbname": "hospital_power",
                "user": "postgres",
                "password": "",
                "sslmode": "prefer"
            }

    def initialize_pool(self):
        """연결 풀 초기화"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["dbname"],
                user=self.config["user"],
                password=self.config["password"],
                sslmode=self.config.get("sslmode", "prefer")
            )
            print(f"✅ DB 연결 완료: {self.config['host']}:{self.config['port']}/{self.config['dbname']}")
        except Exception as e:
            print(f"❌ DB 연결 오류: {e}")

    def setup_base_tables(self):
        """기본 테이블 설정"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print("⚠️ DB 연결 불가")
                return

            cursor = conn.cursor()

            # ★ 1. hospitals 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospitals (
                    id SERIAL PRIMARY KEY,
                    hospital_name VARCHAR(100) UNIQUE NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    hmi_ip VARCHAR(50),
                    port INT,
                    unit_id INT DEFAULT 1,
                    meter_type VARCHAR(20) DEFAULT '3P4W',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            conn.commit()
            print("✅ hospitals 테이블 준비 완료")
            
            cursor.close()

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"❌ 테이블 설정 오류: {e}")
        finally:
            if conn:
                self.release_connection(conn)

    def register_hospital(self, hospital_name, table_name, hmi_ip, port,
                         unit_id, meter_type):
        """
        병원 등록 및 테이블 생성
        ★ 각 작업마다 새 연결 사용
        """
        
        # ★ Step 1: hospitals 테이블에 등록 (새 연결)
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO hospitals
                (hospital_name, table_name, hmi_ip, port, unit_id, meter_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hospital_name) DO NOTHING
            """, (hospital_name, table_name, hmi_ip, port, unit_id, meter_type))

            conn.commit()
            cursor.close()
            self.release_connection(conn)

            if cursor.rowcount == 0:
                print(f"⚠️ {hospital_name}은 이미 등록되어 있습니다.")
                return False

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                self.release_connection(conn)
            print(f"❌ hospitals 등록 오류: {e}")
            return False

        # ★ Step 2: 병원명_1min 테이블 생성 (새 연결)
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 테이블 생성
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    time TIMESTAMP NOT NULL,
                    phase VARCHAR(10) DEFAULT 'L1',
                    power_avg NUMERIC DEFAULT 0,
                    power_max NUMERIC DEFAULT 0,
                    power_min NUMERIC DEFAULT 0,
                    energy_kwh_avg NUMERIC DEFAULT 0,
                    energy_kwh_max NUMERIC DEFAULT 0,
                    energy_kwh_min NUMERIC DEFAULT 0,
                    sample_count INT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'OK'
                )
            """)

            conn.commit()

            # 인덱스 생성
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_phase ON {table_name}(phase)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_time ON {table_name}(time DESC)")

            conn.commit()
            cursor.close()
            self.release_connection(conn)

            print(f"✅ {hospital_name} 등록 완료 (테이블: {table_name})")
            return True

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                self.release_connection(conn)
            print(f"❌ 테이블 생성 오류: {e}")
            return False

    def get_hospitals(self):
        """병원 목록 조회"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM hospitals ORDER BY id")
            hospitals = cursor.fetchall()
            cursor.close()
            self.release_connection(conn)
            return hospitals if hospitals else []
        except Exception as e:
            print(f"❌ 병원 조회 오류: {e}")
            if conn:
                self.release_connection(conn)
            return []

    def insert_energy_data(self, table_name, timestamp, phase='L1',
                           power_avg=0, power_max=0, power_min=0,
                           energy_kwh_avg=0, energy_kwh_max=0, energy_kwh_min=0,
                           sample_count=0, status='OK'):
        """에너지 데이터 삽입"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(f"""
                INSERT INTO {table_name}
                (time, phase, power_avg, power_max, power_min,
                 energy_kwh_avg, energy_kwh_max, energy_kwh_min,
                 sample_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                timestamp, str(phase),
                float(power_avg or 0), float(power_max or 0), float(power_min or 0),
                float(energy_kwh_avg or 0), float(energy_kwh_max or 0), float(energy_kwh_min or 0),
                int(sample_count or 0), str(status)
            ))

            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"❌ DB 저장 오류: {e}")
        finally:
            if conn:
                self.release_connection(conn)

    def get_connection(self):
        """연결 가져오기"""
        try:
            if self.connection_pool:
                return self.connection_pool.getconn()
        except Exception as e:
            print(f"❌ 연결 오류: {e}")
        return None

    def release_connection(self, conn):
        """연결 반환"""
        try:
            if conn and self.connection_pool:
                self.connection_pool.putconn(conn)
        except:
            pass

    def close(self):
        """연결 풀 닫기"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("✅ DB 연결 풀 종료")
