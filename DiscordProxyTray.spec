# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — onedir tray build (windowed, trimmed PySide6)."""

from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)
SRC = ROOT / "src"
PKG = SRC / "discord_proxy_tray"
ASSETS = PKG / "ui" / "assets"

# Qt Widgets tray app — drop QML/Quick/Pdf and other unused Qt stacks.
_SKIP_DLL_PARTS = (
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Pdf",
    "Qt6VirtualKeyboard",
    "Qt6Charts",
    "Qt6DataVisualization",
    "Qt6Graphs",
    "Qt6Multimedia",
    "Qt6WebEngine",
    "Qt6Location",
    "Qt6Sensors",
    "Qt6Bluetooth",
    "Qt6Nfc",
    "Qt6SerialPort",
    "Qt6RemoteObjects",
    "Qt6Scxml",
    "Qt3D",
    "Qt6HttpServer",
    "Qt6SpatialAudio",
    "Qt6TextToSpeech",
    "Qt6Designer",
    "Qt6Help",
    "Qt6UiTools",
    "Qt6OpenGLWidgets",
    "opengl32sw.dll",
)

_SKIP_PLUGIN_PARTS = (
    "plugins/platforminputcontexts/qtvirtualkeyboard",
    "plugins/generic/",
    "plugins/networkinformation/",
    "plugins/tls/",
    "plugins/imageformats/qjpeg",
    "plugins/imageformats/qwebp",
    "plugins/imageformats/qtiff",
    "plugins/imageformats/qtga",
    "plugins/imageformats/qpdf",
)


def _trim_binaries(binaries):
    kept = []
    for dest, src, typ in binaries:
        blob = f"{dest}/{src}".replace("\\", "/").lower()
        if any(part.lower() in blob for part in _SKIP_DLL_PARTS):
            continue
        if any(part.lower() in blob for part in _SKIP_PLUGIN_PARTS):
            continue
        kept.append((dest, src, typ))
    return kept


def _trim_datas(datas):
    kept = []
    for dest, src, typ in datas:
        src_norm = src.replace("\\", "/").lower()
        if "/translations/" in src_norm and src_norm.endswith(".qm"):
            continue
        kept.append((dest, src, typ))
    return kept


a = Analysis(
    [str(PKG / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(ASSETS), "discord_proxy_tray/ui/assets")],
    hiddenimports=[
        "PySide6.QtSvg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PIL",
        "Pillow",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtPdf",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a.binaries = _trim_binaries(a.binaries)
a.datas = _trim_datas(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DiscordProxyTray",
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
    icon=str(ASSETS / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DiscordProxyTray",
)
