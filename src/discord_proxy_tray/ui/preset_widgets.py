"""Presets tab widgets — rows, chips, group headers (design mock)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..presets import PresetSource
from . import theme as T
from .svg_icons import icon_pixmap, star_pixmap
from .widgets import StatusChip
from . import typography as TY


_GROUP_TONE: dict[PresetSource, str] = {
    "local": "tcp",
    "remote": "accent",
    "shipped": "idle",
}


class PresetNameChip(QFrame):
    """Active preset name — bordered chip on surface-2."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("presetNameChip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        self._label = QLabel(text)
        self._label.setFont(TY.mono_lg_font())
        self._label.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none; padding: 0;"
        )
        lay.addWidget(self._label)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def setText(self, text: str) -> None:  # noqa: N802
        self._label.setText(text)


class PresetIconButton(QToolButton):
    """24×24 icon action (star / trash) on preset rows."""

    def __init__(
        self,
        icon_name: str,
        *,
        size: int = 12,
        color: str | None = None,
        tooltip: str = "",
        filled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = size
        self._color = color or T.FAINT
        self._filled = filled
        self.setFixedSize(24, 24)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setStyleSheet(
            "QToolButton { background: transparent; border: none; border-radius: 4px; }"
            f"QToolButton:hover {{ background: rgba(42, 49, 64, 0.45); }}"
        )
        self._apply_icon()

    def _apply_icon(self) -> None:
        from PySide6.QtGui import QIcon

        if self._icon_name == "star":
            pix = star_pixmap(self._icon_size, filled=self._filled, color=self._color)
        else:
            pix = icon_pixmap(self._icon_name, self._icon_size, color=self._color)
        if not pix.isNull():
            self.setIcon(QIcon(pix))
            self.setIconSize(QSize(self._icon_size, self._icon_size))

    def set_star_filled(self, filled: bool) -> None:
        self._filled = filled
        self._color = T.STREAM if filled else T.FAINT
        self._apply_icon()


class PresetListRow(QWidget):
    """Selectable preset row — circle-dot, name, active badge, star, optional trash."""

    activated = Signal()
    star_clicked = Signal()
    delete_clicked = Signal()

    def __init__(
        self,
        name: str,
        src: PresetSource,
        *,
        delete_tooltip: str = "",
        favorite_tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._src = src
        self._selected = False
        self._hover = False
        self.setObjectName("presetListRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 4, 0)
        row.setSpacing(10)

        self._dot = QLabel()
        self._dot.setFixedSize(13, 13)
        self._dot.setScaledContents(True)

        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(TY.mono_row_font())
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none;"
        )

        self._active_badge = QLabel()
        self._active_badge.setFont(TY.mono_xs_font())
        self._active_badge.setStyleSheet(
            f"color: {T.ACCENT}; background: transparent; border: none; "
            f"letter-spacing: 0.8px;"
        )
        self._active_badge.hide()

        row.addWidget(self._dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._name_lbl, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._active_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        if src == "local":
            self._delete_btn = PresetIconButton(
                "trash-2", size=12, color=T.FAINT, tooltip=delete_tooltip, parent=self
            )
            self._delete_btn.clicked.connect(self._on_delete)
            self._delete_btn.setStyleSheet(
                "QToolButton { background: transparent; border: none; border-radius: 4px; }"
                f"QToolButton:hover {{ background: rgba(232, 93, 93, 0.1); color: {T.DANGER}; }}"
            )
            row.addWidget(self._delete_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        else:
            self._delete_btn = None

        self._star_btn = PresetIconButton(
            "star", size=12, tooltip=favorite_tooltip, parent=self
        )
        self._star_btn.clicked.connect(self._on_star)
        row.addWidget(self._star_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._apply_style()

    @property
    def preset_name(self) -> str:
        return self._name

    @property
    def preset_src(self) -> PresetSource:
        return self._src

    def configure(
        self,
        *,
        selected: bool,
        is_active: bool,
        is_favorite: bool,
        active_label: str,
    ) -> None:
        self._selected = selected
        dot_color = T.ACCENT if selected else T.FAINT
        pix = icon_pixmap("circle-dot", 13, color=dot_color)
        if pix.isNull():
            self._dot.clear()
        else:
            self._dot.setPixmap(pix)
        self._dot.setStyleSheet(
            "background: transparent; border: none; padding: 0;"
            + ("" if selected else " opacity: 0.4;")
        )

        if is_active:
            self._active_badge.setText(active_label.upper())
            self._active_badge.show()
        else:
            self._active_badge.hide()

        self._star_btn.set_star_filled(is_favorite)
        self._selected = selected
        self._apply_style()

    def set_selected(self, selected: bool) -> None:
        self.configure(
            selected=selected,
            is_active=self._active_badge.isVisible(),
            is_favorite=self._star_btn._filled,
            active_label=self._active_badge.text(),
        )

    def _apply_style(self) -> None:
        if self._selected:
            bg = T.SURFACE_2
        elif self._hover:
            bg = "rgba(34, 38, 51, 0.6)"
        else:
            bg = "transparent"
        self.setStyleSheet(
            f"QWidget#presetListRow {{ background-color: {bg}; border-radius: 6px; }}"
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if self._star_btn.geometry().contains(pos):
                super().mousePressEvent(event)
                return
            if self._delete_btn is not None and self._delete_btn.geometry().contains(pos):
                super().mousePressEvent(event)
                return
            self.activated.emit()
        super().mousePressEvent(event)

    def _on_star(self) -> None:
        self.star_clicked.emit()

    def _on_delete(self) -> None:
        self.delete_clicked.emit()


class PresetGroupBlock(QFrame):
    """Collapsible group — header + divider + body."""

    toggled = Signal()

    def __init__(
        self,
        src: PresetSource,
        *,
        title: str,
        hint: str,
        count: int,
        open: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._src = src
        self._open = open
        self.setObjectName("groupBlock")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = QPushButton()
        self._header.setProperty("groupHeader", True)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        hdr_lay = QHBoxLayout(self._header)
        hdr_lay.setContentsMargins(8, 6, 8, 6)
        hdr_lay.setSpacing(8)

        self._chev = QLabel()
        self._chev.setFixedSize(14, 14)
        self._chip = StatusChip()
        self._chip.set_label_font(
            TY.faint_sm_font(mono=True, weight=QFont.Weight.Medium)
        )
        self._chip.configure(text=title, tone=_GROUP_TONE[src])  # type: ignore[arg-type]
        self._count = QLabel(str(count))
        self._count.setFont(TY.mono_sm_font())
        self._count.setProperty("role", "faint")
        self._count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count.setFixedHeight(24)
        self._count.setMinimumWidth(14)
        self._count.setStyleSheet(
            f"color: {T.FAINT}; background: transparent; border: none; padding: 0;"
        )
        self._hint = QLabel(hint)
        self._hint.setFont(TY.ui_sm_font(weight=QFont.Weight.Normal))
        self._hint.setProperty("role", "muted")
        self._hint.setStyleSheet(
            f"color: {T.MUTED}; background: transparent; border: none;"
        )
        self._hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        hdr_lay.addWidget(self._chev, alignment=Qt.AlignmentFlag.AlignVCenter)
        hdr_lay.addWidget(self._chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        hdr_lay.addWidget(self._count, alignment=Qt.AlignmentFlag.AlignVCenter)
        hdr_lay.addWidget(self._hint, stretch=1)

        self._divider = QFrame()
        self._divider.setObjectName("groupDivider")
        self._divider.setFixedHeight(1)

        self._body = QWidget()
        self._body.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(4, 4, 4, 4)
        self._body_lay.setSpacing(2)

        root.addWidget(self._header)
        root.addWidget(self._divider)
        root.addWidget(self._body)

        self.set_open(open)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_lay

    def set_header(self, *, title: str, hint: str, count: int) -> None:
        self._chip.configure(text=title, tone=_GROUP_TONE[self._src])  # type: ignore[arg-type]
        self._count.setText(str(count))
        self._hint.setText(hint)

    def set_open(self, open: bool) -> None:
        self._open = open
        chev_name = "chevron-down" if open else "chevron-right"
        pix = icon_pixmap(chev_name, 14, color=T.FAINT)
        if not pix.isNull():
            self._chev.setPixmap(pix)
        self._body.setVisible(open)
        self._divider.setVisible(open)

    def is_open(self) -> bool:
        return self._open

    def _toggle(self) -> None:
        self.set_open(not self._open)
        self.toggled.emit()
