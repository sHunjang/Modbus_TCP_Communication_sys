#!/usr/bin/env python3
# core/database.py

"""
PostgreSQL 데이터베이스 관리

기능:
- 병원 정보 테이블 관리 (hospitals)
- 병원별 데이터 테이블 자동 생성 (hospital_병원명)
- 10초 단위 전력량 데이터 저장
- 연결 풀 관리
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
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
        
        # 연결 풀 초기화
        self.initialize_pool()

        # 기본 테이블 생성
        if self.db_available:
            self.setup_base_tables()

    def load_config(self, config_file):
        """
        설정 파일 로드
        
        Args:
            config_file: 설정 파일 경로
        
        Returns:
            dict: DB 설정
        """
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {config_file} 없음, 기본값 사용")
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
        """
        연결 풀 초기화
        
        - 최소 1개, 최대 20개 연결 유지
        - 연결 실패 시 db_available = False
        """
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # 최소 연결 수
                20,  # 최대 연결 수
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
            print(f"   호스트: {self.config['host']}:{self.config['port']}")
            print(f"   데이터베이스: {self.config['dbname']}")
            print(f"   사용자: {self.config['user']}")

    def setup_base_tables(self):
        """
        기본 테이블(hospitals) 생성
        
        hospitals 테이블:
        - id: 병원 ID (자동 증가)
        - hospital_key: 병원 식별자 (예: "ICN")
        - ip_address: HMI IP 주소
        - port: HMI 포트
        - created_at: 등록 시각
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # 병원 목록 테이블 생성
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

    def register_hospital(self, hospital_key: str, ip_address: str, port: int):
        """
        병원 등록 및 데이터 테이블 생성
        
        Args:
            hospital_key: 병원 식별자 (예: "ICN")
            ip_address: HMI IP 주소
            port: HMI 포트 번호
        
        Returns:
            bool: 성공 여부
        """
        if not self.db_available:
            return False

        # 테이블명 생성 (특수문자 제거)
        # 예: "ICN" → "hospital_ICN"
        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        # Step 1: hospitals 테이블에 병원 정보 등록
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 이미 등록되어 있는지 확인
            cursor.execute(
                "SELECT id FROM hospitals WHERE hospital_key = %s",
                (hospital_key,),
            )
            if cursor.fetchone():
                # 이미 등록됨
                cursor.close()
                self.release_connection(conn)
                return True

            # 새로 등록
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

        # Step 2: 병원별 데이터 테이블 생성
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 데이터 테이블 생성 (소수점 지원)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    value NUMERIC(15, 2) NOT NULL,
                    hex_data TEXT
                )
            """)
            conn.commit()

            # 인덱스 생성 (timestamp 기준 내림차순)
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

    def insert_data(
        self, 
        hospital_key: str, 
        timestamp: str, 
        value: float, 
        hex_data: str = None
    ):
        """
        데이터 저장 (10초마다)
        
        Args:
            hospital_key: 병원 식별자 (예: "ICN")
            timestamp: 시각 (예: "2025-11-21 16:20:10")
            value: 전력량 (예: 6543.21)
            hex_data: HEX 원본 데이터 (선택)
        """
        if not self.db_available:
            return

        # 테이블명 생성
        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # INSERT
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
        """
        등록된 병원 목록 조회
        
        Returns:
            list[dict]: 병원 정보 리스트
                - hospital_key: 병원 식별자
                - ip_address: IP 주소
                - port: 포트
                - created_at: 등록 시각
        """
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
            
            return hospitals if hospitals else []
        except Exception as e:
            print(f"❌ 병원 조회 오류: {e}")
            if conn:
                self.release_connection(conn)
            return []

    def get_hospital_data(
        self, 
        hospital_key: str, 
        start_datetime, 
        end_datetime, 
        limit: int = 1000
    ):
        """
        특정 병원의 기간별 데이터 조회
        
        Args:
            hospital_key: 병원 식별자
            start_datetime: 시작 시각
            end_datetime: 종료 시각
            limit: 최대 레코드 수
        
        Returns:
            list[dict]: 데이터 리스트
        """
        if not self.db_available:
            return []

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = f"""
                SELECT timestamp, value, hex_data
                FROM {table_name}
                WHERE timestamp >= %s AND timestamp <= %s
                ORDER BY timestamp ASC
                LIMIT %s
            """
            cursor.execute(query, (start_datetime, end_datetime, limit))
            rows = cursor.fetchall()
            
            cursor.close()
            self.release_connection(conn)
            
            return rows if rows else []
        except Exception as e:
            print(f"❌ 데이터 조회 오류: {e}")
            if conn:
                self.release_connection(conn)
            return []

    def get_connection(self):
        """
        연결 풀에서 연결 가져오기
        
        Returns:
            psycopg2.connection: DB 연결 객체
        """
        try:
            if self.connection_pool:
                return self.connection_pool.getconn()
        except Exception as e:
            print(f"❌ 연결 오류: {e}")
        return None

    def release_connection(self, conn):
        """
        연결을 풀에 반환
        
        Args:
            conn: 반환할 연결 객체
        """
        try:
            if conn and self.connection_pool:
                self.connection_pool.putconn(conn)
        except Exception as e:
            print(f"❌ 연결 반환 오류: {e}")

    def close(self):
        """
        연결 풀 종료
        
        프로그램 종료 시 호출
        """
        if self.connection_pool:
            self.connection_pool.closeall()
            print("✅ DB 연결 풀 종료")
