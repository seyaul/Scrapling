# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['toolGUI.py'],
    pathex=[],
    binaries=[],
    datas=[('images/hana_logo.png', 'images'), 
        ('browserforge/*', 'browserforge'),
        ('camoufox/*', 'camoufox'),
        ('language_tags/*', 'language_tags'),
        ('scraplingAdaptationHana/safeway/*', 'scraplingAdaptationHana/safeway'),
        ('scraplingAdaptationHana/giant/*', 'scraplingAdaptationHana/giant')],
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
    [],
    exclude_binaries=True,
    name='HanaTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['MyIcon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HanaTool',
)
app = BUNDLE(
    coll,
    name='HanaTool.app',
    icon='MyIcon.icns',
    bundle_identifier=None,
)
