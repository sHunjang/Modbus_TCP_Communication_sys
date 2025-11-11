"""
UI 스타일 정의
"""

from PyQt6.QtGui import QPalette, QColor

class UIStyles:
    """
    UI 스타일 모음임.
    """
    
    @staticmethod
    def get_palette():
        """Application 색상 팔레드"""
        
        palette = QPalette()
        
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(200, 220, 255))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        return palette
    
    
    @staticmethod
    def export_button_style():
        """CSV 저장 버튼 스타일"""
        return """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """
    
    
    @staticmethod
    def add_button_style():
        """병원 추가 버튼 스타일"""
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
    
    
    @staticmethod
    def delete_button_style():
        """삭제 버튼 스타일"""
        return """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """
    
    
    @staticmethod
    def log_text_style():
        """로그 텍스트 스타일"""
        return """
            QPlainTextEdit {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
            }
        """
    
    
    @staticmethod
    def group_box_style():
        """그룹 박스 스타일"""
        return "QGroupBox { font-size: 13pt; font-weight: bold; }"