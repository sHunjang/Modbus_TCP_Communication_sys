#!/usr/bin/env python3
# main.py

"""
병원 전력량 모니터링 시스템 - 메인 실행 파일
"""

import sys
from datetime import datetime
from PyQt6.QtWidgets import QApplication

from UI import MainWindow, UIStyles
from core.database import DatabaseManager


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🏥 병원 전체전력량 모니터링 시스템 v1.0")
    print("="*60)
    print("📅 시작 시간:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60 + "\n")
    
    # ✅ 더미 모드 설정
    USE_DUMMY_MODE = False
    
    if USE_DUMMY_MODE:
        print("🔌 더미 모드 실행 중... (가상 데이터)\n")
    else:
        print("📡 실제 모드 실행 중... (HMI 통신)\n")
    
    # Qt 애플리케이션 생성
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 색상 팔레트 적용
    app.setPalette(UIStyles.get_palette())
    
    # 데이터베이스 초기화
    database = DatabaseManager()
    
    # 메인 윈도우 생성
    window = MainWindow(database=database, use_dummy=USE_DUMMY_MODE)
    window.show()
    
    print("✅ 프로그램 실행 완료!")
    print("="*60 + "\n")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
