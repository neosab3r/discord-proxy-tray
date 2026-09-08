"""Logs tab — filter chips + colored tail (Fig E)."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..paths import runtime_dir
from .i18n import I18n
from .svg_icons import icon_button
from . import theme as T
from . import typography as TY

if TYPE_CHECKING:
    from ..app import TrayApp

_PAD = 20
_PT = 14
_TAIL_LINES = 60
_BOTTOM_EPS = 3

_LOG_RE = re.compile(
    r"^(?:(\d{4}-\d{2}-\d{2}\s+)?(\d{2}:\d{2}:\d{2})(?:,\d+)?\s+)?"
    r"(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|CRIT)\s+(.+)$"
)


def _level_style(level: str) -> str:
    up = level.upper()
    if up in ("WARNING", "WARN"):
        return T.STREAM
    if up in ("ERROR", "CRITICAL", "CRIT"):
        return T.DANGER
    return T.FAINT


def _parse_line(line: str) -> tuple[str, str, str] | None:
    m = _LOG_RE.match(line.strip())
    if not m:
        return None
    ts = m.group(2) or ""
    level = m.group(3).upper()
    if level == "WARN":
        level = "WARNING"
    msg = m.group(4).strip()
    return ts, level, msg


class LogsTab(QWidget):
    def __init__(self, app: TrayApp, i18n: I18n) -> None:
        super().__init__()
        self.app = app
        self.i18n = i18n
        self._follow_tail = True
        self._programmatic_scroll = False
        # After Clear: only show log lines with index >= cutoff (file not truncated).
        self._line_cutoff: int | None = None
        self._cleared_marker = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(_PAD, _PT, _PAD, 0)
        bar.setSpacing(6)

        self._filter_group = QButtonGroup(self)
        self._filter_all = QPushButton(self.i18n.t("logs.all"))
        self._filter_all.setProperty("filter", True)
        self._filter_all.setCheckable(True)
        self._filter_all.setChecked(True)
        self._filter_alerts = QPushButton(self.i18n.t("logs.alerts"))
        self._filter_alerts.setProperty("filter", True)
        self._filter_alerts.setCheckable(True)
        self._filter_group.addButton(self._filter_all, 0)
        self._filter_group.addButton(self._filter_alerts, 1)
        self._filter_group.idClicked.connect(lambda _: self.refresh())

        self._line_count = QLabel()
        self._line_count.setFont(TY.mono_sm_font())
        self._line_count.setProperty("role", "faint")

        self._open_btn = QPushButton(self.i18n.t("logs.openFolder"))
        self._open_btn.setProperty("toolbarBtn", True)
        self._open_btn.clicked.connect(self.app.open_logs)

        self._clear_btn = QPushButton(self.i18n.t("logs.clear"))
        self._clear_btn.setProperty("toolbarBtn", True)
        self._clear_btn.clicked.connect(self.clear_view)

        bar.addWidget(self._filter_all)
        bar.addWidget(self._filter_alerts)
        bar.addWidget(self._line_count)
        bar.addStretch(1)
        bar.addWidget(self._clear_btn)
        bar.addWidget(self._open_btn)
        root.addWidget(toolbar)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(_PAD, 10, _PAD, 12)
        body_lay.setSpacing(0)
        self._view = QTextEdit()
        self._view.setObjectName("logView")
        self._view.setReadOnly(True)
        self._view.setFont(TY.mono_sm_font())
        self._view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_lay.addWidget(self._view, stretch=1)
        root.addWidget(body, stretch=1)

        sb = self._view.verticalScrollBar()
        sb.valueChanged.connect(self._on_scroll_changed)
        sb.sliderPressed.connect(self._on_scroll_grabbed)
        sb.sliderReleased.connect(self._on_scroll_released)

    def _on_scroll_grabbed(self) -> None:
        self._follow_tail = False

    def _on_scroll_released(self) -> None:
        sb = self._view.verticalScrollBar()
        if sb.value() >= sb.maximum() - _BOTTOM_EPS:
            self._follow_tail = True

    def _on_scroll_changed(self, value: int) -> None:
        if self._programmatic_scroll:
            return
        sb = self._view.verticalScrollBar()
        at_bottom = value >= sb.maximum() - _BOTTOM_EPS
        if sb.isSliderDown() or not at_bottom:
            self._follow_tail = False
        else:
            self._follow_tail = True

    def _scroll_to_bottom(self) -> None:
        sb = self._view.verticalScrollBar()
        self._programmatic_scroll = True
        sb.setValue(sb.maximum())
        self._programmatic_scroll = False

    def apply_locale(self) -> None:
        self._filter_all.setText(self.i18n.t("logs.all"))
        self._filter_alerts.setText(self.i18n.t("logs.alerts"))
        self._clear_btn.setText(self.i18n.t("logs.clear"))
        self._open_btn.setText(self.i18n.t("logs.openFolder"))
        icon_button(self._clear_btn, "trash-2", 12, color=T.MUTED)
        icon_button(self._open_btn, "folder-open", 12, color=T.MUTED)

    def clear_view(self) -> None:
        """Clear the on-screen log view (does not delete tray.log)."""
        log_path = runtime_dir() / "logs" / "tray.log"
        cutoff = 0
        if log_path.is_file():
            try:
                cutoff = len(
                    log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                )
            except OSError:
                cutoff = 0
        self._line_cutoff = cutoff
        self._cleared_marker = True
        self._follow_tail = True
        self._show_cleared_marker()
        self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")

    def _show_cleared_marker(self) -> None:
        mono = TY.mono_sm_font().family()
        marker = html.escape(self.i18n.t("logs.cleared"))
        self._view.setHtml(
            f'<body style="background:{T.INSET};color:{T.MUTED};margin:0;">'
            f'<div style="font-family:{mono};font-size:10.5px;'
            f'line-height:1.75;margin:0;padding:0;">'
            f'<span style="color:{T.FAINT};">{marker}</span>'
            f"</div></body>"
        )

    def refresh(self) -> None:
        log_path = runtime_dir() / "logs" / "tray.log"
        if not log_path.is_file():
            if self._cleared_marker:
                self._show_cleared_marker()
                self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")
            else:
                self._view.setPlainText("(no tray.log yet)")
                self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")
            return
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            self._view.setPlainText("(could not read tray.log)")
            self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")
            return

        if self._line_cutoff is not None:
            lines = lines[self._line_cutoff :]

        if not lines:
            self._show_cleared_marker()
            self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")
            return

        self._cleared_marker = False
        alerts_only = self._filter_group.checkedId() == 1

        # Alerts filter: prefer in-memory AlertBus (structured), then log WARN/ERROR.
        bus_rows: list[tuple[str, str, str]] = []
        if alerts_only:
            from datetime import datetime

            from ..alerts import Severity

            for a in reversed(self.app.alerts.items):
                if a.severity == Severity.INFO:
                    continue
                ts = datetime.fromtimestamp(a.ts).strftime("%H:%M:%S")
                lvl = "CRIT" if a.severity == Severity.CRITICAL else "WARN"
                bus_rows.append((ts, lvl, f"[{a.code}] {a.message}"))

        tail = lines[-_TAIL_LINES:]
        parsed: list[tuple[str, str, str]] = list(bus_rows)
        for line in tail:
            item = _parse_line(line)
            if item is None:
                if not alerts_only:
                    parsed.append(("", "INFO", line.strip()))
                continue
            ts, level, msg = item
            if alerts_only and level in ("DEBUG", "INFO"):
                continue
            # Skip duplicate log lines that already mirror AlertBus (rough).
            if alerts_only and bus_rows and "[" in msg and "]" in msg:
                pass
            parsed.append((ts, level, msg))

        if not parsed and self._line_cutoff is not None:
            self._show_cleared_marker()
            self._line_count.setText(f"0 {self.i18n.t('logs.tail')}")
            return

        mono = TY.mono_sm_font().family()
        rows: list[str] = []
        if self._line_cutoff is not None:
            marker = html.escape(self.i18n.t("logs.cleared"))
            rows.append(
                f'<div style="font-family:{mono};font-size:10.5px;'
                f'line-height:1.75;margin:0;padding:0;">'
                f'<span style="color:{T.FAINT};">{marker}</span></div>'
            )
        for ts, level, msg in parsed:
            lvl_color = _level_style(level)
            tag = level if len(level) <= 5 else level[:4]
            ts_html = (
                f'<span style="color:{T.FAINT};opacity:0.7;">{html.escape(ts)}</span>'
                if ts
                else ""
            )
            rows.append(
                f'<div style="font-family:{mono};font-size:10.5px;'
                f'line-height:1.75;margin:0;padding:0;word-wrap:break-word;">'
                f'{ts_html}'
                f'{" " if ts_html else ""}'
                f'<span style="color:{lvl_color};font-weight:500;">'
                f'[{html.escape(tag)}]</span> '
                f'<span style="color:{T.MUTED};">{html.escape(msg)}</span>'
                f"</div>"
            )

        self._view.setHtml(
            f'<body style="background:{T.INSET};color:{T.MUTED};margin:0;">'
            + "".join(rows)
            + "</body>"
        )
        self._line_count.setText(f"{len(parsed)} {self.i18n.t('logs.tail')}")

        if self._follow_tail:
            self._scroll_to_bottom()

        if not hasattr(self, "_btns_styled"):
            icon_button(self._clear_btn, "trash-2", 12, color=T.MUTED)
            icon_button(self._open_btn, "folder-open", 12, color=T.MUTED)
            self._btns_styled = True
