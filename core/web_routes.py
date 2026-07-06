#!/usr/bin/env python3
# core/web_routes.py

"""
대시보드 웹 API 공통 라우트 (Flask Blueprint)

central_monitor.py(TCP+PyQt+웹 통합)와 web_dashboard.py(웹 standalone)가
동일한 API 라우트를 각자 중복 구현하던 것을 이 모듈 하나로 합쳤다.

사용법:
    from core.web_routes import dashboard_bp

    app = Flask(__name__)
    app.config['DB'] = db_manager_instance       # 필수
    app.config['API_KEY'] = 'xxxx'                # 선택 (없으면 '')
    app.register_blueprint(dashboard_bp)

라우트 함수들은 전역변수 대신 current_app.config['DB']를 통해 DB에 접근한다.
→ 앱 인스턴스 변수명(web_app vs app)이 달라도 동일한 Blueprint를 재사용 가능.
"""

import os
from datetime import date, datetime, timedelta
import secrets

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from core.csv_exporter import CSVExporter

dashboard_bp = Blueprint("dashboard_bp", __name__)

# def register_api_key_auth(app):
#     """
#     Flask 앱에 X-API-KEY 인증 훅을 등록한다.
#     central_monitor.py와 web_dashboard.py가 동일한 인증 로직을 쓰도록
#     공통 함수로 분리했다. app.config['API_KEY']가 비어있으면(빈 문자열)
#     인증을 아예 걸지 않는다 — 로컬 개발 중 임시로 인증을 끄고 싶을 때 사용.

#     Args:
#         app: Flask 앱 인스턴스 (app.config['API_KEY']가 미리 설정되어 있어야 함)
#     """
#     api_key = app.config.get("API_KEY", "")

#     if not api_key:
#         print("⚠️  API_KEY가 설정되지 않아 이 서버는 인증 없이 열려 있습니다.")
#         print("⚠️  외부에 노출되는 환경이라면 반드시 API_KEY를 설정하세요.")
#         return

#     @app.before_request
#     def _check_api_key():
#         if request.path == "/" or request.path.startswith("/static/"):
#             return
#         if request.path.startswith("/api/"):
#             provided_key = request.headers.get("X-API-KEY", "")
#             if not secrets.compare_digest(provided_key, api_key):
#                 return jsonify({"error": "인증 실패 (X-API-KEY 헤더 확인)"}), 401

def _get_db():
    """현재 Flask 앱에 등록된 DatabaseManager 인스턴스를 가져온다."""
    return current_app.config["DB"]


# ==================== 페이지 ====================
@dashboard_bp.route("/")
def index():
    return render_template("dashboard.html")


# ==================== 병원 목록 / 실시간 값 ====================
@dashboard_bp.route("/api/hospitals")
def get_hospitals_api():
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    return jsonify(db.get_hospitals())


@dashboard_bp.route("/api/latest_data")
def get_latest_data():
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500

    hospitals = db.get_hospitals()
    result = {}

    for hospital in hospitals:
        hospital_key = hospital["hospital_key"]
        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT timestamp, value FROM {table_name} ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            cursor.close()
            db.release_connection(conn)

            if row:
                result[hospital_key] = {
                    "value": float(row[1]),
                    "timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": hospital.get("ip_address", ""),
                    "port": hospital.get("port", 0),
                }
        except Exception as e:
            print(f"❌ {hospital_key} 데이터 조회 오류: {e}")

    return jsonify(result)


