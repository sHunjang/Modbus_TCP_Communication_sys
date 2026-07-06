#!/usr/bin/env python3
# core/database.py

"""
PostgreSQL 데이터베이스 관리

[변경 이력]
- SQL 인젝션 방어: hospital_key 형식/등록 여부 검증 (is_valid_hospital_key, is_registered_hospital)
- 병원 완전 삭제 기능 (delete_hospital)
- 배포 환경 대응: config 파일을 exe 옆 폴더에서 읽고, 없으면 템플릿 자동 생성
- [신규] DB 자동 재연결: 백그라운드 헬스체크 스레드로 끊김 감지 및 재연결
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
import re
import sys
import os
import threading
from pathlib import Path


class DatabaseManager:
    """PostgreSQL 데이터베이스 관리자"""

    HOSPITAL_KEY_PATTERN = re.compile(r'^[A-Za-z0-9_]{1,20}$')

    # [신규] 헬스체크 주기 (초). 너무 짧으면 DB에 불필요한 부하, 너무 길면 복구가 늦음.
    HEALTH_CHECK_INTERVAL = 10

    def __init__(self, config_file="config/database.json", on_reconnect=None):
        """
        초기화

        Args:
            config_file: DB 설정 파일 경로
        """
        self.config = self.load_config(config_file)
        self.connection_pool = None
        self.db_available = False
        self.on_reconnect = on_reconnect

        # [신규] 연결 풀 교체(재연결) 시 다른 스레드와의 경합을 막기 위한 락
        self._pool_lock = threading.Lock()
        self._stop_health_check = threading.Event()

        self.initialize_pool()

        if self.db_available:
            self.setup_base_tables()

        # [신규] 자동 재연결 백그라운드 스레드 시작
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def load_config(self, config_file):
        """
        설정 파일 로드 (exe 옆 폴더에서 읽음 — csv_exporter.py와 동일한 방식)
        파일이 없으면 기본 템플릿을 생성해서 현장에서 바로 편집할 수 있게 한다.

        Args:
            config_file: 설정 파일 경로

        Returns:
            dict: DB 설정
        """
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.dirname(base_path)

        config_path = os.path.join(base_path, config_file)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                print(f"✅ 설정 파일 로드: {config_path}")
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {config_path} 없음, 기본 템플릿 생성 후 기본값 사용")
            default_config = {
                "host": "localhost",
                "port": 5432,
                "dbname": "hospital_power",
                "user": "postgres",
                "password": "CHANGE_ME",
                "sslmode": "prefer",
            }
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                print(f"✅ 기본 설정 템플릿 생성됨: {config_path} (편집 후 재실행 필요)")
            except Exception as e:
                print(f"⚠️ 기본 설정 템플릿 생성 실패: {e}")
            return default_config
        except Exception as e:
            print(f"⚠️ 설정 로드 오류: {e}, 기본값 사용")
            return {
                "host": "localhost",
                "port": 5432,
                "dbname": "hospital_power",
                "user": "postgres",
                "password": "CHANGE_ME",
                "sslmode": "prefer",
            }

    def initialize_pool(self):
        """
        연결 풀 초기화 (최초 연결 및 재연결 시 공통으로 사용)
        """
        success = False
        with self._pool_lock:
            try:
                new_pool = psycopg2.pool.SimpleConnectionPool(
                    1,
                    20,
                    host=self.config["host"],
                    port=self.config["port"],
                    database=self.config["dbname"],
                    user=self.config["user"],
                    password=self.config["password"],
                    sslmode=self.config.get("sslmode", "prefer"),
                )
                self.connection_pool = new_pool
                self.db_available = True
                success = True
                print(f"✅ DB 연결: {self.config['host']}:{self.config['port']}/{self.config['dbname']}")
            except Exception as e:
                self.db_available = False
                print(f"❌ DB 연결 오류: {e}")

        # [신규] 콜백은 반드시 _pool_lock을 놓은 뒤 호출한다.
        # 콜백(flush_buffer) 안에서 insert_data() 등 다른 DB 메서드를 부를 수 있는데,
        # 그 메서드들이 같은 락을 다시 잡으려 하면 데드락이 나기 때문.
        if success and self.on_reconnect:
            try:
                self.on_reconnect(self)
            except Exception as e:
                print(f"❌ on_reconnect 콜백 처리 중 오류: {e}")

    # ==================== [신규] 자동 재연결 ====================
    def _health_check_loop(self):
        while not self._stop_health_check.wait(self.HEALTH_CHECK_INTERVAL):
            if self.db_available:
                if not self._ping():
                    print("⚠️ DB 헬스체크 실패 — 연결이 끊긴 것으로 판단하여 재연결을 준비합니다.")
                    self._mark_disconnected()
                elif self.on_reconnect:
                    # [수정] db_available이 계속 True였더라도(재연결 이벤트가 없었더라도),
                    # 개별 insert 실패로 버퍼에 데이터가 쌓여있을 수 있으므로
                    # 매 헬스체크 주기마다 flush를 시도한다. 버퍼가 비어있으면
                    # flush_buffer 내부에서 즉시 리턴하므로 평소엔 비용이 거의 없다.
                    try:
                        self.on_reconnect(self)
                    except Exception as e:
                        print(f"❌ 주기적 버퍼 flush 시도 중 오류: {e}")
            else:
                print("🔄 DB 재연결 시도 중...")
                self.initialize_pool()
                if self.db_available:
                    print("✅ DB 재연결 성공")
                    self.setup_base_tables()

    def _ping(self) -> bool:
        """가벼운 쿼리로 DB가 실제로 응답하는지 확인"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            self.release_connection(conn)
            return True
        except Exception:
            # 커넥션 자체가 죽어있을 수 있으니 풀에 되돌리지 않고 완전히 폐기
            if conn and self.connection_pool:
                try:
                    self.connection_pool.putconn(conn, close=True)
                except Exception:
                    pass
            return False

    def _mark_disconnected(self):
        """연결 끊김 확정 처리 — 기존 풀을 정리하고 재연결 대상 상태로 전환"""
        with self._pool_lock:
            self.db_available = False
            if self.connection_pool:
                try:
                    self.connection_pool.closeall()
                except Exception:
                    pass
                self.connection_pool = None

    def is_valid_hospital_key(self, hospital_key: str) -> bool:
        """hospital_key가 테이블명으로 안전하게 쓸 수 있는 형식인지 검증"""
        return bool(hospital_key) and bool(self.HOSPITAL_KEY_PATTERN.match(hospital_key))

    def is_registered_hospital(self, hospital_key: str) -> bool:
        """hospital_key가 형식적으로 안전하고, 실제 등록되어 있는지 확인"""
        if not self.is_valid_hospital_key(hospital_key):
            return False
        if not self.db_available:
            return False

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM hospitals WHERE hospital_key = %s",
                (hospital_key,),
            )
            found = cursor.fetchone() is not None
            cursor.close()
            self.release_connection(conn)
            return found
        except Exception as e:
            if conn:
                self.release_connection(conn)
            print(f"❌ 병원 등록 확인 오류: {e}")
            return False

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
            try:
                self.connection_pool.putconn(conn)
            except Exception:
                pass

    def close(self):
        """연결 풀 닫기 (프로그램 종료 시 호출)"""
        # [신규] 헬스체크 스레드도 같이 정지시켜야 종료가 깔끔하게 됨
        self._stop_health_check.set()
        with self._pool_lock:
            if self.connection_pool:
                self.connection_pool.closeall()
                print("✅ DB 연결 풀 닫힘")

    def register_hospital(self, hospital_key: str, ip_address: str, port: int):
        """
        병원 등록 및 데이터 테이블 생성

        [버그 수정] 기존에는 hospitals 테이블에 이미 등록된 병원이면
        곧바로 return True로 끝나서, 데이터 테이블(hospital_XXX) 생성
        코드가 두 번 다시 실행되지 않았다. 만약 최초 등록 시점에 hospitals
        INSERT는 성공했는데 바로 이어지는 CREATE TABLE만 실패하는 상황
        (일시적 DB 부하, 커넥션 문제 등)이 벌어지면, 그 병원은 영원히
        데이터 테이블 없이 남아 모든 INSERT가 "relation does not exist"로
        계속 실패하는 상태에 빠졌다 — 재시작해도 스스로 복구되지 않았다.

        수정 후에는 hospitals 등록 여부와 무관하게 CREATE TABLE IF NOT EXISTS를
        매번 시도한다. 이미 테이블이 있으면 그냥 넘어가므로 비용은 무시할 수준이고,
        테이블이 빠진 상태라면 다음 호출 때 자동으로 복구된다.
        """
        if not self.db_available:
            return False

        if not self.is_valid_hospital_key(hospital_key):
            print(f"❌ 잘못된 hospital_key 형식으로 등록 거부: {hospital_key}")
            return False

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        # 1) hospitals 테이블에 병원 정보 등록 (없을 때만 INSERT)
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM hospitals WHERE hospital_key = %s",
                (hospital_key,),
            )
            if not cursor.fetchone():
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

        # 2) [수정] 데이터 테이블은 hospitals 등록 여부와 무관하게 매번 확인/생성 시도
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

            return True

        except Exception as e:
            if conn:
                conn.rollback()
                self.release_connection(conn)
            print(f"❌ 테이블 생성 오류: {e}")
            return False

    def insert_data(self, hospital_key: str, timestamp: str, value: float, hex_data: str = None) -> bool:
        """
        데이터 저장

        Returns:
            bool: [신규] 저장 성공 여부. central_monitor.py가 이 값을 보고
                  실패 시 로컬 버퍼 파일에 임시 저장할지 판단한다.
        """
        if not self.db_available:
            return False

        if not self.is_valid_hospital_key(hospital_key):
            print(f"❌ 잘못된 hospital_key 형식으로 저장 거부: {hospital_key}")
            return False

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
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
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ DB 저장 오류: {e}")
            return False
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

    def delete_hospital(self, hospital_key: str) -> bool:
        """병원 완전 삭제 (hospitals 테이블 행 + 데이터 테이블 모두 제거)"""
        if not self.db_available:
            return False

        if not self.is_valid_hospital_key(hospital_key):
            print(f"❌ 잘못된 hospital_key 형식으로 삭제 거부: {hospital_key}")
            return False

        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(
                "DELETE FROM hospitals WHERE hospital_key = %s",
                (hospital_key,),
            )
            conn.commit()
            cursor.close()
            self.release_connection(conn)

            print(f"✅ {hospital_key} 삭제 완료 (테이블 {table_name} 제거됨)")
            return True

        except Exception as e:
            if conn:
                conn.rollback()
                self.release_connection(conn)
            print(f"❌ 병원 삭제 오류: {e}")
            return False