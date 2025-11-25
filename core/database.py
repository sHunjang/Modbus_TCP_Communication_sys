#!/usr/bin/env python3
# core/database.py

"""
PostgreSQL 데이터베이스 관리
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
import sys
import os
from pathlib import Path


class DatabaseManager:
    """PostgreSQL 데이터베이스 관리자"""

    def __init__(self, config_file="config/database.json"):
        """
        초기화
        
        Args:
            config_file: DB 설정 파일 경로
        """
        self.config = self.load_config(config_file)
        self.connection_pool = None
        self.db_available = False
        
        self.initialize_pool()

        if self.db_available:
            self.setup_base_tables()

    def load_config(self, config_file):
        """
        설정 파일 로드 (PyInstaller 경로 처리)
        
        Args:
            config_file: 설정 파일 경로
        
        Returns:
            dict: DB 설정
        """
        # PyInstaller 실행 파일 경로 처리
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 실행 파일
            # sys._MEIPASS: 임시 압축 해제 폴더
            base_path = sys._MEIPASS
        else:
            # 개발 환경
            base_path = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.dirname(base_path)  # 프로젝트 루트로
        
        config_path = os.path.join(base_path, config_file)
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                print(f"✅ 설정 파일 로드: {config_path}")
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {config_path} 없음, 기본값 사용")
            return {
                "host": "localhost",
                "port": 5432,
                "dbname": "hospital_power",
                "user": "postgres",
                "password": "1234",
                "sslmode": "prefer",
            }
        except Exception as e:
            print(f"⚠️ 설정 로드 오류: {e}, 기본값 사용")
            return {
                "host": "localhost",
                "port": 5432,
                "dbname": "hospital_power",
                "user": "postgres",
                "password": "1234",
                "sslmode": "prefer",
            }

    def initialize_pool(self):
        """연결 풀 초기화"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1,
                20,
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["dbname"],
                user=self.config["user"],
                password=self.config["password"],
                sslmode=self.config.get("sslmode", "prefer"),
            )
            self.db_available = True
            print(f"✅ DB 연결: {self.config['host']}:{self.config['port']}/{self.config['dbname']}")
        except Exception as e:
            self.db_available = False
            print(f"❌ DB 연결 오류: {e}")

    def setup_base_tables(self):
        """기본 테이블 생성"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospitals (
                    id SERIAL PRIMARY KEY,
                    hospital_key VARCHAR(100) UNIQUE NOT NULL,
                    ip_address VARCHAR(50),
                    port INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            cursor.close()
            print("✅ hospitals 테이블 준비 완료")

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ 테이블 설정 오류: {e}")
        finally:
            if conn:
                self.release_connection(conn)

    # ... (나머지 메서드는 동일)
    
    def get_connection(self):
        """연결 풀에서 연결 가져오기"""
        if not self.db_available or not self.connection_pool:
            return None
        try:
            return self.connection_pool.getconn()
        except Exception as e:
            print(f"❌ 연결 가져오기 오류: {e}")
            return None

    def release_connection(self, conn):
        """연결 풀에 연결 반환"""
        if self.connection_pool:
            self.connection_pool.putconn(conn)

    def close(self):
        """연결 풀 닫기"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("✅ DB 연결 풀 닫힘")

    def register_hospital(self, hospital_key: str, ip_address: str, port: int):
        """병원 등록 및 데이터 테이블 생성"""
        if not self.db_available:
            return False

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM hospitals WHERE hospital_key = %s",
                (hospital_key,),
            )
            if cursor.fetchone():
                cursor.close()
                self.release_connection(conn)
                return True

            cursor.execute(
                """
                INSERT INTO hospitals (hospital_key, ip_address, port)
                VALUES (%s, %s, %s)
                """,
                (hospital_key, ip_address, port),
            )
            conn.commit()
            cursor.close()
            self.release_connection(conn)

        except Exception as e:
            if conn:
                conn.rollback()
                self.release_connection(conn)
            print(f"❌ hospitals 등록 오류: {e}")
            return False

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    value NUMERIC(15, 2) NOT NULL,
                    hex_data TEXT
                )
            """)
            conn.commit()

            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp "
                f"ON {table_name}(timestamp DESC)"
            )
            conn.commit()

            cursor.close()
            self.release_connection(conn)

            print(f"✅ {hospital_key} 등록 완료 (테이블: {table_name})")
            return True

        except Exception as e:
            if conn:
                conn.rollback()
                self.release_connection(conn)
            print(f"❌ 테이블 생성 오류: {e}")
            return False

    def insert_data(self, hospital_key: str, timestamp: str, value: float, hex_data: str = None):
        """데이터 저장"""
        if not self.db_available:
            return

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                f"""
                INSERT INTO {table_name} (timestamp, value, hex_data)
                VALUES (%s, %s, %s)
                """,
                (timestamp, value, hex_data),
            )
            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ DB 저장 오류: {e}")
        finally:
            if conn:
                self.release_connection(conn)

    def get_hospitals(self):
        """등록된 병원 목록 조회"""
        if not self.db_available:
            return []

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("SELECT * FROM hospitals ORDER BY id")
            hospitals = cursor.fetchall()
            
            cursor.close()
            self.release_connection(conn)
            
            return [dict(h) for h in hospitals]
        
        except Exception as e:
            print(f"❌ 병원 목록 조회 오류: {e}")
            return []
