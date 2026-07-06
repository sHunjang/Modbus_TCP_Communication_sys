#!/usr/bin/env python3
# web_dashboard.py

"""
웹 기반 대시보드 서버 (standalone)

근로복지공단 등 외부에서 브라우저로 접속하여 실시간 모니터링
포트: 20000 (HTTP)

※ TCP 수신 없이 DB만 있는 환경에서 단독 실행 가능
※ /api/* 라우트는 core/web_routes.py 공통 Blueprint를 그대로 사용.
※ 사내망 전용으로 사용하기로 결정하여 API 키 인증은 적용하지 않음.
"""

import sys
import os

# [배포 수정] 두 가지 문제를 한 번에 방어한다.
# 1) console=False(창 없음) 빌드에서 sys.stdout/stderr가 None이 되는 문제
# 2) 한글 Windows 콘솔 기본 인코딩(cp949)이 이모지(✅⚠️❌ 등)를 인코딩 못 해
#    print() 호출 시 UnicodeEncodeError로 크래시하는 문제
# → stdout/stderr를 UTF-8로 강제 재설정(콘솔 있는 경우) 또는 UTF-8 devnull로 대체(없는 경우)
def _safe_stream(stream):
    if stream is None:
        return open(os.devnull, "w", encoding="utf-8", errors="replace")
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    except Exception:
        return open(os.devnull, "w", encoding="utf-8", errors="replace")

sys.stdout = _safe_stream(sys.stdout)
sys.stderr = _safe_stream(sys.stderr)

from flask import Flask
from flask_cors import CORS
from datetime import datetime

from core.database import DatabaseManager
from core.web_routes import dashboard_bp


app = Flask(__name__)
CORS(app)

db = DatabaseManager()
app.config["DB"] = db

app.register_blueprint(dashboard_bp)


def main():
    print("\n" + "=" * 70)
    print("🌐 웹 대시보드 서버 시작 (standalone)")
    print("=" * 70)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"로컬 접속: http://127.0.0.1:20000")
    print("=" * 70 + "\n")

    from waitress import serve
    serve(app, host='0.0.0.0', port=20000, threads=4)


if __name__ == "__main__":
    main()