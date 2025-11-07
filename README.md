# 🏥 병원 전력량 모니터링 시스템

> Modbus TCP 기반 실시간 전력 데이터 수집 및 모니터링 시스템

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-lightblue?logo=postgresql)

## 📋 개요

병원의 다중 전력량계에서 실시간으로 전력 데이터를 수집하고, 데이터베이스에 저장하며, CSV로 내보낼 수 있는 통합 모니터링 시스템입니다.

### ✨ 주요 기능

- ✅ **실시간 모니터링** - 3개 이상의 병원 동시 모니터링
- ✅ **Modbus TCP** - 산업용 전력량계와 통신
- ✅ **데이터 수집** - 1분 단위 데이터 수집 및 집계
- ✅ **CSV 내보내기** - 기간 선택 후 데이터 내보내기
- ✅ **데이터베이스** - PostgreSQL/TimescaleDB 저장
- ✅ **사용자 관리** - UI에서 병원 추가/삭제
- ✅ **에러 시뮬레이션** - 테스트용 더미 모드

---

## 🔧 설치 방법

### 1. 저장소 클론

git clone https://github.com/yourusername/ModbusTCPCollector.git
cd ModbusTCPCollector

### 3. 의존성 설치
pip install -r requirements.txt


### 4. 데이터베이스 설정

PostgreSQL 설치 및 데이터베이스 생성
createdb hospital_power

필요시 환경 변수 설정
export DB_HOST=localhost
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_NAME=hospital_power


### 5. 프로그램 실행

python main.py

---

## 📚 사용 방법

### 더미 모드 (테스트)

main.py에서
USE_DUMMY_MODE = True # 가상 데이터로 테스트


### 실제 장치 연동

main.py에서
USE_DUMMY_MODE = False # 실제 장치와 연동

UI에서 병원 추가
병원명: 인천병원
HMI IP: 192.168.1.100
포트: 502


### CSV 내보내기

1. 시작 날짜/시간 선택
2. 종료 날짜/시간 선택
3. "📥 CSV 내보내기" 버튼 클릭
4. `다운로드/병원전력량데이터/` 폴더에서 확인

---

## 📊 기술 스택

- **언어**: Python 3.8+
- **GUI**: PyQt6
- **데이터베이스**: PostgreSQL + TimescaleDB
- **통신**: Modbus TCP (pymodbus)
- **데이터 포맷**: CSV

---

## 🛠️ 개발 환경 세팅

### requirements.txt

PyQt6==6.6.1
psycopg2-binary==2.9.9
pymodbus==3.5.0
python-dotenv==1.0.0

---

## 📝 설정 파일

### .env (선택사항)

DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=hospital_power
DB_PORT=5432

MODBUS_TIMEOUT=5
MODBUS_RETRY=3

---

## 🐛 문제 해결

### 데이터베이스 연결 오류

PostgreSQL 상태 확인
sudo systemctl status postgresql

데이터베이스 초기화
dropdb hospital_power
createdb hospital_power

---

## 📦 PyInstaller로 .exe 생성

설치
pip install pyinstaller

.exe 생성
pyinstaller --onefile --windowed --name "병원전력량모니터링" main.py

실행 파일 위치
dist/병원전력량모니터링.exe

---

## 📚 참고자료

- [Modbus TCP 스펙](http://www.modbus.org/)
- [PyQt6 문서](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [PostgreSQL 문서](https://www.postgresql.org/docs/)

---

**마지막 업데이트**: 2025-10-30
