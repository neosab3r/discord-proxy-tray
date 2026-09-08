"""Build Windows app.ico from the tray SVG (multi-size ICO with PNG payloads).

Usage (from discord-proxy-tray root):
  .\\.venv\\Scripts\\python.exe scripts\\make_app_icon.py
"""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from PySide6.QtCore import QByteArray, Qt, QSize
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from discord_proxy_tray.ui.tray_icon import tray_svg_bytes

# Standard Windows shell sizes (16…256).
_SIZES = (16, 24, 32, 48, 64, 128, 256)
_OUT_ICO = ROOT / "src" / "discord_proxy_tray" / "ui" / "assets" / "app.ico"
_OUT_PNG = ROOT / "src" / "discord_proxy_tray" / "ui" / "assets" / "app-icon-256.png"


def _render_png(svg: bytes, size: int) -> bytes:
    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        raise RuntimeError("invalid tray SVG")
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    # QImage.save(QIODevice) is flaky on some PySide builds — use a temp file.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        if not image.save(str(tmp_path), "PNG"):
            raise RuntimeError(f"failed to encode PNG {size}x{size}")
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_ico(path: Path, pngs: list[tuple[int, bytes]]) -> None:
    """ICO with embedded PNGs (Vista+)."""
    count = len(pngs)
    offset = 6 + 16 * count
    chunks: list[bytes] = []
    header = struct.pack("<HHH", 0, 1, count)
    directory = bytearray()
    for size, data in pngs:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        chunks.append(data)
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(directory) + b"".join(chunks))


def main() -> int:
    app = QGuiApplication([])
    svg = tray_svg_bytes(tcp=True, desync=True)  # green "both" brand mark
    pngs = [(s, _render_png(svg, s)) for s in _SIZES]
    _write_ico(_OUT_ICO, pngs)
    _OUT_PNG.write_bytes(dict(pngs)[256])
    print(f"wrote {_OUT_ICO.relative_to(ROOT)} ({_OUT_ICO.stat().st_size} bytes)")
    print(f"wrote {_OUT_PNG.relative_to(ROOT)} (preview PNG, not used by Windows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
