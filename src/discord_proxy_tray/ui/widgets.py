"""Design-system widgets matching the React mock (Switch, Section, Chip, …)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme as T
from .fonts import mono_font, ui_font
from . import typography as TY


def _font(size: float, *, mono: bool = False, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    if mono:
        return mono_font(size, weight=weight)
    return ui_font(size, weight=weight)


class ColorDot(QWidget):
    """7×7 status dot before mode labels."""

    _COLORS = {
        "tcp": T.TCP,
        "warn": T.STREAM,
        "ok": T.OK,
        "idle": T.FAINT,
        "accent": T.ACCENT,
    }

    def __init__(self, tone: Tone = "idle", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tone = tone
        self.setFixedSize(10, 10)

    def set_tone(self, tone: Tone) -> None:
        self._tone = tone
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        color = QColor(self._COLORS.get(self._tone, T.FAINT))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(1, 1, 8, 8)


class ToggleSwitch(QWidget):
    """36×20 switch with white knob — chrome.tsx Switch."""

    toggled = Signal(bool)

    def __init__(self, *, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self.update()

    def blockSignals(self, block: bool) -> bool:  # noqa: N802
        return super().blockSignals(block)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.isEnabled():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        if self._checked:
            track = QColor(T.ACCENT)
        else:
            track = QColor(T.FAINT)
            track.setAlphaF(0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, 0, 36, 20, 10, 10)
        knob_x = 19 if self._checked else 3
        p.setBrush(Qt.GlobalColor.white)
        p.drawEllipse(knob_x, 3, 14, 14)


class SquareCheckbox(QWidget):
    """16×16 checkbox with check mark."""

    toggled = Signal(bool)

    def __init__(self, *, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self.update()

    def blockSignals(self, block: bool) -> bool:  # noqa: N802
        return super().blockSignals(block)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ForbiddenCursor
        )
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.isEnabled():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        if self._checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.ACCENT))
            p.drawRoundedRect(0, 0, 16, 16, 4, 4)
            pen = QPen(QColor(T.ACCENT_INK))
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.drawLine(4, 8, 7, 11)
            p.drawLine(7, 11, 12, 5)
        else:
            p.setPen(QPen(QColor(T.FAINT)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(1, 1, 14, 14, 4, 4)


def make_section_header(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setProperty("role", "section")
    lbl.setFont(TY.section_font())
    lbl.setStyleSheet(
        f"color: {T.FAINT}; letter-spacing: {TY.SECTION_TRACKING}; "
        f"background: transparent; border: none;"
    )
    return lbl


class ReadOnlyField(QLineEdit):
    """Read-only entry box (Discord path)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setFont(TY.mono_lg_font())
        self.setFixedHeight(28)
        self.setStyleSheet(
            f"QLineEdit {{ background: {T.SURFACE_2}; border: 1px solid {T.LINE}; "
            f"border-radius: 6px; padding: 0 8px; color: {T.TEXT}; }}"
        )


class SocksField(QLineEdit):
    """Editable SOCKS host/port field."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFont(TY.mono_md_font())
        self.setFixedHeight(28)
        self.setStyleSheet(
            f"QLineEdit {{ background: {T.SURFACE_2}; border: 1px solid {T.LINE}; "
            f"border-radius: 6px; padding: 0 8px; color: {T.TEXT}; }}"
            f"QLineEdit:focus {{ border-color: rgba(76, 194, 168, 0.7); }}"
        )


class StatusPill(QFrame):
    """Rounded SOCKS status — right-aligned; wide enough for RU strings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 12, 4)
        lay.setSpacing(6)
        self._dot = ColorDot("ok", self)
        self._text = QLabel()
        self._text.setFont(TY.ui_sm_font())
        self._text.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        lay.addWidget(self._dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._text, alignment=Qt.AlignmentFlag.AlignVCenter)

    def configure(self, *, text: str, tone: Tone) -> None:
        self._text.setText(text)
        self._dot.set_tone(tone)
        border, color = {
            "ok": ("rgba(67, 182, 117, 0.5)", T.OK),
            "warn": ("rgba(220, 176, 80, 0.5)", T.STREAM),
            "bad": ("rgba(232, 93, 93, 0.5)", T.DANGER),
            "idle": (T.FAINT, T.MUTED),
        }.get(tone, (T.LINE, T.MUTED))
        self.setStyleSheet(
            f"QFrame {{ background: transparent; border: 1px solid {border}; "
            f"border-radius: 12px; }}"
            f"QLabel {{ color: {color}; background: transparent; border: none; "
            f"padding: 0; margin: 0; }}"
        )
        fm = self._text.fontMetrics()
        min_w = fm.horizontalAdvance(text) + 10 + 12 + 6 + 8
        self.setMinimumWidth(min_w)
        self.setFixedHeight(max(24, fm.height() + 10))


