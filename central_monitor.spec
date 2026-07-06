# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs

psycopg2_binaries = collect_dynamic_libs('psycopg2')

block_cipher = None

a = Analysis(
    ['central_monitor.py'],
    pathex=[],
    binaries=psycopg2_binaries,
    datas=[
        ('templates/*', 'templates'),
        ('static/css/*', 'static/css'),
        ('static/js/*', 'static/js'),
    ],
    hiddenimports=[
        # PostgreSQL
        'psycopg2',
        'psycopg2._psycopg',
        
        # PyQt6
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        
        # Flask
        'flask',
        'flask_cors',
        'waitress',
        'werkzeug',
        'jinja2',
        
        # Core 모듈
        'core.database',
        'core.csv_exporter',
        'core.web_routes',
        
        # UI 모듈 (추가)
        'UI.main_window',
        'UI.styles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'PIL',
        'tkinter',
        'PySide6',          
        'PySide6.QtCore',   
        'PySide6.QtGui',    
        'PySide6.QtWidgets',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CentralMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
