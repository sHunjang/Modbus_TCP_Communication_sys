# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs

psycopg2_binaries = collect_dynamic_libs('psycopg2')

block_cipher = None

a = Analysis(
    ['web_dashboard.py'],
    pathex=[],
    binaries=psycopg2_binaries,
    datas=[
        ('templates/*', 'templates'),
        ('static/css/*', 'static/css'),
        ('static/js/*', 'static/js'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'waitress',
        'psycopg2',
        'psycopg2._psycopg',
        'core.database',
        'core.csv_exporter',
        'core.web_routes',
        'werkzeug',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'PIL',
        'tkinter',
        'PyQt6',
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
    name='WebDashboard',
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
    icon=None
)
