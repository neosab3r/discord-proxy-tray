"""Overlay covering the Modes section (TUN emergency or DLL install)."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsBlurEffect,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme as T
from . import typography as TY
from .svg_icons import icon_pixmap

OverlayKind = Literal["none", "tun", "dll"]


class ModesTunHost(QWidget):
    """Hosts the Modes Section + blur overlay (TUN pause or DLL install)."""

    install_clicked = Signal()

    def __init__(self, section: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._section = section
        # Needed so QGraphicsBlurEffect actually paints the widget contents.
        self._section.setAutoFillBackground(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(section)

        self._overlay = QFrame(self)
        self._overlay.setObjectName("modesOverlay")
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._overlay.hide()

        inner = QVBoxLayout(self._overlay)
        inner.setContentsMargins(24, 20, 24, 20)
        inner.setSpacing(0)

        self._block = QWidget(self._overlay)
        self._block.setObjectName("modesOverlayBlock")
        self._block.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._block.setAutoFillBackground(False)
        self._block.setStyleSheet(
            "QWidget#modesOverlayBlock { background: transparent; border: none; }"
        )
        self._block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        block_lay = QVBoxLayout(self._block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(8)
        block_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("background: transparent; border: none;")
        block_lay.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title.setFont(TY.setting_font())
        self._title.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none;"
        )
        block_lay.addWidget(self._title)

        self._sub = QLabel()
        self._sub.setWordWrap(True)
        self._sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._sub.setFont(TY.ui_sm_font())
        self._sub.setStyleSheet(
            f"color: {T.MUTED}; background: transparent; border: none;"
        )
        block_lay.addWidget(self._sub)

        self._install_btn = QPushButton()
        self._install_btn.setFont(TY.button_font())
        self._install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_btn.setStyleSheet(
            f"QPushButton {{ background-color: {T.ACCENT}; color: {T.TEXT}; "
            f"border: none; border-radius: 5px; padding: 3px 10px; min-height: 22px; "
            f"font-size: 12px; }}"
            f"QPushButton:hover:enabled {{ background-color: #5fd4ba; color: {T.TEXT}; }}"
            f"QPushButton:disabled {{ background-color: {T.SURFACE_2}; color: {T.FAINT}; "
            f"border: 1px solid {T.LINE}; }}"
        )
        self._install_btn.clicked.connect(self.install_clicked.emit)
        self._install_btn.hide()
        block_lay.addWidget(self._install_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        inner.addStretch(1)
        inner.addWidget(self._block)
        inner.addStretch(1)

        self._kind: OverlayKind = "none"
        self._tun_title = ""
        self._tun_sub = ""
        self._dll_title = ""
        self._dll_sub = ""
        self._dll_btn = ""

    def set_tun_copy(self, title: str, subtitle: str) -> None:
        self._tun_title = title
        self._tun_sub = subtitle
        if self._kind == "tun":
            self._title.setText(title)
            self._sub.setText(subtitle)
            self._update_label_widths()

    def set_dll_copy(self, title: str, subtitle: str, button: str) -> None:
        self._dll_title = title
        self._dll_sub = subtitle
        self._dll_btn = button
        if self._kind == "dll":
            self._title.setText(title)
            self._sub.setText(subtitle)
            self._install_btn.setText(button)
            self._update_label_widths()

    def set_copy(self, title: str, subtitle: str) -> None:
        """Back-compat: TUN overlay strings."""
        self.set_tun_copy(title, subtitle)

    def set_paused(self, paused: bool) -> None:
        """Back-compat: TUN-only pause flag (prefer set_overlay)."""
        if paused:
            self.set_overlay("tun")
        elif self._kind == "tun":
            self.set_overlay("none")

    def set_overlay(self, kind: OverlayKind) -> None:
        """
        Idempotent. Qt owns QGraphicsEffect — recreate only when entering
        a blocked state from none / switching kinds that need a fresh effect.
        """
        if kind == self._kind:
            if kind != "none":
                self._ensure_blur()
                self._overlay.raise_()
                self._sync_overlay_geom()
            return

        prev = self._kind
        self._kind = kind

        if kind == "none":
            if prev != "none":
                self._section.setGraphicsEffect(None)
                self._overlay.hide()
                self._install_btn.hide()
            return

        self._ensure_blur()

        if kind == "tun":
            self._apply_tun_style()
            self._title.setText(self._tun_title)
            self._sub.setText(self._tun_sub)
            self._install_btn.hide()
        else:
            self._apply_dll_style()
            self._title.setText(self._dll_title)
            self._sub.setText(self._dll_sub)
            self._install_btn.setText(self._dll_btn)
            self._install_btn.setEnabled(True)
            self._install_btn.show()

        self._overlay.show()
        self._overlay.raise_()
        self._sync_overlay_geom()

    def set_install_busy(self, busy: bool) -> None:
        self._install_btn.setEnabled(not busy)

    def _ensure_blur(self) -> None:
        effect = self._section.graphicsEffect()
        if isinstance(effect, QGraphicsBlurEffect):
            effect.setBlurRadius(10)
            return
        blur = QGraphicsBlurEffect(self._section)
        blur.setBlurRadius(10)
        self._section.setGraphicsEffect(blur)

    def _apply_tun_style(self) -> None:
        self._overlay.setStyleSheet(
            f"QFrame#modesOverlay {{ background: rgba(18, 20, 26, 0.72); "
            f"border: none; }}"
        )
        pix = icon_pixmap("triangle-alert", 18, color=T.DANGER)
        if not pix.isNull():
            self._icon.setPixmap(pix)

    def _apply_dll_style(self) -> None:
        self._overlay.setStyleSheet(
            f"QFrame#modesOverlay {{ background: rgba(18, 20, 26, 0.72); "
            f"border: none; }}"
        )
        pix = icon_pixmap("info", 18, color=T.STREAM)
        if not pix.isNull():
            self._icon.setPixmap(pix)

    def _update_label_widths(self) -> None:
        text_w = max(160, self._overlay.width() - 48)
        self._title.setFixedWidth(text_w)
        self._sub.setFixedWidth(text_w)
        self._block.adjustSize()

    def _sync_overlay_geom(self) -> None:
        self._overlay.setGeometry(self.rect())
        self._update_label_widths()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._kind != "none":
            self._sync_overlay_geom()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._kind != "none":
            self._ensure_blur()
            self._overlay.raise_()
            self._sync_overlay_geom()
