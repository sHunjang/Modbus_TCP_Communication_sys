# README.md 파일

```markdown
# 🔌 Modbus TCP 통신 테스트 프로젝트

2대 PC 간 Modbus TCP 통신을 통한 전력 데이터 송수신 및 저장 테스트 프로그램

---

## 📋 프로젝트 개요

이 프로젝트는 산업용 통신 프로토콜인 **Modbus TCP**를 사용하여 실시간 전력 데이터를 수집하고 저장하는 시스템입니다.

### 목적
- Modbus TCP 프로토콜 학습 및 테스트
- 네트워크 기반 데이터 통신 실습
- 실시간 데이터 수집 및 CSV 저장 구현

### 시스템 구성

```
[PC 1 - 서버]                      [PC 2 - 클라이언트]
┌──────────────────┐               ┌──────────────────┐
│ Modbus TCP Server│               │ Modbus TCP Client│
│  (HMI 시뮬레이터) │◄─────────────►│  (데이터 수집기)  │
│                  │  Modbus TCP   │                  │
│ - 전력 데이터 생성│  Port: 502    │ - 데이터 읽기    │
│ - 레지스터 관리  │               │ - CSV 저장       │
└──────────────────┘               └──────────────────┘
```

---

## 🚀 주요 기능

### PC 1 (서버)
- ⚡ 랜덤 전력 데이터 생성 (전력, 전력량, 역률, 전압, 전류)
- 📊 Modbus Holding Register 관리
- 🔄 5초마다 자동 데이터 갱신
- 🌐 Modbus TCP 서버 (포트 502)

### PC 2 (클라이언트)
- 📥 서버로부터 실시간 데이터 수신
- 💾 CSV 파일 자동 저장
- 📈 수집 데이터 실시간 모니터링
- ⏱️ 5초 주기 자동 수집

---

## 📁 프로젝트 구조

```
Modbus_network_communication/
├── server_pc/
│   └── modbus_server.py          # PC 1: Modbus TCP 서버
├── client_pc/
│   └── modbus_client.py          # PC 2: Modbus TCP 클라이언트
├── power_data.csv                # 수집된 데이터 (자동 생성)
└── README.md
```

---

## 🔧 설치 방법

### 1. Python 설치
- Python 3.8 이상 필요
- 다운로드: https://www.python.org/downloads/

### 2. 라이브러리 설치

```
# pymodbus 설치 (양쪽 PC 모두 실행)
pip install pymodbus

# 특정 버전 설치 (권장)
pip install pymodbus==3.5.4
```

---

## 🎮 실행 방법

### Step 1: 네트워크 확인

**PC 1과 PC 2가 같은 네트워크에 연결되어 있는지 확인**

```
# PC 1에서 IP 주소 확인
# Windows:
ipconfig

# Mac/Linux:
ifconfig

# 예시 출력:
# IPv4 주소: 192.168.0.10  ← 이 IP 주소를 기억!
```

### Step 2: 방화벽 설정

**PC 1 (서버)에서 포트 502 열기**

#### Windows
1. Windows 설정 → 네트워크 및 인터넷 → Windows 방화벽
2. "고급 설정" → "인바운드 규칙" → "새 규칙"
3. 포트 → TCP → 특정 로컬 포트: `502`
4. 연결 허용 → 이름: "Modbus TCP"

#### Mac/Linux
```
# 방화벽 비활성화 (테스트 시)
sudo ufw disable

# 또는 포트만 열기
sudo ufw allow 502/tcp
```

### Step 3: 서버 실행 (PC 1)

```
# 관리자 권한으로 실행 (포트 502는 관리자 권한 필요)
# Windows: 우클릭 → "관리자 권한으로 실행"
python modbus_server.py

# 출력 예시:
# ══════════════════════════════════════════════════
# 🖥️ Modbus TCP 서버 시작 (HMI 시뮬레이터)
# ══════════════════════════════════════════════════
# 📍 IP 주소를 확인하세요!
# 🔌 포트: 502
# ⏱️ 데이터 갱신 주기: 5초
# ══════════════════════════════════════════════════
```

### Step 4: 클라이언트 실행 (PC 2)

```
python modbus_client.py

# IP 주소 입력 (PC 1의 IP)
서버 IP 주소: 192.168.0.10  ← PC 1의 IP 입력

