"""PySide6 control panel — segmented tabs like design mock."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..elevation import is_admin
from ..presets import preset_pack_version
from .i18n import I18n
from .svg_icons import icon_button
from .icons import make_tray_icon
from .title_bar import PanelTitleBar
from .panel_about import AboutTab
from .panel_logs import LogsTab
from .panel_presets import PresetsTab
from .panel_status import StatusTab
from .scroll import style_scroll_area
from .widgets import (
    InfoLine,
    ModeRow,
    PresetBar,
    ReadOnlyField,
    Section,
    SocksField,
    SquareCheckbox,
    StatusChip,
    StatusPill,
)
from .tun_overlay import ModesTunHost
from . import theme as T
from . import typography as TY
from .win32_foreground import bring_window_to_foreground

if TYPE_CHECKING:
    from ..app import TrayApp


class ControlPanel(QWidget):
    _TAB_KEYS = ("modes", "presets", "status", "logs", "about")
    _zapret_check_finished = Signal()

    def __init__(self, app: TrayApp) -> None:
        super().__init__(
            None,
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint,
        )
        self.app = app
        self.i18n = I18n(app.config.locale)
        self._zapret_check_finished.connect(self._on_zapret_check_finished)

        self.setFixedSize(T.WINDOW_W, T.WINDOW_H)
        self.setObjectName("panelRoot")
        self._apply_window_icon()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title_bar = PanelTitleBar(self, app, self.i18n)
        self._title_bar.minimize_clicked.connect(self.showMinimized)
        self._title_bar.close_clicked.connect(self.hide)
        root.addWidget(self._title_bar)

        body = QWidget()
        body.setObjectName("panelBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        tab_outer = QWidget()
        tab_outer.setObjectName("tabOuter")
        tab_outer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tab_outer_lay = QHBoxLayout(tab_outer)
        tab_outer_lay.setContentsMargins(12, 8, 12, 8)
        tab_outer_lay.setSpacing(0)

        self._tab_strip = QFrame()
        self._tab_strip.setObjectName("tabStrip")
        strip_lay = QHBoxLayout(self._tab_strip)
        strip_lay.setContentsMargins(4, 4, 4, 4)
        strip_lay.setSpacing(2)

        self._stack = QStackedWidget()
        self._stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_modes = QWidget()
        self._tab_presets = PresetsTab(app, self.i18n)
        self._tab_status = StatusTab(app, self.i18n)
        self._tab_logs = LogsTab(app, self.i18n)
        self._tab_about = AboutTab(app, self.i18n)
        self._tab_buttons: list[QPushButton] = []

        self._stack.addWidget(self._tab_modes)
        self._stack.addWidget(self._tab_presets)
        self._stack.addWidget(self._tab_status)
        self._stack.addWidget(self._tab_logs)
        self._stack.addWidget(self._tab_about)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        tab_labels = (
            self.i18n.t("tab.modes"),
            self.i18n.t("tab.presets"),
            self.i18n.t("tab.status"),
            self.i18n.t("tab.logs"),
            self.i18n.t("tab.about"),
        )
        for i, label in enumerate(tab_labels):
            btn = QPushButton(label)
            btn.setProperty("tabButton", True)
            btn.setCheckable(True)
            self._tab_group.addButton(btn, i)
            self._tab_buttons.append(btn)
            strip_lay.addWidget(btn, stretch=1)
        self._tab_group.button(0).setChecked(True)
        self._tab_group.idClicked.connect(self._on_tab_changed)

        tab_outer_lay.addWidget(self._tab_strip)
        body_lay.addWidget(tab_outer)
        body_lay.addWidget(self._stack, stretch=1)
        root.addWidget(body, stretch=1)

        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(T.FOOTER_H)
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(16, 6, 16, 6)
        self._footer_label = QLabel()
        self._footer_label.setProperty("role", "faint")
        footer_row.addWidget(self._footer_label, stretch=1)
        self._footer_logs_btn = QPushButton()
        self._footer_logs_btn.setObjectName("footerLink")
        self._footer_logs_btn.setFlat(True)
        self._footer_logs_btn.clicked.connect(app.open_logs)
        footer_row.addWidget(self._footer_logs_btn)
        root.addWidget(footer)

        self._build_modes_tab()

        self._poll = QTimer(self)
        self._poll.setInterval(3000)
        self._poll.timeout.connect(self.refresh_light)
        self._poll.start()

        self.refresh(full=True)

    def _on_tab_changed(self, index: int) -> None:
        self.setUpdatesEnabled(False)
        try:
            self._stack.setCurrentIndex(index)
        finally:
            self.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda: self._deferred_tab_refresh(index))

    def _deferred_tab_refresh(self, index: int) -> None:
        if index == 1:
            self._tab_presets.refresh_light()
        elif index == 2:
            self._tab_status.refresh()
        elif index == 3:
            self._tab_logs.refresh()

    def _build_modes_tab(self) -> None:
        outer = QVBoxLayout(self._tab_modes)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        style_scroll_area(scroll)
        content = QWidget()
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        outer.addWidget(scroll)

        sec_modes = Section(self.i18n.t("sec.modes"))
        self._sec_modes = sec_modes

        # Strategy: Hybrid (TCP+Stream) vs Full (TCP+UDP DLL)
        strat_row = QHBoxLayout()
        strat_row.setSpacing(6)
        self._strategy_group = QButtonGroup(self)
        self._btn_hybrid = QPushButton(self.i18n.t("strategy.hybrid"))
        self._btn_hybrid.setProperty("filter", True)
        self._btn_hybrid.setCheckable(True)
        self._btn_full = QPushButton(self.i18n.t("strategy.full"))
        self._btn_full.setProperty("filter", True)
        self._btn_full.setCheckable(True)
        self._strategy_group.addButton(self._btn_hybrid, 0)
        self._strategy_group.addButton(self._btn_full, 1)
        if self.app.config.is_full_proxy:
            self._btn_full.setChecked(True)
        else:
            self._btn_hybrid.setChecked(True)
        self._strategy_group.idClicked.connect(self._on_strategy_id)
        strat_row.addWidget(self._btn_hybrid)
        strat_row.addWidget(self._btn_full)
        strat_row.addStretch(1)
        sec_modes.body.addLayout(strat_row)

        tcp_label = (
            self.i18n.t("tray.tcpUdp")
            if self.app.config.is_full_proxy
            else self.i18n.t("tray.tcp")
        )
        self._row_tcp = ModeRow(
            tcp_label,
            subtitle=f"· {self.i18n.t('modes.tcpSub')}",
            tone="tcp",
            checked=self.app.config.tcp_proxy,
        )
        self._row_tcp.toggled.connect(self._on_tcp_toggle)
        self._row_stream = ModeRow(
            self.i18n.t("tray.stream"),
            subtitle=f"· {self.i18n.t('modes.streamSub')}",
            tone="warn",
            checked=self.app.stream_toggle_display(),
        )
        self._row_stream.toggled.connect(self._on_stream_toggle)
        sec_modes.body.addWidget(self._row_tcp)
        sec_modes.body.addWidget(self._row_stream)

        self._stream_admin_hint = InfoLine(self.i18n.t("admin.streamNeedAdmin"))
        self._stream_admin_hint.setVisible(not is_admin())
        sec_modes.body.addWidget(self._stream_admin_hint)

        self._preset_bar = PresetBar()
        sec_modes.body.addWidget(self._preset_bar)

        self._modes_host = ModesTunHost(sec_modes)
        self._modes_host.set_tun_copy(
            self.i18n.t("tun.overlayTitle"),
            self.i18n.t("tun.overlaySub"),
        )
        self._modes_host.set_dll_copy(
            self.i18n.t("dll.overlayTitle"),
            self.i18n.t("dll.overlaySub"),
            self.i18n.t("dll.overlayInstall"),
        )
        self._modes_host.install_clicked.connect(self._on_dll_install)
        lay.addWidget(self._modes_host)

        sec_conn = Section(self.i18n.t("sec.connection"))
        socks_row = QHBoxLayout()
        socks_row.setSpacing(8)
        self._socks_host = SocksField()
        self._socks_host.setFixedWidth(136)
        self._socks_port = SocksField()
        self._socks_port.setFixedWidth(68)
        self._socks_host.editingFinished.connect(self._apply_socks)
        self._socks_port.editingFinished.connect(self._apply_socks)
        from PySide6.QtGui import QFont

        colon = QLabel(":")
        colon.setFont(TY.mono_md_font())
        colon.setStyleSheet(f"color: {T.FAINT}; background: transparent; border: none;")
        self._socks_pill = StatusPill()
        socks_row.addWidget(self._socks_host)
        socks_row.addWidget(colon)
        socks_row.addWidget(self._socks_port)
        socks_row.addStretch(1)
        socks_row.addWidget(self._socks_pill)
        sec_conn.body.addLayout(socks_row)
        sec_conn.body.addWidget(InfoLine(self.i18n.t("conn.tunNote")))
        lay.addWidget(sec_conn)

        sec_disc = Section(self.i18n.t("sec.discord"))
        self._sec_discord = sec_disc
        disc_row = QHBoxLayout()
        disc_row.setSpacing(8)
        self._discord_path = ReadOnlyField("—")
        self._dll_chip = StatusChip()
        disc_row.addWidget(self._discord_path, stretch=1)
        disc_row.addWidget(self._dll_chip)
        sec_disc.body.addLayout(disc_row)
        self._discord_restart_hint = InfoLine(self.i18n.t("discord.restart"))
        sec_disc.body.addWidget(self._discord_restart_hint)
        lay.addWidget(sec_disc)

        sec_zapret = Section(self.i18n.t("sec.zapret"))
        self._sec_zapret = sec_zapret
        zap_path_row = QHBoxLayout()
        zap_path_row.setSpacing(8)
        self._zapret_path = ReadOnlyField("—")
        zap_path_row.addWidget(self._zapret_path, stretch=1)
        sec_zapret.body.addLayout(zap_path_row)
        zap_meta = QHBoxLayout()
        zap_meta.setSpacing(8)
        self._zapret_ver = StatusChip()
        self._zapret_ver.configure(text="—", tone="idle")
        self._zapret_check_btn = QPushButton(self.i18n.t("zapret.check"))
        self._zapret_check_btn.setProperty("toolbarBtn", True)
        self._zapret_check_btn.clicked.connect(self._on_zapret_check)
        icon_button(self._zapret_check_btn, "refresh-cw", 12, color=T.MUTED)
        zap_meta.addWidget(self._zapret_ver)
        zap_meta.addStretch(1)
        zap_meta.addWidget(self._zapret_check_btn)
        sec_zapret.body.addLayout(zap_meta)
        lay.addWidget(sec_zapret)

        sec_startup = Section(self.i18n.t("sec.startup"), last=True)
        self._sec_startup = sec_startup
        start_col = QVBoxLayout()
        start_col.setSpacing(6)
        start_row = QHBoxLayout()
        start_row.setSpacing(10)
        self._autostart_cb = SquareCheckbox(checked=self.app.config.autostart)
        self._autostart_cb.toggled.connect(self._on_autostart_toggle)
        self._autostart_lbl = QLabel(self.i18n.t("tray.autostart"))
        self._autostart_lbl.setFont(TY.label_font())
        self._autostart_lbl.setProperty("role", "label")
        self._autostart_lbl.setStyleSheet(
            f"color: {T.TEXT}; background: transparent; border: none;"
        )
        start_row.addWidget(self._autostart_cb)
        start_row.addWidget(self._autostart_lbl)
        start_row.addStretch(1)
        start_col.addLayout(start_row)
        self._autostart_admin_hint = InfoLine(self.i18n.t("admin.autostartNeedAdmin"))
        self._autostart_admin_hint.setVisible(not is_admin())
        start_col.addWidget(self._autostart_admin_hint)
        sec_startup.body.addLayout(start_col)
        lay.addWidget(sec_startup)
        lay.addStretch(1)

    def _window_title(self) -> str:
        base = self.i18n.t("panel.titleBase")
        admin = self.i18n.t("panel.asAdmin" if is_admin() else "panel.notAsAdmin")
        return f"{base} — {admin}"

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _ensure_on_screen(self) -> None:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self._center_on_screen()
            return
        if not screen.availableGeometry().intersects(self.frameGeometry()):
            self._center_on_screen()

    def show_panel(self) -> None:
        self.setWindowTitle(self._window_title())
        self._title_bar.refresh()
        if not self.isVisible():
            self._center_on_screen()
        else:
            self._ensure_on_screen()
        was_top = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if not was_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if sys.platform == "win32":
            try:
                bring_window_to_foreground(int(self.winId()))
            except (OSError, AttributeError, ValueError):
                pass
        if not was_top:
            def _drop_topmost() -> None:
                if self.isVisible():
                    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
                    self.show()

            QTimer.singleShot(150, _drop_topmost)
        # Refresh TUN overlay immediately when opening the panel
        try:
            self.app.poll_tun_state(force_toast=False)
        except Exception:
            pass
        QTimer.singleShot(0, lambda: self.refresh(full=True))

    def _apply_window_icon(self) -> None:
        """Prefer app.ico (taskbar); fall back to tray mark."""
        qapp = QApplication.instance()
        if qapp is not None:
            icon = qapp.windowIcon()
            if icon is not None and not icon.isNull():
                self.setWindowIcon(icon)
                return
        self.setWindowIcon(
            make_tray_icon(
                self.app.config.tcp_proxy, self.app.stream_toggle_display()
            )
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def refresh_light(self) -> None:
        if not self.isVisible():
            return
        self.setWindowTitle(self._window_title())
        self._title_bar.refresh()
        self._apply_window_icon()
        self._sync_switches()
        self._refresh_modes_labels()
        idx = self._stack.currentIndex()
        if idx == 1:
            self._tab_presets.refresh_light()
        elif idx == 2:
            self._tab_status.refresh(full=False)
        elif idx == 3:
            pass  # logs: refresh on tab open only (reading tray.log every 3s freezes UI)
        pack = preset_pack_version()
        self._footer_label.setText(
            f"v{__version__} · {self.i18n.t('footer.pack')} {pack}"
        )

    def refresh(self, *, full: bool = False) -> None:
        self.setWindowTitle(self._window_title())
        self._title_bar.refresh()
        self._apply_window_icon()
        self._footer_logs_btn.setText(self.i18n.t("footer.openLogs"))
        icon_button(self._footer_logs_btn, "folder-open", 12, color=T.MUTED)
        self._refresh_tab_labels()
        self._sync_switches()
        self._refresh_modes_labels()
        if full:
            self._tab_presets.refresh(force_rebuild=True)
            self._tab_status.apply_locale()
            self._tab_logs.apply_locale()
            self._tab_about.apply_locale()
            self._tab_status.refresh()
            self._tab_logs.refresh()
            self._tab_about.refresh()
        pack = preset_pack_version()
        self._footer_label.setText(
            f"v{__version__} · {self.i18n.t('footer.pack')} {pack}"
        )

    def _refresh_tab_labels(self) -> None:
        keys = (
            "tab.modes",
            "tab.presets",
            "tab.status",
            "tab.logs",
            "tab.about",
        )
        for i, key in enumerate(keys):
            btn = self._tab_buttons[i]
            btn.setText(self.i18n.t(key))

    def _sync_switches(self) -> None:
        self._row_tcp.block_switch_signals(True)
        self._row_stream.block_switch_signals(True)
        self._autostart_cb.blockSignals(True)
        self._btn_hybrid.blockSignals(True)
        self._btn_full.blockSignals(True)

        self._row_tcp.setChecked(self.app.config.tcp_proxy)
        self._row_stream.setChecked(self.app.stream_toggle_display())
        self._autostart_cb.setChecked(self.app.config.autostart)
        admin_ok = is_admin()
        self._autostart_cb.setEnabled(admin_ok)
        full = self.app.config.is_full_proxy
        self._btn_full.setChecked(full)
        self._btn_hybrid.setChecked(not full)
        # Stream only in hybrid; still needs admin for winws.
        self._row_stream.set_switch_enabled(not full)
        self._row_stream.setVisible(not full)
        self._preset_bar.setVisible(not full)

        self._row_tcp.block_switch_signals(False)
        self._row_stream.block_switch_signals(False)
        self._autostart_cb.blockSignals(False)
        self._btn_hybrid.blockSignals(False)
        self._btn_full.blockSignals(False)

        # Never overwrite SOCKS fields while the user is editing them.
        if not self._socks_editing():
            host = self.app.config.socks_host
            port = str(self.app.config.socks_port)
            if self._socks_host.text() != host:
                self._socks_host.setText(host)
            if self._socks_port.text() != port:
                self._socks_port.setText(port)

    def _socks_editing(self) -> bool:
        return self._socks_host.hasFocus() or self._socks_port.hasFocus()

    def _refresh_modes_labels(self) -> None:
        report = self.app.readiness_cached()
        socks_ok = (
            report.socks_ok if report is not None else self.app.socks_ok_cached()
        )
        if socks_ok:
            self.app.alerts.clear_code("socks_down")

        full = self.app.config.is_full_proxy
        self._btn_hybrid.setText(self.i18n.t("strategy.hybrid"))
        self._btn_full.setText(self.i18n.t("strategy.full"))

        if full:
            self._stream_admin_hint.hide()
        elif is_admin():
            self._stream_admin_hint.hide()
        else:
            self._stream_admin_hint.show()

        self._stream_admin_hint.setText(self.i18n.t("admin.streamNeedAdmin"))
        self._autostart_admin_hint.setText(self.i18n.t("admin.autostartNeedAdmin"))
        self._row_tcp.set_label(
            self.i18n.t("tray.tcpUdp") if full else self.i18n.t("tray.tcp")
        )
        tcp_sub = (
            self.i18n.t("strategy.fullSub")
            if full
            else self.i18n.t("modes.tcpSub")
        )
        self._row_tcp.set_subtitle(f"· {tcp_sub}")
        self._row_stream.set_subtitle(f"· {self.i18n.t('modes.streamSub')}")
        self._autostart_admin_hint.setVisible(not is_admin())

        if self.app.tun_blocks_ui():
            self._preset_bar.set_content(
                self.i18n.t("modes.streamChip"),
                self.i18n.t("preset.notSelected"),
                "",
            )
        elif full:
            self._preset_bar.set_content(
                self.i18n.t("strategy.full"),
                self.i18n.t("preset.notSelected"),
                "",
            )
        else:
            self._preset_bar.set_content(
                self.i18n.t("modes.streamChip"),
                self.app.config.preset,
                self.i18n.t("modes.presetsTab"),
            )

        if socks_ok:
            self._socks_pill.configure(
                text=self.i18n.t("conn.socksOk"), tone="ok"
            )
        else:
            self._socks_pill.configure(
                text=self.i18n.t("conn.socksBad"), tone="warn"
            )

        discord = self.app._discord_dir()
        self._discord_path.setText(str(discord) if discord else "—")

        scan = self.app.dll_scan_cached()
        if discord:
            if scan is None:
                self._dll_chip.configure(
                    text=self.i18n.t("discord.dllMissing"), tone="warn"
                )
            elif scan.ours_ok:
                self._dll_chip.configure(
                    text=self.i18n.t("discord.dllOk"), tone="ok"
                )
            elif scan.drover:
                self._dll_chip.configure(
                    text=self.i18n.t("discord.dllDrover"), tone="warn"
                )
            elif scan.foreign_force_proxy:
                self._dll_chip.configure(
                    text=self.i18n.t("discord.dllForeign"), tone="warn"
                )
            else:
                self._dll_chip.configure(
                    text=self.i18n.t("discord.dllMissing"), tone="warn"
                )
            self._dll_chip.show()
        else:
            self._dll_chip.hide()

        from ..paths import zapret_dir

        zroot = zapret_dir()
        self._zapret_path.setText(str(zroot))
        ver = self.app.updater.local_display()
        zapret_ok = report.zapret_ok if report is not None else True
        if ver and ver != "-":
            self._zapret_ver.configure(text=ver, tone="ok" if zapret_ok else "warn")
        else:
            self._zapret_ver.configure(
                text=self.i18n.t("zapret.none"),
                tone="bad" if not zapret_ok else "idle",
            )
        self._zapret_check_btn.setText(self.i18n.t("zapret.check"))
        self._discord_restart_hint.setText(self.i18n.t("discord.restart"))
        if hasattr(self, "_sec_discord"):
            self._sec_discord.set_title(self.i18n.t("sec.discord"))
            self._sec_zapret.set_title(self.i18n.t("sec.zapret"))
            self._sec_startup.set_title(self.i18n.t("sec.startup"))
            self._autostart_lbl.setText(self.i18n.t("tray.autostart"))
        if hasattr(self, "_sec_modes"):
            self._sec_modes.set_title(self.i18n.t("sec.modes"))
        if hasattr(self, "_modes_host"):
            self._modes_host.set_tun_copy(
                self.i18n.t("tun.overlayTitle"),
                self.i18n.t("tun.overlaySub"),
            )
            if scan is None:
                dll_title = self.i18n.t("dll.overlayTitle")
                dll_sub = self.i18n.t("dll.overlaySub")
            elif scan.drover:
                dll_title = self.i18n.t("dll.overlayDroverTitle")
                dll_sub = self.i18n.t("dll.overlayDroverSub")
            elif scan.foreign_force_proxy:
                dll_title = self.i18n.t("dll.overlayForeignTitle")
                dll_sub = self.i18n.t("dll.overlayForeignSub")
            else:
                dll_title = self.i18n.t("dll.overlayTitle")
                dll_sub = self.i18n.t("dll.overlaySub")
            self._modes_host.set_dll_copy(
                dll_title,
                dll_sub,
                self.i18n.t("dll.overlayInstall"),
            )
            if self.app.tun_blocks_ui():
                self._modes_host.set_overlay("tun")
            elif self.app.needs_dll_install():
                self._modes_host.set_overlay("dll")
            else:
                self._modes_host.set_overlay("none")

    def _on_dll_install(self) -> None:
        if self.app.tun_blocks_ui():
            return
        self._modes_host.set_install_busy(True)
        try:
            self.app.bootstrap_dll_install()
        finally:
            self._modes_host.set_install_busy(False)
            self._sync_switches()
            self._refresh_modes_labels()

    def _on_zapret_check(self) -> None:
        if not self._zapret_check_btn.isEnabled():
            return
        self._zapret_check_btn.setEnabled(False)
        self._zapret_check_btn.setText(self.i18n.t("zapret.checking"))
        icon_button(self._zapret_check_btn, "loader-2", 12, color=T.MUTED)

        def _run() -> None:
            try:
                self.app.check_updates()
            finally:
                self._zapret_check_finished.emit()

        import threading

        threading.Thread(target=_run, name="zapret-check-ui", daemon=True).start()

    def _on_zapret_check_finished(self) -> None:
        self._zapret_check_btn.setEnabled(True)
        self._zapret_check_btn.setText(self.i18n.t("zapret.check"))
        icon_button(self._zapret_check_btn, "refresh-cw", 12, color=T.MUTED)
        self._refresh_modes_labels()
        self._tab_status.refresh()

    def _on_strategy_id(self, sid: int) -> None:
        if self.app.tun_blocks_ui() or self.app.needs_dll_install():
            self._sync_switches()
            return
        strategy = "full_proxy" if sid == 1 else "hybrid"
        if strategy == self.app.config.proxy_strategy:
            return

        from ..discord_control import discord_is_running

        need_restart = discord_is_running()
        if need_restart:
            reply = QMessageBox.question(
                self,
                self.i18n.t("strategy.restartTitle"),
                self.i18n.t("strategy.restartBody"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._sync_switches()
                return

        if not self.app.set_proxy_strategy(
            strategy, restart_discord_client=need_restart
        ):
            self._sync_switches()
            return
        self._sync_switches()
        self._refresh_modes_labels()

    def _on_tcp_toggle(self, checked: bool) -> None:
        if self.app.tun_blocks_ui() and not checked:
            # Allow visual sync only; cannot change while TUN up
            self._sync_switches()
            return
        if self.app.tun_blocks_ui() or self.app.needs_dll_install():
            self._sync_switches()
            return
        if checked == self.app.config.tcp_proxy:
            return
        if checked:
            self.app.enable_tcp_proxy()
        else:
            self.app.disable_tcp_proxy()
        self._sync_switches()

    def _on_stream_toggle(self, checked: bool) -> None:
        if self.app.tun_blocks_ui() or self.app.needs_dll_install():
            self._sync_switches()
            return
        if getattr(self.app, "_elevation_dialog_active", False):
            return
        if checked == self.app.stream_toggle_display():
            return
        if checked:
            if not self.app.enable_stream_desync():
                self._sync_switches()
        else:
            self.app.disable_stream_desync()
            self._sync_switches()

    def _on_autostart_toggle(self, checked: bool) -> None:
        if not is_admin():
            self._sync_switches()
            return
        if checked == self.app.config.autostart:
            return
        self.app.toggle_autostart()
        self._sync_switches()

    def _apply_socks(self) -> None:
        host = self._socks_host.text().strip()
        port = self._socks_port.text().strip()
        if (
            host == self.app.config.socks_host
            and port == str(self.app.config.socks_port)
        ):
            return
        # Save on blur / Enter. Invalid values: toast only — do not reset the field.
        if not self.app.update_socks(host, port):
            return
        self._refresh_modes_labels()
