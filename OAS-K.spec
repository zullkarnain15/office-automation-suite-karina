# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('assets', 'assets'),
    (
        'config/attendance/OAS-K_Attendance_Configuration.xlsx',
        'config/attendance',
    ),
    (
        'config/hris/OAS-K_HRIS_Configuration.xlsx',
        'config/hris',
    ),
    (
        'config/outlook/OAS-K_Outlook-Revisi_Configuration.xlsx',
        'config/outlook',
    ),
]
binaries = []
hiddenimports = [
    'hris.batch_uploader',
    'hris.browser',
    'hris.diagnostics',
    'hris.file_manager',
    'hris.navigator',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    'win32timezone',
]
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyautogui')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OAS-K',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\app.ico'],
)
