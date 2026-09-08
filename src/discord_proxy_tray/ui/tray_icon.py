"""Tray icon from design mock (chrome.tsx TrayIcon) — SVG generated in code."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# chrome.tsx STATE_COLORS
_TRAY_FILL = {
    "both": "#43b675",
    "tcp": "#4d8fea",
    "stream": "#e0a63e",
    "off": "#c94f4f",
}

_TRAY_SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="10" fill="{fill}"/>
  <rect x="6.4" y="9.2" width="2.6" height="5.6" rx="1.3" fill="#0c0e12" opacity="0.92"/>
  <rect x="10.7" y="6.6" width="2.6" height="10.8" rx="1.3" fill="#0c0e12" opacity="0.92"/>
  <rect x="15" y="10.2" width="2.6" height="3.6" rx="1.3" fill="#0c0e12" opacity="0.92"/>
  <circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.75"/>
</svg>
"""


def tray_state(tcp: bool, desync: bool) -> str:
    if tcp and desync:
        return "both"
    if tcp:
        return "tcp"
    if desync:
        return "stream"
    return "off"


def tray_svg_bytes(tcp: bool, desync: bool) -> bytes:
    state = tray_state(tcp, desync)
    fill = _TRAY_FILL[state]
    return _TRAY_SVG_TEMPLATE.format(fill=fill).encode("utf-8")


def write_tray_icon_svg(path, tcp: bool = True, desync: bool = True) -> None:
    """Write reference SVG (e.g. assets/icons/tray-icon-both.svg)."""
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(tray_svg_bytes(tcp, desync))


def make_tray_icon(tcp: bool, desync: bool, size: int = 64) -> QIcon:
    data = tray_svg_bytes(tcp, desync)
    renderer = QSvgRenderer(QByteArray(data))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    if renderer.isValid():
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(p)
        p.end()
    return QIcon(pixmap)
