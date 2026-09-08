"""Scroll area styling — avoids Win32 ghost window + slim scrollbar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea

from . import theme as T


def style_scroll_area(scroll: QScrollArea) -> None:
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
    scroll.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
    scroll.setAutoFillBackground(True)
    scroll.setStyleSheet(f"QScrollArea {{ background-color: {T.SURFACE}; border: none; }}")
    vp = scroll.viewport()
    vp.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
    vp.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
    vp.setAutoFillBackground(True)
    vp.setStyleSheet(f"background-color: {T.SURFACE};")
    content = scroll.widget()
    if content is not None:
        content.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        content.setAutoFillBackground(True)
