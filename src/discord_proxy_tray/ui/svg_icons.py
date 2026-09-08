"""Load Lucide SVG icons for the panel (PySide6 QtSvg)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme as T

_ICONS_DIR = Path(__file__).resolve().parent / "assets" / "icons"

# Lucide names used in the app — files: assets/icons/{name}.svg
LUCIDE_ICONS = (
    "info",
    "check",
    "save",
    "folder-open",
    "refresh-cw",
    "copy",
    "triangle-alert",
    "chevron-down",
    "chevron-right",
    "circle-dot",
    "star",
    "trash-2",
    "loader-2",
)


def icons_dir() -> Path:
    return _ICONS_DIR


def _resolve_file(name: str) -> Path | None:
    path = _ICONS_DIR / f"{name}.svg"
    return path if path.is_file() else None


def _tint_svg(raw: str, color: str) -> str:
    """Lucide uses stroke=currentColor; replace with theme color."""
    out = raw.replace("currentColor", color)
    return out


@lru_cache(maxsize=128)
def _render_svg_data_cached(svg_data: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    if renderer.isValid():
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(p)
        p.end()
    return pixmap


@lru_cache(maxsize=128)
def _render_svg_cached(file_path: str, size: int, color: str) -> QPixmap:
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8")
    data = _tint_svg(raw, color)
    return _render_svg_data_cached(data, size)


def star_pixmap(size: int = 12, *, filled: bool = False, color: str | None = None) -> QPixmap:
    path = _resolve_file("star")
    if path is None:
        return QPixmap()
    raw = path.read_text(encoding="utf-8")
    tint = color or (T.STREAM if filled else T.FAINT)
    if filled:
        svg = raw.replace('fill="none"', f'fill="{tint}"').replace("currentColor", tint)
    else:
        svg = _tint_svg(raw, tint)
    return _render_svg_data_cached(svg, size)


def icon_pixmap(name: str, size: int = 16, *, color: str | None = None) -> QPixmap:
    path = _resolve_file(name)
    if path is None:
        return QPixmap()
    tint = color or T.MUTED
    return _render_svg_cached(str(path.resolve()), size, tint)


def icon(name: str, size: int = 16, *, color: str | None = None) -> QIcon:
    pix = icon_pixmap(name, size, color=color)
    if pix.isNull():
        return QIcon()
    return QIcon(pix)


def icon_button(
    button,
    name: str,
    size: int = 14,
    *,
    color: str | None = None,
    text_right: bool = True,
) -> None:
    """Prepend Lucide icon to QPushButton."""
    ic = icon(name, size, color=color or T.MUTED)
    if not ic.isNull():
        button.setIcon(ic)
        button.setIconSize(QSize(size, size))
    if text_right:
        from PySide6.QtCore import Qt as QtCore

        button.setLayoutDirection(QtCore.LayoutDirection.LeftToRight)