class StatusChip(QFrame):
    """Border chip with dot (DLL ok / missing)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 8, 2)
        lay.setSpacing(6)
        self._dot = ColorDot("ok", self)
        self._text = QLabel()
        self._text.setFont(TY.ui_sm_font())
        lay.addWidget(self._dot)
        lay.addWidget(self._text)
        self.setFixedHeight(24)

    def set_label_font(self, font: QFont) -> None:
        self._text.setFont(font)

    def configure(self, *, text: str, tone: Tone) -> None:
        self._text.setText(text)
        self._dot.set_tone(tone)
        border, color = {
            "ok": (T.OK, T.OK),
            "warn": (T.STREAM, T.STREAM),
            "bad": (T.DANGER, T.DANGER),
            "idle": (T.FAINT, T.MUTED),
            "tcp": (T.TCP, T.TCP),
            "accent": (T.ACCENT, T.ACCENT),
        }.get(tone, (T.FAINT, T.MUTED))
        self.setStyleSheet(
            f"QFrame {{ background: transparent; border: 1px solid {border}; "
            f"border-radius: 5px; }}"
            f"QLabel {{ color: {color}; background: transparent; border: none; }}"
        )


class InfoLine(QWidget):
    """Info SVG + muted hint (Lucide info, no underline)."""

    def __init__(
        self,
        text: str,
        *,
        wrap: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        from .svg_icons import icon_pixmap

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._icon = QLabel()
        self._icon.setObjectName("infoIcon")
        self._icon.setFixedSize(11, 11)
        pix = icon_pixmap("info", 11, color=T.FAINT)
        if not pix.isNull():
            self._icon.setPixmap(pix)
            self._icon.setScaledContents(False)
        else:
            self._icon.setText("i")
            self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._icon.setFont(_font(9, weight=QFont.Weight.DemiBold))
        self._icon.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")
        self._text = QLabel(text)
        self._text.setWordWrap(wrap)
        if not wrap:
            self._text.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
            )
        self._text.setFont(TY.body_font())
        self._text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._text.setStyleSheet(
            f"color: {T.MUTED}; background: transparent; border: none; "
            f"text-decoration: none; padding: 0; margin: 0;"
        )
        row.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._text, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def setText(self, text: str) -> None:  # noqa: N802
        self._text.setText(text)


class Section(QFrame):
    """Labeled block with optional bottom divider."""

    def __init__(
        self,
        title: str,
        *,
        last: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        border = "" if last else f"border-bottom: 1px solid {T.LINE_SOFT};"
        self.setStyleSheet(f"QFrame {{ background: transparent; {border} }}")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 14, 20, 14)
        self._root.setSpacing(8)
        hdr = QLabel(title.upper())
        hdr.setProperty("role", "section")
        hdr.setFont(TY.section_font())
        hdr.setStyleSheet(
            f"color: {T.FAINT}; letter-spacing: {TY.SECTION_TRACKING}; "
            f"background: transparent; border: none;"
        )
        self._hdr = hdr
        self._root.addWidget(hdr)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self._root.addLayout(self.body)

    def set_title(self, title: str) -> None:
        self._hdr.setText(title.upper())

    def set_body_bleed(self, horizontal: int) -> None:
        """Widen body content into section padding (mock: -mx-1 … -mx-2)."""
        m = self.body.contentsMargins()
        self.body.setContentsMargins(-horizontal, m.top(), -horizontal, m.bottom())


class ModeRow(QWidget):
    """Colored dot + label + subtitle (left), switch (right)."""

    toggled = Signal(bool)

    def __init__(
        self,
        label: str,
        *,
        subtitle: str = "",
        tone: Tone = "tcp",
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self._tone = tone
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._dot = ColorDot(tone if checked else "idle", self)
        self._label = QLabel(label)
        self._label.setFont(TY.setting_font())
        self._label.setProperty("role", "setting")
        self._label.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none; "
            f"text-decoration: none; padding: 0; margin: 0;"
        )
        self._subtitle = QLabel(subtitle)
        self._subtitle.setFont(TY.body_font())
        self._subtitle.setProperty("role", "muted")
        self._subtitle.setStyleSheet(
            f"color: {T.MUTED}; background: transparent; border: none; "
            f"text-decoration: none; padding: 0; margin: 0;"
        )
        self._switch = ToggleSwitch(checked=checked, parent=self)
        self._switch.toggled.connect(self._on_switch)
        self._switch.toggled.connect(self.toggled.emit)
        left = QHBoxLayout()
        left.setSpacing(6)
        left.addWidget(self._dot)
        left.addWidget(self._label)
        if subtitle:
            left.addWidget(self._subtitle)
        row.addLayout(left)
        row.addStretch(1)
        row.addWidget(self._switch)

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)
        self._subtitle.setVisible(bool(text))

    def _on_switch(self, checked: bool) -> None:
        self._dot.set_tone(self._tone if checked else "idle")

    def isChecked(self) -> bool:
        return self._switch.isChecked()

    def setChecked(self, checked: bool) -> None:
        self._switch.blockSignals(True)
        self._switch.setChecked(checked)
        self._switch.blockSignals(False)
        self._dot.set_tone(self._tone if checked else "idle")

    def block_switch_signals(self, block: bool) -> None:
        self._switch.blockSignals(block)

    def set_switch_enabled(self, enabled: bool) -> None:
        self._switch.setEnabled(enabled)


class PresetBar(QFrame):
    """Stream preset bar — muted label · name · tab hint (right)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        # surface-2 @ 60% — mock: bg-[var(--surface-2)]/60
        self.setStyleSheet(
            f"QFrame {{ background: rgba(34, 38, 47, 0.6); "
            f"border: 1px solid {T.LINE}; border-radius: 6px; }}"
            f"QFrame QLabel {{ background: transparent; border: none; "
            f"border-radius: 0; padding: 0; margin: 0; text-decoration: none; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)
        self._prefix = QLabel()
        self._prefix.setFont(TY.body_font())
        self._prefix.setProperty("role", "muted")
        self._prefix.setStyleSheet(f"color: {T.MUTED}; background: transparent; border: none;")
        sep = QLabel("·")
        sep.setStyleSheet(f"color: {T.FAINT}; background: transparent; border: none;")
        self._name = QLabel()
        self._name.setFont(TY.mono_md_font())
        self._name.setStyleSheet(f"color: {T.TEXT}; background: transparent; border: none;")
        self._link = QLabel()
        self._link.setFont(TY.faint_sm_font(mono=True))
        self._link.setProperty("role", "faint-sm")
        self._link.setStyleSheet(
            f"color: {T.FAINT}; background: transparent; border: none; "
            f"border-radius: 0; padding: 0; margin: 0; text-decoration: none;"
        )
        row.addWidget(self._prefix)
        row.addWidget(sep)
        row.addWidget(self._name, stretch=1)
        row.addWidget(self._link)

    def set_content(self, prefix: str, preset: str, link: str) -> None:
        self._prefix.setText(prefix)
        self._name.setText(preset)
        self._link.setText(link)
