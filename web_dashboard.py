#!/usr/bin/env python3
# web_dashboard.py

"""
웹 기반 대시보드 서버

근로복지공단 등 외부에서 브라우저로 접속하여 실시간 모니터링
포트: 20000 (HTTP)
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime
import threading
import os

from core.database import DatabaseManager


# ==================== Flask 앱 설정 ====================
app = Flask(__name__)
CORS(app)  # CORS 허용 (외부 접속)

# DB 인스턴스
db = DatabaseManager()


# ==================== API 엔드포인트 ====================
@app.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html')


@app.route('/api/hospitals')
def get_hospitals_api():
    """
    등록된 병원 목록 조회
    
    Returns:
        JSON: [{"hospital_key": "ICN", "ip_address": "...", ...}]
    """
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    hospitals = db.get_hospitals()
    return jsonify(hospitals)


@app.route('/api/latest_data')
def get_latest_data():
    """
    모든 병원의 최신 전력량 데이터 조회
    
    Returns:
        JSON: {
            "ICN": {"value": 7584.55, "timestamp": "2025-11-24 11:15:00"},
            ...
        }
    """
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    hospitals = db.get_hospitals()
    result = {}
    
    for hospital in hospitals:
        hospital_key = hospital['hospital_key']
        table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"
        
        try:
            # 최신 데이터 1개 조회
            conn = db.get_connection()
            cursor = conn.cursor()
            
            query = f"""
                SELECT timestamp, value
                FROM {table_name}
                ORDER BY timestamp DESC
                LIMIT 1
            """
            cursor.execute(query)
            row = cursor.fetchone()
            
            cursor.close()
            db.release_connection(conn)
            
            if row:
                result[hospital_key] = {
                    "value": float(row[1]),
                    "timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": hospital.get('ip_address', ''),
                    "port": hospital.get('port', 0)
                }
        except Exception as e:
            print(f"❌ {hospital_key} 데이터 조회 오류: {e}")
    
    return jsonify(result)


@app.route('/api/hospital_data/<hospital_key>')
def get_hospital_data(hospital_key):
    """
    특정 병원의 최근 데이터 조회
    
    Args:
        hospital_key: 병원 식별자 (예: ICN)
        limit: 최대 개수 (쿼리 파라미터, 기본 100)
    
    Returns:
        JSON: [{"timestamp": "...", "value": 7584.55}, ...]
    """
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    limit = request.args.get('limit', 100, type=int)
    
    table_name = f"hospital_{hospital_key.replace('.', '_').replace(':', '_')}"
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        query = f"""
            SELECT timestamp, value
            FROM {table_name}
            ORDER BY timestamp DESC
            LIMIT %s
        """
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        cursor.close()
        db.release_connection(conn)
        
        result = []
        for row in rows:
            result.append({
                "timestamp": row[0].strftime("%Y-%m-%d %H:%M:%S"),
                "value": float(row[1])
            })
        
        # 시간 순서대로 정렬 (오름차순)
        result.reverse()
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status')
def get_status():
    """
    시스템 상태 조회
    
    Returns:
        JSON: {"db_connected": true, "hospital_count": 3, "server_time": "..."}
    """
    return jsonify({
        "db_connected": db.db_available,
        "hospital_count": len(db.get_hospitals()) if db.db_available else 0,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/export_csv/<hospital_key>')
def export_csv(hospital_key):
    """
    CSV 내보내기 API
    
    Args:
        hospital_key: 병원 식별자
        start: 시작 시간 (YYYY-MM-DDTHH:MM 형식)
        end: 종료 시간 (YYYY-MM-DDTHH:MM 형식)
    
    Returns:
        CSV 파일 다운로드
    """
    if not db.db_available:
        return jsonify({"error": "DB 연결 안됨"}), 500
    
    # 쿼리 파라미터 가져오기
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    
    if not start_time or not end_time:
        return jsonify({"error": "시작/종료 시간이 필요합니다"}), 400
    
    try:
        # 시간 형식 변환 (ISO 8601 → datetime)
        start_dt = datetime.fromisoformat(start_time.replace('T', ' ').replace('Z', ''))
        end_dt = datetime.fromisoformat(end_time.replace('T', ' ').replace('Z', ''))
    except Exception as e:
        return jsonify({"error": f"시간 형식 오류: {e}"}), 400
    
    # CSV exporter 사용
    from core.csv_exporter import CSVExporter
    exporter = CSVExporter()
    
    success, filepath, message = exporter.export_hospital_data(
        db,
        hospital_key,
        start_dt,
        end_dt
    )
    
    if not success:
        return jsonify({"error": message}), 500
    
    # CSV 파일 전송
    return send_file(
        filepath,
        mimetype='text/csv',
        as_attachment=True,
        download_name=os.path.basename(filepath)
    )


# ==================== 메인 ====================
def main():
    """웹 서버 시작"""
    print("\n" + "=" * 70)
    print("🌐 웹 대시보드 서버 시작")
    print("=" * 70)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"로컬 접속: http://127.0.0.1:20000")
    print(f"내부망 접속: http://192.168.0.x:20000")
    print(f"외부 접속: http://14.42.209.171:20000")
    print("=" * 70 + "\n")
    
    # Waitress 사용 (운영 환경 적합)
    from waitress import serve
    serve(app, host='0.0.0.0', port=20000, threads=4)


if __name__ == "__main__":
    main()
