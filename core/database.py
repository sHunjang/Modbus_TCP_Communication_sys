#!/usr/bin/env python3
# core/database.py
"""
PostgreSQL + TimescaleDB 데이터베이스 관리
자동 초기화 기능 포함
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
from pathlib import Path


class DatabaseManager:
    """데이터베이스 관리자"""
    
    def __init__(self, config_file="config/database.json", auto_init=True):
        """
        초기화
        
        Args:
            config_file (str): DB 설정 파일 경로
            auto_init (bool): 자동 초기화 여부
        """
        # 설정 로드
        self.config = self.load_config(config_file)
        
        # 연결 풀
        self.connection_pool = None
        self.initialize_pool()
        
        # 자동 초기화
        if auto_init:
            self.auto_initialize()
    
    def load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ 설정 파일 없음: {config_file}")
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
                1, 10,  # min, max connections
                host=self.config['host'],
                port=self.config['port'],
                dbname=self.config['dbname'],
                user=self.config['user'],
                password=self.config['password'],
                sslmode=self.config.get('sslmode', 'prefer')
            )
            
            print(f"✅ DB 연결 완료: {self.config['host']}:{self.config['port']}/{self.config['dbname']}")
        
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            self.connection_pool = None
    
    def auto_initialize(self):
        """
        자동 초기화
        - TimescaleDB Extension 활성화
        - 테이블 생성 함수 등록
        - hospitals 테이블 생성
        """
        conn = None
        try:
            print("🔧 DB 자동 초기화 시작...")
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 1. TimescaleDB Extension 활성화
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            print("  ✅ TimescaleDB Extension 활성화")
            
            # 2. 테이블 생성 함수 등록
            cursor.execute("""
                CREATE OR REPLACE FUNCTION create_hospital_table(table_name TEXT)
                RETURNS void AS $$
                BEGIN
                    -- 테이블 생성
                    EXECUTE format('
                        CREATE TABLE IF NOT EXISTS %I (
                            time            TIMESTAMPTZ NOT NULL,
                            energy_kwh_avg  NUMERIC(12,2),
                            energy_kwh_max  NUMERIC(12,2),
                            energy_kwh_min  NUMERIC(12,2),
                            sample_count    INTEGER,
                            status          TEXT DEFAULT ''OK''
                        )', table_name);
                    
                    -- TimescaleDB Hypertable 변환
                    EXECUTE format('
                        SELECT create_hypertable(%L, ''time'', 
                            if_not_exists => TRUE,
                            chunk_time_interval => INTERVAL ''7 days''
                        )', table_name);
                    
                    -- 인덱스 생성
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS %I 
                        ON %I (time DESC)
                    ', 'idx_' || table_name || '_time', table_name);
                    
                    RAISE NOTICE '✅ 테이블 생성 완료: %', table_name;
                END;
                $$ LANGUAGE plpgsql;
            """)
            print("  ✅ 테이블 생성 함수 등록")
            
            # 3. hospitals 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospitals (
                    id              SERIAL PRIMARY KEY,
                    hospital_name   VARCHAR(100) UNIQUE NOT NULL,
                    table_name      VARCHAR(100) UNIQUE NOT NULL,
                    hmi_ip          VARCHAR(50) NOT NULL,
                    port            INTEGER DEFAULT 502,
                    unit_id         INTEGER DEFAULT 1,
                    meter_type      VARCHAR(20) DEFAULT '3P4W',
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    last_update     TIMESTAMPTZ,
                    status          TEXT DEFAULT 'ACTIVE'
                )
            """)
            print("  ✅ hospitals 테이블 생성")
            
            # 4. 인덱스 생성
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hospitals_name 
                ON hospitals (hospital_name)
            """)
            
            conn.commit()
            cursor.close()
            self.release_connection(conn)
            
            print("✅ DB 자동 초기화 완료!")
        
        except Exception as e:
            print(f"⚠️ DB 자동 초기화 중 오류 (무시): {e}")
            if conn:
                conn.rollback()
                self.release_connection(conn)
    
    def get_connection(self):
        """연결 가져오기"""
        if self.connection_pool:
            return self.connection_pool.getconn()
        else:
            raise Exception("연결 풀이 초기화되지 않았습니다")
    
    def release_connection(self, conn):
        """연결 반환"""
        if self.connection_pool:
            self.connection_pool.putconn(conn)
    
    def create_hospital_table(self, table_name):
        """
        병원 테이블 생성
        
        Args:
            table_name (str): 테이블명 (예: 인천병원_1min)
        
        Returns:
            bool: 성공 여부
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 테이블 생성 함수 호출
            cursor.execute("SELECT create_hospital_table(%s)", (table_name,))
            conn.commit()
            
            cursor.close()
            self.release_connection(conn)
            
            print(f"✅ 테이블 생성 완료: {table_name}")
            return True
        
        except Exception as e:
            print(f"❌ 테이블 생성 오류: {e}")
            if conn:
                conn.rollback()
                self.release_connection(conn)
            return False
    
    def insert_energy_data(self, table_name, data):
        """
        유효전력량 데이터 삽입
        
        Args:
            table_name (str): 테이블명
            data (dict): 집계된 데이터
        
        Returns:
            bool: 성공 여부
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # SQL 쿼리 (동적 테이블명)
            query = f"""
                INSERT INTO {table_name} 
                (time, energy_kwh_avg, energy_kwh_max, energy_kwh_min, sample_count, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                data['time'],
                data['energy_kwh_avg'],
                data['energy_kwh_max'],
                data['energy_kwh_min'],
                data['sample_count'],
                data['status']
            ))
            
            conn.commit()
            cursor.close()
            self.release_connection(conn)
            
            return True
        
        except Exception as e:
            print(f"❌ 데이터 삽입 오류: {e}")
            if conn:
                conn.rollback()
                self.release_connection(conn)
            return False
    
    def get_hospitals(self):
        """
        등록된 병원 목록 조회
        
        Returns:
            list: 병원 정보 리스트
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM hospitals
                WHERE status = 'ACTIVE'
                ORDER BY hospital_name
            """)
            
            results = cursor.fetchall()
            
            cursor.close()
            self.release_connection(conn)
            
            return results
        
        except Exception as e:
            print(f"❌ 병원 목록 조회 오류: {e}")
            if conn:
                self.release_connection(conn)
            return []
    
    def register_hospital(self, hospital_name, table_name, hmi_ip, port=502, unit_id=1, meter_type="3P4W"):
        """
        새 병원 등록
        
        Args:
            hospital_name (str): 병원명
            table_name (str): 테이블명
            hmi_ip (str): HMI IP
            port (int): 포트
            unit_id (int): Unit ID
            meter_type (str): 미터 타입
        
        Returns:
            bool: 성공 여부
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 병원 등록
            cursor.execute("""
                INSERT INTO hospitals 
                (hospital_name, table_name, hmi_ip, port, unit_id, meter_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hospital_name) DO UPDATE
                SET hmi_ip = EXCLUDED.hmi_ip,
                    port = EXCLUDED.port,
                    unit_id = EXCLUDED.unit_id,
                    meter_type = EXCLUDED.meter_type
            """, (hospital_name, table_name, hmi_ip, port, unit_id, meter_type))
            
            conn.commit()
            cursor.close()
            self.release_connection(conn)
            
            # 테이블 생성
            self.create_hospital_table(table_name)
            
            print(f"✅ 병원 등록 완료: {hospital_name}")
            return True
        
        except Exception as e:
            print(f"❌ 병원 등록 오류: {e}")
            if conn:
                conn.rollback()
                self.release_connection(conn)
            return False
    
    def query_recent_data(self, table_name, limit=100):
        """
        최근 데이터 조회
        
        Args:
            table_name (str): 테이블명
            limit (int): 조회 개수
        
        Returns:
            list: 데이터 리스트
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = f"""
                SELECT * FROM {table_name}
                ORDER BY time DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            
            results = cursor.fetchall()
            
            cursor.close()
            self.release_connection(conn)
            
            return results
        
        except Exception as e:
            print(f"❌ 데이터 조회 오류: {e}")
            if conn:
                self.release_connection(conn)
            return []
    
    def close(self):
        """연결 풀 종료"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("✅ DB 연결 종료")
