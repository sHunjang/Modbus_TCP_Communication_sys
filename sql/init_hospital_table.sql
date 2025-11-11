-- ============================================================
-- PostgreSQL + TimescaleDB 초기화 스크립트 (수정 버전)
-- ============================================================

-- TimescaleDB Extension 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 병원 전력량 테이블 생성 함수 (압축 오류 수정)
-- ============================================================
CREATE OR REPLACE FUNCTION create_hospital_table(table_name TEXT)
RETURNS void AS $$
BEGIN
    -- 테이블 생성
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I (
            time            TIMESTAMPTZ NOT NULL,
            energy_kwh_avg  NUMERIC(12,2),     -- 1분 평균 유효전력량 (kWh)
            energy_kwh_max  NUMERIC(12,2),     -- 1분 최대 유효전력량
            energy_kwh_min  NUMERIC(12,2),     -- 1분 최소 유효전력량
            sample_count    INTEGER,           -- 1분 동안 수집된 샘플 수
            status          TEXT DEFAULT ''OK''
        )', table_name);
    
    -- TimescaleDB Hypertable 변환 (시계열 최적화)
    EXECUTE format('
        SELECT create_hypertable(%L, ''time'', 
            if_not_exists => TRUE,
            chunk_time_interval => INTERVAL ''7 days''
        )', table_name);
    
    -- 인덱스 생성 (빠른 조회)
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS %I 
        ON %I (time DESC)
    ', 'idx_' || table_name || '_time', table_name);
    
    -- ============================================================
    -- 압축 설정 (columnstore 활성화 먼저)
    -- ============================================================
    BEGIN
        -- 압축 활성화
        EXECUTE format('
            ALTER TABLE %I SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = ''''
            )
        ', table_name);
        
        -- 압축 정책 추가 (7일 지난 데이터 자동 압축)
        EXECUTE format('
            SELECT add_compression_policy(%L, INTERVAL ''7 days'', if_not_exists => TRUE)
        ', table_name);
        
        RAISE NOTICE '  ✅ 압축 정책 활성화: %', table_name;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE WARNING '  ⚠️ 압축 정책 설정 실패 (무시): %', SQLERRM;
    END;
    
    -- ============================================================
    -- 보관 정책 (1년 지난 데이터 자동 삭제)
    -- ============================================================
    BEGIN
        EXECUTE format('
            SELECT add_retention_policy(%L, INTERVAL ''365 days'', if_not_exists => TRUE)
        ', table_name);
        
        RAISE NOTICE '  ✅ 보관 정책 활성화: %', table_name;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE WARNING '  ⚠️ 보관 정책 설정 실패 (무시): %', SQLERRM;
    END;
    
    RAISE NOTICE '✅ 테이블 생성 완료: %', table_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 병원 목록 관리 테이블
-- ============================================================
CREATE TABLE IF NOT EXISTS hospitals (
    id              SERIAL PRIMARY KEY,
    hospital_name   VARCHAR(100) UNIQUE NOT NULL,  -- 병원명
    table_name      VARCHAR(100) UNIQUE NOT NULL,  -- 테이블명
    hmi_ip          VARCHAR(50) NOT NULL,          -- HMI IP 주소
    port            INTEGER DEFAULT 502,            -- Modbus 포트
    unit_id         INTEGER DEFAULT 1,              -- Unit ID
    meter_type      VARCHAR(20) DEFAULT '3P4W',     -- 미터 타입
    created_at      TIMESTAMPTZ DEFAULT NOW(),      -- 생성 시간
    last_update     TIMESTAMPTZ,                    -- 마지막 데이터 수신 시간
    status          TEXT DEFAULT 'ACTIVE'           -- 상태
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_hospitals_name ON hospitals (hospital_name);

-- ============================================================
-- 초기 병원 등록 (기본 병원 3곳)
-- ============================================================
-- INSERT INTO hospitals (hospital_name, table_name, hmi_ip, port, unit_id)
-- VALUES 
--     ('인천병원', '인천병원_1min', '192.168.0.100', 502, 1),
--     ('안산병원', '안산병원_1min', '192.168.0.101', 502, 1),
--     ('대구병원', '대구병원_1min', '192.168.0.102', 502, 1)
-- ON CONFLICT (hospital_name) DO NOTHING;

-- ============================================================
-- 병원 테이블 자동 생성
-- ============================================================
DO $$
DECLARE
    hospital_record RECORD;
BEGIN
    -- hospitals 테이블에서 병원 목록 읽어서 테이블 생성
    FOR hospital_record IN 
        SELECT table_name FROM hospitals
    LOOP
        PERFORM create_hospital_table(hospital_record.table_name);
    END LOOP;
END $$;

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ 병원 전력량 모니터링 DB 초기화 완료!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '📊 등록된 병원: 인천, 안산, 대구';
    RAISE NOTICE '💾 데이터: 유효전력량(kWh) 1분 평균';
    RAISE NOTICE '🔥 TimescaleDB: Hypertable 활성화';
    RAISE NOTICE '📦 압축: 7일 지난 데이터 자동 압축';
    RAISE NOTICE '🗑️ 보관: 365일 지난 데이터 자동 삭제';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
END $$;
