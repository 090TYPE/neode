# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NeoIDE.  Build with:  pyinstaller build.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('themes', 'themes'),
        ('plugins', 'plugins'),
        ('assets', 'assets'),
    ],
    hiddenimports=['PyQt6.Qsci'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NeoIDE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/icons/app.ico' if __import__('os').path.exists('assets/icons/app.ico') else None,
)
