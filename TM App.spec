# -*- mode: python ; coding: utf-8 -*-
# TM App v1.0.0, standalone Windows executable.


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('machines.json', '.'),
        ('assets/tm-app.ico', 'assets'),
        ('assets/tm-device-icon-small.png', 'assets'),
        ('assets/tm-device-icon-header.png', 'assets'),
    ],
    hiddenimports=[],
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
    name='TM App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='assets/tm-app.ico',
    version='version_info.txt',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
