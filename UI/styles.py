#!/usr/bin/env python3
# UI/styles.py

"""
UI 스타일 정의

기능:
- 컬러 팔레트 설정
- 위젯별 스타일시트 제공
- 일관된 디자인 유지
"""

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt


class UIStyles:
    """UI 스타일 클래스"""

    @staticmethod
    def get_palette():
        """
        애플리케이션 컬러 팔레트 생성
        
        Returns:
            QPalette: 전체 앱에 적용할 팔레트
        """
        palette = QPalette()
        
        # 기본 배경/전경색
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        
        # 버튼 색상
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        
        # 텍스트 입력 필드
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        
        # 하이라이트
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        return palette

    @staticmethod
    def group_box_style():
        """
        QGroupBox 스타일
        
        Returns:
            str: GroupBox용 스타일시트
        """
        return """
            QGroupBox {
                font-size: 14pt;
                font-weight: bold;
                border: 2px solid #0078D7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """

    @staticmethod
    def delete_button_style():
        """
        삭제 버튼 스타일
        
        Returns:
            str: 삭제 버튼용 스타일시트
        """
        return """
            QPushButton {
                background-color: #D32F2F;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B71C1C;
            }
            QPushButton:pressed {
                background-color: #8B0000;
            }
        """

    @staticmethod
    def primary_button_style():
        """
        기본 버튼 스타일 (파란색)
        
        Returns:
            str: 기본 버튼용 스타일시트
        """
        return """
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
        """

    @staticmethod
    def secondary_button_style():
        """
        보조 버튼 스타일 (회색)
        
        Returns:
            str: 보조 버튼용 스타일시트
        """
        return """
            QPushButton {
                background-color: #E0E0E0;
                color: black;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
        """

    @staticmethod
    def success_button_style():
        """
        성공 버튼 스타일 (녹색)
        
        Returns:
            str: 성공 버튼용 스타일시트
        """
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
            QPushButton:pressed {
                background-color: #3D8B40;
            }
        """

    @staticmethod
    def table_style():
        """
        QTableWidget 스타일
        
        Returns:
            str: 테이블용 스타일시트
        """
        return """
            QTableWidget {
                background-color: white;
                alternate-background-color: #F5F5F5;
                gridline-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
            QHeaderView::section {
                background-color: #F0F0F0;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #0078D7;
                font-weight: bold;
            }
        """

    @staticmethod
    def log_style():
        """
        로그 텍스트 영역 스타일
        
        Returns:
            str: 로그용 스타일시트
        """
        return """
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """

    @staticmethod
    def status_good():
        """
        정상 상태 색상
        
        Returns:
            QColor: 녹색
        """
        return QColor(0, 150, 0)

    @staticmethod
    def status_warning():
        """
        경고 상태 색상
        
        Returns:
            QColor: 주황색
        """
        return QColor(255, 140, 0)

    @staticmethod
    def status_error():
        """
        오류 상태 색상
        
        Returns:
            QColor: 빨간색
        """
        return QColor(200, 0, 0)

    @staticmethod
    def status_info():
        """
        정보 색상
        
        Returns:
            QColor: 파란색
        """
        return QColor(0, 120, 215)
