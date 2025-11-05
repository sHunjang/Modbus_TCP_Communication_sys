#!/usr/bin/env python3

import sys
sys.path.insert(0, 'core')

from core.database import DatabaseManager
from core.data_aggregator import DataAggregator
from datetime import datetime
import time

# 1️⃣ DB 연결 테스트
print("=" * 60)
print("1️⃣ DB 연결 테스트")
print("=" * 60)

db = DatabaseManager()
print("✅ DB 연결 성공\n")

# 2️⃣ 병원 등록 테스트
print("=" * 60)
print("2️⃣ 병원 등록 테스트")
print("=" * 60)

success = db.register_hospital(
    hospital_name="테스트병원",
    table_name="테스트병원_1min",
    hmi_ip="192.168.1.102",
    port=8000,
    unit_id=1,
    meter_type="3P4W"
)

if success:
    print("✅ 병원 등록 성공\n")
else:
    print("❌ 병원 등록 실패\n")

# 3️⃣ 데이터 집계 테스트
print("=" * 60)
print("3️⃣ 데이터 집계 테스트")
print("=" * 60)

agg = DataAggregator("테스트병원")

# 가상 데이터 12개 추가 (1분치)
for i in range(12):
    agg.add_data({
        'power_l1': 20000 + i * 100,
        'power_l2': 21000 + i * 100,
        'power_l3': 19000 + i * 100,
        'energy_l1': 30000 + i * 0.5,
        'energy_l2': 30001 + i * 0.5,
        'energy_l3': 30002 + i * 0.5,
    })
    print(f"  데이터 {i+1}/12 추가")

# 집계
aggregated = agg.aggregate()
print(f"\n✅ 집계 완료:")
print(f"  L1 전력: {aggregated['power_l1_avg']:.2f} W")
print(f"  L2 전력: {aggregated['power_l2_avg']:.2f} W")
print(f"  L3 전력: {aggregated['power_l3_avg']:.2f} W")
print(f"  전체 전력: {aggregated['power_total_avg']:.2f} W")
print(f"  전체 전력량: {aggregated['energy_total_avg']:.2f} kWh\n")

# 4️⃣ DB 저장 테스트
print("=" * 60)
print("4️⃣ DB 저장 테스트")
print("=" * 60)

db.insert_energy_data(
    table_name="테스트병원_1min",
    timestamp=datetime.now(),
    phase='L1',
    power_avg=aggregated['power_l1_avg'],
    energy_kwh_avg=aggregated['energy_l1_avg'],
    sample_count=12,
    status='OK'
)

db.insert_energy_data(
    table_name="테스트병원_1min",
    timestamp=datetime.now(),
    phase='TOTAL',
    power_avg=aggregated['power_total_avg'],
    energy_kwh_avg=aggregated['energy_total_avg'],
    sample_count=12,
    status='OK'
)

print("✅ DB 저장 완료\n")

# 5️⃣ DB 확인
print("=" * 60)
print("5️⃣ DB 데이터 확인")
print("=" * 60)

hospitals = db.get_hospitals()
print(f"등록된 병원: {len(hospitals)}개")
for h in hospitals:
    print(f"  - {h['hospital_name']} ({h['table_name']})")

db.close()
print("\n✅ 모든 테스트 완료!\n")