# 출력 예시:
# [17:05:10] 📥 데이터 수신 #1
#   ⚡ 전력:    12.35 kW
#   📈 전력량:  150.52 kWh
#   📊 역률:     0.952
#   🔌 전압:    220.3 V
#   ⚡ 전류:     56.1 A
```

---

## 📊 데이터 형식

### Modbus 레지스터 맵

| 주소 | 데이터 | 크기 | 단위 | 설명 |
|------|--------|------|------|------|
| 0-1 | 전력 | Float (32bit) | kW | 순시 전력 |
| 2-3 | 전력량 | Float (32bit) | kWh | 누적 전력량 |
| 4-5 | 역률 | Float (32bit) | - | 전력 효율 |
| 6-7 | 전압 | Float (32bit) | V | 전압 |
| 8-9 | 전류 | Float (32bit) | A | 전류 |

### CSV 파일 형식

```
Timestamp,Power (kW),Energy (kWh),Power Factor,Voltage (V),Current (A),Status
2025-10-29 17:05:10,12.35,150.52,0.952,220.3,56.1,online
2025-10-29 17:05:15,13.21,150.54,0.948,219.8,60.1,online
```

---

## 🔍 트러블슈팅

### 문제 1: 연결 실패 (Connection Refused)

**원인**: 
- 서버가 실행되지 않음
- 방화벽 차단
- IP 주소 오류

**해결**:
```
1. PC 1에서 서버가 실행 중인지 확인
2. 방화벽 설정 확인 (포트 502 열림)
3. IP 주소 재확인 (ipconfig)
4. 같은 네트워크인지 확인 (같은 WiFi/공유기)
```

### 문제 2: Permission Denied (포트 502)

**원인**: 포트 502는 Well-Known Port로 관리자 권한 필요

**해결**:
```
# Windows
우클릭 → "관리자 권한으로 실행"

# Linux/Mac
sudo python modbus_server.py

# 또는 다른 포트 사용
포트 5020으로 변경 (코드에서 502 → 5020)
```

### 문제 3: 데이터가 0으로 표시됨

**원인**: Float 변환 오류 또는 레지스터 미설정

**해결**:
```
1. 서버가 정상 작동하는지 확인
2. pymodbus 버전 확인 (3.5.4 권장)
3. 서버 재시작
```

---

## 📚 기술 스택

- **언어**: Python 3.8+
- **라이브러리**: pymodbus 3.5.4
- **프로토콜**: Modbus TCP (Function Code 03)
- **데이터 저장**: CSV
- **통신 방식**: TCP/IP (포트 502)

---

## 🧪 테스트 시나리오

### 기본 테스트
1. ✅ 서버 실행 및 데이터 생성 확인
2. ✅ 클라이언트 연결 확인
3. ✅ 데이터 수신 및 출력 확인
4. ✅ CSV 파일 생성 및 저장 확인

### 성능 테스트
- 연속 24시간 운영 테스트
- 네트워크 지연 시 재연결 테스트
- 다중 클라이언트 동시 접속 테스트

---

## 🔐 보안 고려사항

⚠️ **주의**: 이 프로그램은 테스트용으로 보안 기능이 없습니다.

**프로덕션 환경에서는:**
- 인증/암호화 추가 (Modbus TCP over TLS)
- 방화벽 규칙 강화 (특정 IP만 허용)
- VPN 사용 권장
- 로그 모니터링

---

## 📈 확장 가능성

### 추가 개발 아이디어
- [ ] 실시간 차트 시각화 (Matplotlib, Plotly)
- [ ] 웹 대시보드 구축 (FastAPI + React)
- [ ] 알람 기능 (전력 임계값 초과 시 알림)
- [ ] 데이터베이스 연동 (PostgreSQL, InfluxDB)
- [ ] 여러 병원 동시 모니터링
- [ ] 모바일 앱 연동

---

## 📝 참고 자료

### Modbus 프로토콜
- [Modbus 공식 사이트](https://modbus.org/)
- [pymodbus 공식 문서](https://pymodbus.readthedocs.io/)

### 학습 자료
- 네트워크 기초: TCP/IP 프로토콜
- Modbus RTU vs Modbus TCP 차이
- Float → 레지스터 변환 (IEEE 754)

---

## 👨‍💻 개발자

- **프로젝트**: Modbus TCP 통신 테스트
- **목적**: 네트워크 통신 및 데이터 수집 학습
- **날짜**: 2025년 10월

---

## 📞 문의

문제가 발생하거나 질문이 있으시면:
1. 트러블슈팅 섹션 확인
2. pymodbus 버전 확인 (`pip show pymodbus`)
3. 네트워크 연결 상태 확인

---

## 📄 라이선스

이 프로젝트는 학습 및 테스트 목적으로 제공됩니다.

---

## ⚡ 빠른 시작 (Quick Start)

```
# 1. 라이브러리 설치
pip install pymodbus==3.5.4

# 2. PC 1 (서버) - 관리자 권한으로 실행
python modbus_server.py

# 3. PC 2 (클라이언트) - 서버 IP 입력 후 실행
python modbus_client.py

# 4. 데이터 확인
# power_data.csv 파일 열기
```

---