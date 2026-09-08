"""Status tab — summary card, actions, raw dump (Fig D)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..alerts import Severity
from ..diagnostics import build_status
from .i18n import I18n
from .svg_icons import icon_button, icon_pixmap
from . import theme as T
from . import typography as TY

if TYPE_CHECKING:
    from ..app import TrayApp

_PAD = 20
_PT = 14


class _StatusRow(QFrame):
    def __init__(self, label: str, *, last: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        border = "" if last else f"border-bottom: 1px solid {T.LINE_SOFT};"
        self.setStyleSheet(f"QFrame {{ background: transparent; {border} }}")
        self.setMinimumHeight(30)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)
        lbl = QLabel(label.upper())
        lbl.setFixedWidth(64)
        lbl.setFont(TY.mono_sm_font())
        lbl.setStyleSheet(
            f"color: {T.FAINT}; background: transparent; border: none; "
            f"letter-spacing: 1px;"
        )
        self._label = lbl
        self._value = QHBoxLayout()
        self._value.setSpacing(4)
        self._value.setContentsMargins(0, 0, 0, 0)
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(self._value)
        row.addStretch(1)

    def set_label(self, text: str) -> None:
        self._label.setText(text.upper())

    def clear_values(self) -> None:
        while self._value.count():
            item = self._value.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_sep(self) -> None:
        sep = QLabel("·")
        sep.setFont(TY.ui_sm_font())
        sep.setStyleSheet(f"color: {T.FAINT}; background: transparent; border: none;")
        self._value.addWidget(sep)

    def _tone_color(self, tone: str) -> str:
        return {
            "tcp": T.TCP,
            "stream": T.STREAM,
            "text": T.TEXT,
            "muted": T.MUTED,
            "faint": T.FAINT,
            "ok": T.OK,
            "warn": T.STREAM,
            "bad": T.DANGER,
            "off": T.FAINT,
        }.get(tone, T.TEXT)

    def add_part(
        self,
        text: str,
        *,
        tone: str = "text",
        mono: bool = False,
        semibold: bool = False,
    ) -> None:
        lbl = QLabel(text)
        if mono:
            lbl.setFont(TY.mono_md_font(weight=TY.SEMI_WEIGHT if semibold else QFont.Weight.Normal))
        elif semibold:
            lbl.setFont(TY.ui_sm_font(weight=TY.SEMI_WEIGHT))
        else:
            lbl.setFont(TY.ui_sm_font())
        lbl.setStyleSheet(
            f"color: {self._tone_color(tone)}; background: transparent; border: none;"
        )
        lbl.setWordWrap(False)
        self._value.addWidget(lbl)

    def set_parts(
        self,
        parts: list[tuple[str, str, bool, bool]],
    ) -> None:
        """Each part: (text, tone, mono, semibold). Inserts · between parts."""
        self.clear_values()
        for i, (text, tone, mono, semibold) in enumerate(parts):
            if i:
                self._add_sep()
            self.add_part(text, tone=tone, mono=mono, semibold=semibold)

    def set_alert(self, text: str) -> None:
        self.clear_values()
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        icon = QLabel()
        icon.setFixedSize(12, 12)
        pix = icon_pixmap("triangle-alert", 12, color=T.STREAM)
        if not pix.isNull():
            icon.setPixmap(pix)
        icon.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")
        msg = QLabel(text)
        msg.setFont(TY.ui_sm_font())
        msg.setStyleSheet(
            f"color: {T.STREAM}; background: transparent; border: none; "
            f"text-decoration: none; padding: 0; margin: 0;"
        )
        msg.setWordWrap(True)
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        wrap.setLayout(row)
        row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(msg, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._value.addWidget(wrap, alignment=Qt.AlignmentFlag.AlignVCenter)


class StatusTab(QWidget):
    def __init__(self, app: TrayApp, i18n: I18n) -> None:
        super().__init__()
        self.app = app
        self.i18n = i18n

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card_wrap = QWidget()
        card_lay = QVBoxLayout(card_wrap)
        card_lay.setContentsMargins(_PAD, _PT, _PAD, 0)
        card_lay.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("statusCard")
        card_inner = QVBoxLayout(self._card)
        card_inner.setContentsMargins(16, 8, 16, 8)
        card_inner.setSpacing(0)

        self._rows: dict[str, _StatusRow] = {}
        self._row_keys = ("tcp", "stream", "discord", "vendor", "zapret", "alerts")
        for i, key in enumerate(self._row_keys):
            label = self.i18n.t(f"status.{key}")
            row = _StatusRow(label, last=(i == len(self._row_keys) - 1))
            card_inner.addWidget(row)
            self._rows[key] = row

        card_lay.addWidget(self._card)
        root.addWidget(card_wrap)

        btn_wrap = QWidget()
        btn_lay = QHBoxLayout(btn_wrap)
        btn_lay.setContentsMargins(_PAD, 10, _PAD, 6)
        btn_lay.setSpacing(8)
        self._refresh_btn = QPushButton(self.i18n.t("status.refresh"))
        self._refresh_btn.setProperty("toolbarBtn", True)
        self._refresh_btn.clicked.connect(lambda: self.refresh(full=True))
        self._copy_btn = QPushButton(self.i18n.t("status.copy"))
        self._copy_btn.setProperty("toolbarBtn", True)
        self._copy_btn.clicked.connect(self._copy_status)
        self._folder_btn = QPushButton(self.i18n.t("status.openFolder"))
        self._folder_btn.setProperty("toolbarBtn", True)
        self._folder_btn.clicked.connect(self.app.open_logs)
        self._vendor_btn = QPushButton(self.i18n.t("status.openVendor"))
        self._vendor_btn.setProperty("toolbarBtn", True)
        self._vendor_btn.clicked.connect(self.app.open_vendor_folder)
        self._zapret_btn = QPushButton(self.i18n.t("status.openZapret"))
        self._zapret_btn.setProperty("toolbarBtn", True)
        self._zapret_btn.clicked.connect(self.app.open_zapret_folder)
        self._ack_btn = QPushButton(self.i18n.t("status.ack"))
        self._ack_btn.setProperty("toolbarBtn", True)
        self._ack_btn.clicked.connect(self._ack_critical)
        self._ack_btn.hide()
        btn_lay.addWidget(self._refresh_btn)
        btn_lay.addWidget(self._copy_btn)
        btn_lay.addWidget(self._folder_btn)
        btn_lay.addWidget(self._vendor_btn)
        btn_lay.addWidget(self._zapret_btn)
        btn_lay.addWidget(self._ack_btn)
        btn_lay.addStretch(1)
        root.addWidget(btn_wrap)

        raw_wrap = QWidget()
        raw_lay = QVBoxLayout(raw_wrap)
        raw_lay.setContentsMargins(_PAD, 0, _PAD, 8)
        raw_lay.setSpacing(2)
        self._raw_label = QLabel(self.i18n.t("status.dump").upper())
        self._raw_label.setProperty("role", "section")
        self._raw_label.setFont(TY.section_font())
        self._raw_label.setContentsMargins(0, 0, 0, 0)
        self._raw_label.setStyleSheet(
            f"color: {T.FAINT}; letter-spacing: {TY.SECTION_TRACKING}; "
            f"background: transparent; border: none; padding: 0; margin: 0;"
        )
        self._time = QLabel()
        self._time.setFont(TY.mono_sm_font())
        self._time.setProperty("role", "faint")
        self._time.setStyleSheet(
            f"color: {T.FAINT}; background: transparent; border: none; "
            f"padding: 0; margin: 0;"
        )
        self._raw = QPlainTextEdit()
        self._raw.setObjectName("rawStatus")
        self._raw.setReadOnly(True)
        self._raw.setMaximumBlockCount(500)
        self._raw.setMinimumHeight(118)
        self._raw.setFont(TY.mono_sm_font())
        raw_lay.addWidget(self._raw_label)
        raw_lay.addWidget(self._time)
        raw_lay.addWidget(self._raw, stretch=1)
        root.addWidget(raw_wrap, stretch=1)

        self._style_buttons()

    def apply_locale(self) -> None:
        for key in self._row_keys:
            self._rows[key].set_label(self.i18n.t(f"status.{key}"))
        self._refresh_btn.setText(self.i18n.t("status.refresh"))
        self._copy_btn.setText(self.i18n.t("status.copy"))
        self._folder_btn.setText(self.i18n.t("status.openFolder"))
        self._vendor_btn.setText(self.i18n.t("status.openVendor"))
        self._zapret_btn.setText(self.i18n.t("status.openZapret"))
        self._ack_btn.setText(self.i18n.t("status.ack"))
        self._raw_label.setText(self.i18n.t("status.dump").upper())
        self._style_buttons()

    def _style_buttons(self) -> None:
        icon_button(self._refresh_btn, "refresh-cw", 12, color=T.MUTED)
        icon_button(self._copy_btn, "copy", 12, color=T.MUTED)
        icon_button(self._folder_btn, "folder-open", 12, color=T.MUTED)
        icon_button(self._vendor_btn, "folder-open", 12, color=T.MUTED)
        icon_button(self._zapret_btn, "folder-open", 12, color=T.MUTED)
        icon_button(self._ack_btn, "check", 12, color=T.MUTED)

    def _ack_critical(self) -> None:
        self.app.ack_critical_alert()
        self.refresh(full=True)

    def refresh(self, *, full: bool = True) -> None:
        """full=True rebuilds the raw dump (heavy). Timer polls use full=False."""
        from ..readiness import ReadinessReport

        if full:
            self._refresh_btn.setEnabled(False)
            icon_button(self._refresh_btn, "loader-2", 12, color=T.MUTED)

        cfg = self.app.config
        report = self.app.readiness_cached()
        socks_ok = (
            report.socks_ok if report is not None else self.app.socks_ok_cached()
        )
        if socks_ok:
            self.app.alerts.clear_code("socks_down")

        if report is None:
            self.app.kick_live_probes()
            disc0 = self.app._discord_dir()
            report = ReadinessReport(
                vendor_ok=True,
                vendor_missing=(),
                zapret_ok=True,
                zapret_missing=(),
                discord_dir=disc0,
                discord_ok=disc0 is not None,
                dll_ok=False,
                socks_ok=socks_ok,
                preset_remote_offline=False,
                preset_first_run=False,
                preset_local_version=None,
                presets_sync_offline=self.app._presets_sync_offline,
            )

        if full:
            text = build_status(
                cfg,
                self.app.zapret,
                socks_ok,
                watcher=self.app.watcher,
                alerts=self.app.alerts,
            )

            # Preserve raw dump scroll position across refresh.
            raw_bar = self._raw.verticalScrollBar()
            raw_pos = raw_bar.value()
            at_bottom = raw_pos >= raw_bar.maximum() - 3
            self._raw.setPlainText(text)
            if at_bottom:
                raw_bar.setValue(raw_bar.maximum())
            else:
                raw_bar.setValue(min(raw_pos, raw_bar.maximum()))

        on = self.i18n.t("status.on")
        off = self.i18n.t("status.off")

        if cfg.tcp_proxy:
            parts: list[tuple[str, str, bool, bool]] = [(on, "tcp", False, True)]
            if cfg.is_full_proxy:
                parts.append((self.i18n.t("strategy.full"), "text", False, False))
            parts.append((
                self.i18n.t("status.socksOkShort" if socks_ok else "status.socksBadShort"),
                "text" if socks_ok else "warn",
                False,
                False,
            ))
            parts.append((
                self.i18n.t("status.dllOkShort" if report.dll_ok else "status.dllBadShort"),
                "text" if report.dll_ok else "warn",
                False,
                False,
            ))
            self._rows["tcp"].set_parts(parts)
        else:
            self._rows["tcp"].set_parts([(off, "off", False, True)])

        stream_on = self.app.stream_toggle_display()
        if cfg.is_full_proxy:
            self._rows["stream"].set_parts([
                (self.i18n.t("strategy.full"), "muted", False, False),
                (self.i18n.t("status.off"), "off", False, True),
            ])
        elif stream_on and self.app.zapret.is_running():
            self._rows["stream"].set_parts([
                (on, "stream", False, True),
                (self.i18n.t("status.winwsRunning"), "text", False, False),
                (cfg.preset, "muted", True, False),
            ])
        elif stream_on:
            self._rows["stream"].set_parts([
                (on, "stream", False, True),
                (self.i18n.t("status.winwsStopped"), "warn", False, False),
            ])
        else:
            self._rows["stream"].set_parts([(off, "off", False, True)])

        disc = self.app._discord_dir()
        if disc is not None:
            scan = self.app.dll_scan_cached()
            patched = bool(scan and scan.ours_ok)
            parts_d: list[tuple[str, str, bool, bool]] = [
                (disc.name, "text", True, False),
                (
                    self.i18n.t("status.patched" if patched else "status.notPatched"),
                    "text" if patched else "warn",
                    False,
                    False,
                ),
            ]
            # Module enum is expensive — only on explicit / full refresh.
            if full:
                try:
                    from ..discord_modules import discord_module_status

                    ms = discord_module_status()
                    if ms.discord_running and ms.force_proxy_loaded is True:
                        parts_d.append(
                            (self.i18n.t("status.dllLoaded"), "ok", False, False)
                        )
                    elif ms.discord_running and ms.force_proxy_loaded is False:
                        parts_d.append(
                            (self.i18n.t("status.dllNotLoaded"), "warn", False, False)
                        )
                except Exception:
                    pass
            self._rows["discord"].set_parts(parts_d)
        else:
            self._rows["discord"].set_parts([("—", "faint", True, False)])

        from ..vendor_check import format_missing_names

        if report.vendor_ok:
            self._rows["vendor"].set_parts([
                (self.i18n.t("status.depsOk"), "ok", False, True),
            ])
        else:
            miss = format_missing_names(report.vendor_missing) or self.i18n.t(
                "status.depsMissing"
            )
            self._rows["vendor"].set_parts([
                (self.i18n.t("status.depsMissing"), "bad", False, True),
                (miss, "warn", True, False),
            ])

        if report.zapret_ok:
            zap_parts: list[tuple[str, str, bool, bool]] = [
                (self.i18n.t("status.depsOk"), "ok", False, True),
            ]
            zver = self.app.updater.local_display()
            if zver and zver != "-":
                zap_parts.append((zver, "muted", True, False))
            self._rows["zapret"].set_parts(zap_parts)
        else:
            miss_z = format_missing_names(report.zapret_missing) or self.i18n.t(
                "status.depsMissing"
            )
            self._rows["zapret"].set_parts([
                (self.i18n.t("status.depsMissing"), "bad", False, True),
                (miss_z, "warn", True, False),
            ])

        alert = self.app.alerts.latest(Severity.CRITICAL) or self.app.alerts.latest(
            Severity.WARN
        )
        pending = self.app.alerts.pending_critical()
        self._ack_btn.setVisible(pending is not None)
        if alert:
            ts = datetime.fromtimestamp(alert.ts).strftime("%H:%M")
            level = "CRIT" if alert.severity == Severity.CRITICAL else "WARN"
            self._rows["alerts"].set_alert(f"{ts} {level} {alert.message}")
        else:
            self._rows["alerts"].set_parts([
                (self.i18n.t("status.none"), "faint", False, False)
            ])

        self._time.setText(
            f"{self.i18n.t('status.refreshed')} {datetime.now().strftime('%H:%M:%S')}"
        )
        if full:
            QTimer.singleShot(280, self._finish_refresh_feedback)

    def _finish_refresh_feedback(self) -> None:
        self._refresh_btn.setEnabled(True)
        icon_button(self._refresh_btn, "refresh-cw", 12, color=T.MUTED)

    def _copy_status(self) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(self._raw.toPlainText())
        self._copy_btn.setText(self.i18n.t("status.copied"))
        icon_button(self._copy_btn, "check", 12, color=T.OK)
        QTimer.singleShot(1200, self._reset_copy_btn)

    def _reset_copy_btn(self) -> None:
        self._copy_btn.setText(self.i18n.t("status.copy"))
        icon_button(self._copy_btn, "copy", 12, color=T.MUTED)
