# 🏥 중앙 모니터링 시스템 v1.0

병원 HMI에서 전력량 데이터를 수신하여 실시간 모니터링 및 저장하는 시스템

## 📋 개요

- **HMI**: 10초마다 전력량 데이터 전송 (TCP)
- **중앙 서버**: 데이터 수신 → UI 표시 → PostgreSQL 저장
- **포맷**: `[병원명3자리][00][00][전력량10자리]`
  - 예: `ICN{00}{00}0000654321` → 병원: ICN, 전력: 6543.21 kWh

## 🚀 설치 및 실행

### 1. 환경 설정

- Python 3.10 이상 필요
```bash
python --version
```


### 2. 패키지 설치

```bash
pip install -r requirements.txt
```


### 3. PostgreSQL 설정

- PostgreSQL 설치 후 DB 생성
```bash
createdb hospital_power
```

- 또는 psql에서
```bash
psql -U postgres
CREATE DATABASE hospital_power;
\q
```

### 4. 설정 파일 수정

`config/database.json`:

```bash
{
"host": "localhost",
"port": 5432,
"dbname": "hospital_power",
"user": "postgres",
"password": "your_password"
}
```

### 5. 프로그램 실행

```bash
python central_monitor.py
```

## 🎯 주요 기능

### 1. 실시간 모니터링
- 10초마다 HMI 데이터 수신
- UI 테이블에 실시간 표시
- 병원명 / IP:포트 / 전력량 표시

### 2. 데이터 저장
- PostgreSQL에 10초 단위 저장
- 병원별 자동 테이블 생성
- 소수점 2자리 지원 (NUMERIC)

### 3. CSV 내보내기
- 기간별 데이터 CSV 저장
- 통계 정보 제공 (평균/최대/최소)
- exports/ 폴더에 저장

### 4. 자동 병원 등록
- HMI 첫 접속 시 자동 등록
- 테이블 자동 생성
- 인덱스 자동 생성

## 🔧 설정

### 포트 포워딩
- 라우터에서 23000 포트를 중앙 서버 IP로 포워딩
- 공인 IP 확인: https://www.whatismyip.com

### 방화벽
- Windows: 23000 포트 인바운드 허용
- Linux: `ufw allow 23000/tcp`

## 📊 DB 테이블 구조

### hospitals (병원 목록)

```sql
CREATE TABLE hospitals (
id SERIAL PRIMARY KEY,
hospital_key VARCHAR(100) UNIQUE,
ip_address VARCHAR(50),
port INTEGER,
created_at TIMESTAMP DEFAULT NOW()
);
```

### hospital_ICN (병원별 데이터)
```sql
CREATE TABLE hospital_ICN (
id BIGSERIAL PRIMARY KEY,
timestamp TIMESTAMP NOT NULL,
value NUMERIC(15, 2) NOT NULL,
hex_data TEXT
);
```

## 🧪 테스트

### 단일 병원 테스트
```bash
python dummy_client.py
```

### 다중 병원 테스트
```bash
python dummy_client_multi.py
```

## 📅 버전

v1.0 - 2025.11.21