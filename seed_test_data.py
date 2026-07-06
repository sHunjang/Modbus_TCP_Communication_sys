#!/usr/bin/env python3
# seed_test_data.py
# 프로젝트 루트(central_monitor.py가 있는 폴더)에 놓고 실행할 것
#
# 목적: 월별/일별 드릴다운 기능을 테스트하기 위해
#       ICN/SEL/BUS 3개 병원에 과거 13개월치 더미 데이터를 DB에 미리 심는다.
#
# 실행: python seed_test_data.py

import random
from datetime import date, datetime, timedelta

from core.database import DatabaseManager

# 병원별 시작 전력량(kWh)과 하루 평균 증가량 범위 (더미이므로 대략적인 값)
HOSPITALS = {
    "ICN": {"start": 900000.0, "daily_min": 35.0, "daily_max": 55.0, "ip": "127.0.0.1", "port": 51001},
    "SEL": {"start": 1500000.0, "daily_min": 60.0, "daily_max": 90.0, "ip": "127.0.0.1", "port": 51002},
    "BUS": {"start": 600000.0, "daily_min": 20.0, "daily_max": 35.0, "ip": "127.0.0.1", "port": 51003},
}

# 최근 13개월 + 진행 중인 이번 달의 오늘까지 시딩
MONTHS_BACK = 13


def daterange(start: date, end: date):
    """start부터 end까지(포함) 날짜를 하루씩 순회"""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def month_start(base: date, months_back: int) -> date:
    """base 기준 months_back개월 전의 1일"""
    year = base.year
    month = base.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def main():
    db = DatabaseManager()
    if not db.db_available:
        print("❌ DB에 연결할 수 없습니다. config/database.json 설정을 확인하세요.")
        return

    # [수정] 재실행 시 데이터가 중복/오염되는 것을 막기 위해
    # 시딩 대상 병원의 기존 데이터 테이블을 먼저 비운다.
    for hospital_key in HOSPITALS:
        if db.is_valid_hospital_key(hospital_key):
            table_name = f"hospital_{hospital_key}"
            conn = db.get_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    # TRUNCATE는 IF EXISTS를 지원하지 않으므로
                    # 테이블이 없는 첫 실행에서는 예외가 나는 게 정상 → 무시하고 진행
                    cursor.execute(f"TRUNCATE TABLE {table_name}")
                    conn.commit()
                    print(f"🧹 {hospital_key} 기존 테스트 데이터 초기화")
                except Exception:
                    conn.rollback()
                    print(f"ℹ️ {hospital_key} 테이블이 아직 없어 초기화 생략 (첫 실행)")
                finally:
                    cursor.close()
                    db.release_connection(conn)

    today = date.today()
    start_date = month_start(today, MONTHS_BACK)

    for hospital_key, cfg in HOSPITALS.items():
        print(f"\n▶ {hospital_key} 시딩 시작 ({start_date} ~ {today})")

        # 1) 병원 등록 (테이블 없으면 생성)
        db.register_hospital(hospital_key, cfg["ip"], cfg["port"])

        # 2) 누적 전력량 시작값
        cumulative = cfg["start"]
        row_count = 0

        for day in daterange(start_date, today):
            # 하루 동안의 증가량(랜덤) 을 하루 시작/끝 두 시점에 나눠서 저장
            # → MIN/MAX 기반 일별/월별 집계 쿼리 테스트에는 하루 2포인트만으로도 충분함
            daily_increase = random.uniform(cfg["daily_min"], cfg["daily_max"])

            # 의도적으로 하루 정도씩 데이터 결손(통신 두절)을 섞어서
            # generate_series LEFT JOIN이 null을 잘 채우는지도 함께 테스트
            if random.random() < 0.03:  # 약 3% 확률로 그 날은 데이터 없음
                print(f"  ⛔ {day} 데이터 결손 (테스트용으로 의도적 생략)")
                continue

            start_ts = datetime.combine(day, datetime.min.time()).replace(hour=0, minute=5)
            end_ts = datetime.combine(day, datetime.min.time()).replace(hour=23, minute=55)

            db.insert_data(hospital_key, start_ts.strftime("%Y-%m-%d %H:%M:%S"), round(cumulative, 2))
            cumulative += daily_increase
            db.insert_data(hospital_key, end_ts.strftime("%Y-%m-%d %H:%M:%S"), round(cumulative, 2))

            row_count += 2

        print(f"  ✅ {hospital_key} 완료: {row_count}건 저장 (현재 누적값: {cumulative:,.2f} kWh)")

    print("\n✅ 전체 시딩 완료. web_dashboard.py 또는 central_monitor.py를 실행해서 확인하세요.")
    db.close()


if __name__ == "__main__":
    main()
