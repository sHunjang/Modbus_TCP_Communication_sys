# 🏥 중앙 모니터링 시스템 v1.5

병원 HMI에서 전력량 데이터를 수신하여 실시간 모니터링 및 저장하는 시스템

## 📋 개요

- **HMI**: 10초마다 전력량 데이터 전송 (TCP)
- **중앙 서버**: 데이터 수신 → UI 표시 → 30초 단위 DB 저장
- **웹 대시보드**: 원격으로 브라우저를 통해 IP 접속 시 실시간 모니터링
- **포맷**: `[병원명3자리][전력량10자리]`
  - 예: `ICN00654321` → 병원: ICN, 전력: 6543.21 kWh

## 🚀 설치 및 실행

### 1. 환경 설정

- Python 3.10 이상 필요
```bash
python --version
```


### 2. 패키지 설치

```text
PyQt6==6.6.1
psycopg2-binary==2.9.9
Flask==3.0.0
Flask-CORS==4.0.0
waitress==3.0.0
```

```bash
pip install -r requirements.txt
```


### 3. PostgreSQL 설정

- PostgreSQL 설치 후 DB 생성
```sql
createdb hospitals
```

- 또는 psql에서
```sql
psql -U postgres
CREATE DATABASE hospitals;
\q
```

### 4. 설정 파일 수정

`config/database.json`:

```json
{
  "host": "localhost",
  "port": 5432,
  "dbname": "hospitals",
  "user": "postgres",
  "password": "your_password",
  "sslmode": "prefer"
}
```

### 5. 프로그램 실행

```bash
python central_monitor.py
```
- 또는 exe 파일 실행 (CentralMonitor.exe)

## 🎯 주요 기능

### 1. 실시간 모니터링
- 10초마다 HMI 데이터 수신
- UI 테이블에 실시간 표시
- 병원명 / IP:포트 / 전력량 표시

### 2. 데이터 저장
- PostgreSQL에 30초 단위 저장
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

### 5. 웹 대시보드
- 접속: `http://서버IP:20000`
- 병원별 실시간 전력량 조회
- 30초 단위 로그 출력
- CSV 내보내기
- 통신 상태 모니터링

## 🔧 설정

### 포트 포워딩
- 라우터에서 중앙 서버 IP로 포워딩
- 230000: HMI 데이터 수신용
- 200000: 웹 대시보드 접속용
- 공인 IP 확인: https://www.whatismyip.com

### 방화벽
- Windows
```bash
netsh advfirewall firewall add rule name="HMI Server" dir=in action=allow protocol=TCP localport=23000
netsh advfirewall firewall add rule name="Web Dashboard" dir=in action=allow protocol=TCP localport=20000
```
- Linux
```bash
ufw allow 23000/tcp
ufw allow 20000/tcp
```

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

## 🏗️ 프로젝트 구조
```text
ModbusTCPCollector_v2/
├── central_monitor.py      # 메인 프로그램 (통합)
├── central_monitor.spec    # PyInstaller 빌드 설정
├── requirements.txt        # Python 패키지 목록
├── config/
│   └── database.json       # DB 설정
├── core/
│   ├── database.py         # DB 관리
│   └── csv_exporter.py     # CSV 내보내기
├── UI/
│   ├── main_window.py      # PyQt 메인 창
│   └── styles.py           # UI 스타일
├── templates/
│   └── dashboard.html      # 웹 대시보드 HTML
├── static/
│   ├── css/
│   │   └── style.css       # 웹 스타일
│   └── js/
│       └── dashboard.js    # 웹 JavaScript
└── exports/                # CSV 저장 폴더 (자동 생성)
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

v1.3 - 2025.11.26