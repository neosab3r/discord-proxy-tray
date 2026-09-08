"""Custom panel title bar (mock chrome — tray icon, title, min/close)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from ..elevation import is_admin
from .i18n import I18n
from .icons import make_tray_icon
from .svg_icons import icon
from . import theme as T
from . import typography as TY

if TYPE_CHECKING:
    from ..app import TrayApp


class PanelTitleBar(QFrame):
    minimize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, window: QWidget, app: TrayApp, i18n: I18n) -> None:
        super().__init__(window)
        self._window = window
        self._app = app
        self.i18n = i18n
        self._drag_pos: QPoint | None = None

        self.setObjectName("titleBar")
        self.setFixedHeight(T.TITLE_BAR_H)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 4, 0)
        row.setSpacing(8)

        self._icon = QLabel()
        self._icon.setFixedSize(15, 15)
        self._icon.setScaledContents(True)
        self._icon.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")

        self._title = QLabel()
        self._title.setFont(TY.ui_sm_font(weight=TY.SEMI_WEIGHT))
        self._title.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none; "
            f"padding: 0; margin: 0; text-decoration: none;"
        )

        row.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._title, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)

        controls = QHBoxLayout()
        controls.setSpacing(2)
        controls.setContentsMargins(0, 0, 0, 0)

        self._btn_min = self._make_win_btn("minus", "min", 13)
        self._btn_min.clicked.connect(self.minimize_clicked.emit)
        self._btn_min.setToolTip("Minimize")

        self._btn_close = self._make_win_btn("x", "close", 14)
        self._btn_close.clicked.connect(self.close_clicked.emit)
        self._btn_close.setToolTip("Close")

        controls.addWidget(self._btn_min)
        controls.addWidget(self._btn_close)
        row.addLayout(controls)

        self.refresh()

    def _make_win_btn(self, icon_name: str, role: str, size: int) -> QPushButton:
        btn = QPushButton()
        btn.setProperty("winBtn", role)
        btn.setFixedSize(36, 28)
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ic = icon(icon_name, size, color=T.MUTED)
        if not ic.isNull():
            btn.setIcon(ic)
            btn.setIconSize(QSize(size, size))
        return btn

    def _click_on_button(self, pos: QPoint) -> bool:
        w = self.childAt(pos)
        while w is not None and w is not self:
            if isinstance(w, QPushButton):
                return True
            w = w.parentWidget()
        return False

    def refresh(self) -> None:
        stream_on = self._app.stream_toggle_display()
        pix = make_tray_icon(self._app.config.tcp_proxy, stream_on).pixmap(15, 15)
        self._icon.setPixmap(pix)
        base = self.i18n.t("panel.titleBase")
        admin = self.i18n.t("panel.asAdmin" if is_admin() else "panel.notAsAdmin")
        self._title.setText(f"{base} — {admin}")
        ic_min = icon("minus", 13, color=T.MUTED)
        if not ic_min.isNull():
            self._btn_min.setIcon(ic_min)
        ic_close = icon("x", 14, color=T.MUTED)
        if not ic_close.isNull():
            self._btn_close.setIcon(ic_close)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._click_on_button(event.position().toPoint())
        ):
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.minimize_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