@dashboard_bp.route("/api/status")
def get_status():
    db = _get_db()
    return jsonify(
        {
            "db_connected": db.db_available,
            "hospital_count": len(db.get_hospitals()) if db.db_available else 0,
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


# ==================== 월별 사용량 ====================
@dashboard_bp.route("/api/monthly_usage/<hospital_key>")
def get_monthly_usage(hospital_key):
    """
    월별 전력 사용량 조회 (최근 13개월 + 전년 동월 비교)
    전력량계는 누적값이므로: 해당 월 사용량 = MAX(value) - MIN(value)
    """
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500

    # [보안] hospital_key는 외부 입력이므로 반드시 등록 여부까지 검증
    if not db.is_registered_hospital(hospital_key):
        return jsonify({"error": "등록되지 않았거나 잘못된 병원 코드입니다."}), 400

    table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT
                TO_CHAR(DATE_TRUNC('month', timestamp), 'YYYY-MM') AS month,
                MIN(value) AS first_value,
                MAX(value) AS last_value
            FROM {table_name}
            GROUP BY DATE_TRUNC('month', timestamp)
            ORDER BY DATE_TRUNC('month', timestamp) DESC
            LIMIT 25
        """)
        rows = cursor.fetchall()
        cursor.close()
        db.release_connection(conn)

        if not rows:
            return jsonify({"error": "데이터 없음"}), 404

        usage_map = {}
        for row in rows:
            month_str = row[0]
            first_val = float(row[1])
            last_val = float(row[2])
            usage = round(last_val - first_val, 2)
            usage_map[month_str] = max(usage, 0)

        today = date.today()
        months = []
        for i in range(12, -1, -1):
            year = today.year - (1 if today.month - i <= 0 else 0)
            month = (today.month - i - 1) % 12 + 1
            months.append(f"{year}-{month:02d}")

        usage_list = [usage_map.get(m) for m in months]
        prev_year_usage = [usage_map.get(f"{int(m[:4])-1}{m[4:]}") for m in months]

        return jsonify(
            {
                "hospital_key": hospital_key,
                "months": months,
                "usage": usage_list,
                "prev_year_usage": prev_year_usage,
            }
        )

    except Exception as e:
        print(f"❌ 월별 사용량 조회 오류 ({hospital_key}): {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 일별 사용량 (드릴다운) ====================
@dashboard_bp.route("/api/daily_usage/<hospital_key>/<int:year>/<int:month>")
def get_daily_usage(hospital_key, year, month):
    """
    특정 월의 일별(1일~말일) 전력 사용량 조회.
    generate_series로 그 달의 모든 날짜를 만든 뒤 LEFT JOIN하여
    데이터 없는 날은 날짜는 유지한 채 사용량만 null로 반환한다.
    """
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500

    if not db.is_registered_hospital(hospital_key):
        return jsonify({"error": "등록되지 않았거나 잘못된 병원 코드입니다."}), 400

    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        return jsonify({"error": "잘못된 연/월 값입니다."}), 400

    table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

    try:
        first_day = date(year, month, 1)
        next_month_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        last_day = next_month_first - timedelta(days=1)

        today = date.today()
        if (year, month) == (today.year, today.month):
            last_day = min(last_day, today)

        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            WITH days AS (
                SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS day
            )
            SELECT
                d.day,
                MIN(t.value) AS first_value,
                MAX(t.value) AS last_value
            FROM days d
            LEFT JOIN {table_name} t
                ON t.timestamp >= d.day AND t.timestamp < d.day + interval '1 day'
            GROUP BY d.day
            ORDER BY d.day
        """, (first_day, last_day))
        rows = cursor.fetchall()
        cursor.close()
        db.release_connection(conn)

        days = []
        usage = []
        for day, first_val, last_val in rows:
            days.append(day.day)
            if first_val is None or last_val is None:
                usage.append(None)
            else:
                daily_usage = round(float(last_val) - float(first_val), 2)
                usage.append(max(daily_usage, 0))

        return jsonify(
            {
                "hospital_key": hospital_key,
                "year": year,
                "month": month,
                "days": days,
                "usage": usage,
            }
        )

    except Exception as e:
        print(f"❌ 일별 사용량 조회 오류 ({hospital_key} {year}-{month}): {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 실시간 추이 (원시 데이터) ====================
@dashboard_bp.route("/api/recent_data/<hospital_key>")
def get_recent_data(hospital_key):
    """
    최근 N분간의 원시 수신 데이터 조회 (실시간 추이 그래프용).
    월별/일별 API와 달리 집계하지 않고 timestamp, value를 그대로 반환한다.

    Query params:
        minutes (int): 조회할 시간 범위 (기본 60, 1~1440 사이로 clamp)

    Returns:
        JSON: {
            "hospital_key": "ICN",
            "minutes": 60,
            "points": [{"timestamp": "2026-07-03 15:00:00", "value": 917123.45}, ...]
        }
    """
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500

    if not db.is_registered_hospital(hospital_key):
        return jsonify({"error": "등록되지 않았거나 잘못된 병원 코드입니다."}), 400

    try:
        minutes = int(request.args.get("minutes", 60))
    except (TypeError, ValueError):
        return jsonify({"error": "잘못된 minutes 값입니다."}), 400

    # [성능] 범위를 최대 24시간(1440분)으로 제한해서 과도한 조회를 방지
    minutes = max(1, min(minutes, 1440))

    table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"

    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT timestamp, value
            FROM {table_name}
            WHERE timestamp >= NOW() - (%s::text || ' minutes')::interval
            ORDER BY timestamp ASC
        """, (minutes,))
        rows = cursor.fetchall()
        cursor.close()
        db.release_connection(conn)

        points = [
            {"timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"), "value": float(row[1])}
            for row in rows
        ]

        return jsonify({
            "hospital_key": hospital_key,
            "minutes": minutes,
            "points": points,
        })

    except Exception as e:
        print(f"❌ 실시간 데이터 조회 오류 ({hospital_key}): {e}")
        return jsonify({"error": str(e)}), 500


# ==================== CSV 내보내기 ====================
@dashboard_bp.route("/api/export_csv/<hospital_key>")
def export_csv(hospital_key):
    db = _get_db()
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500

    if not db.is_registered_hospital(hospital_key):
        return jsonify({"error": "등록되지 않았거나 잘못된 병원 코드입니다."}), 400

    start_time = request.args.get("start")
    end_time = request.args.get("end")

    if not start_time or not end_time:
        return jsonify({"error": "시작/종료 시간이 필요합니다"}), 400

    try:
        start_dt = datetime.fromisoformat(start_time.replace("T", " ").replace("Z", ""))
        end_dt = datetime.fromisoformat(end_time.replace("T", " ").replace("Z", ""))
    except Exception as e:
        return jsonify({"error": f"시간 형식 오류: {e}"}), 400

    exporter = CSVExporter()
    success, filepath, message = exporter.export_hospital_data(db, hospital_key, start_dt, end_dt)

    if not success:
        return jsonify({"error": message}), 500

    return send_file(
        filepath,
        mimetype="text/csv",
        as_attachment=True,
        download_name=os.path.basename(filepath),
    )

# ==================== 시스템 로그 ====================
@dashboard_bp.route("/api/logs")
def get_logs():
    """
    시스템 로그 조회.

    central_monitor.py는 TCP 수신 로그(web_logs 큐)를 조회하는 함수를
    app.config['GET_LOGS_FUNC']로 등록해서 사용한다.
    web_dashboard.py처럼 TCP 서버가 없는 standalone 모드에서는
    이 설정이 없으므로 빈 배열을 반환한다 (404 대신 정상적인 "로그 없음").
    """
    get_logs_func = current_app.config.get("GET_LOGS_FUNC")
    if get_logs_func:
        return jsonify(get_logs_func())
    return jsonify([])