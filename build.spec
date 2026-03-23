# PyInstaller spec — run with: pyinstaller build.spec
#
# Mac:    produces dist/ZohoETL.app  (onedir, windowed)
# Windows: produces dist/ZohoETL.exe (onefile, windowed)
#
# Build commands:
#   Mac:     pyinstaller build.spec
#   Windows: pyinstaller build.spec

import sys
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config.ini.example', '.'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='ZohoETL',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=False,
        upx_exclude=[],
        name='ZohoETL',
    )
    app = BUNDLE(
        coll,
        name='ZohoETL.app',
        icon=None,
        bundle_identifier='com.yourcompany.zoho-etl',
        info_plist={
            'NSHighResolutionCapable': True,
        },
    )
else:
    # Windows — single executable
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name='ZohoETL',
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
        icon=None,
    )
