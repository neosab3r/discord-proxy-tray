"""System tray UI: TCP proxy + stream desync toggles + diagnostics."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .alerts import AlertBus, Severity
from .autostart import (
    disable_autostart,
    enable_autostart,
    is_autostart_enabled,
)
from .config import AppConfig
from .diagnostics import build_status
from .discord_control import (
    discord_is_running,
    restart_discord,
    start_discord,
    stop_discord,
)
from .discord_watcher import DiscordFolderWatcher
from .elevation import elevation_error, is_admin, relaunch_as_admin
from .force_proxy_manager import (
    clean_all_discord_injects,
    clean_all_our_discord_dlls,
    dlls_present,
    install_force_proxy,
    latest_discord_dir,
    proxy_enabled_value,
    scan_discord_dlls,
    soft_disable_force_proxy,
    vendor_force_proxy_dir,
    write_proxy_txt,
)
from .logging_setup import setup_logging
from .paths import project_root, runtime_dir, zapret_dir
from .preset_updater import (
    PresetUpdater,
    mark_zapret_checked_today,
    zapret_checked_today,
)
from .presets import (
    delete_local_preset as remove_local_preset_file,
    list_preset_names,
    resolve_preset_path,
    save_preset_as_local,
)
from .remote_presets import (
    RemotePresetSync,
    mark_presets_checked_today,
    presets_checked_today,
)
from .readiness import build_readiness, vendor_folder, zapret_folder
from .ui.i18n import I18n
from .ui.icons import make_tray_icon
from .ui.styles import apply_application_theme
from .vendor_check import missing_force_proxy_vendor, missing_zapret_bin
from .zapret_manager import ZapretManager
from .single_instance import SHOW_PANEL, TAKEOVER, InstanceGuard

log = logging.getLogger(__name__)


def socks_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class TrayApp:
    def __init__(self) -> None:
        self.log_file = setup_logging()
        self.config = AppConfig.load()
        self.i18n = I18n(self.config.locale)
        self.alerts = AlertBus()
        # Prefer ALT12 (user-verified for streams)
        if self.config.preset in ("discord-udp-only", "flowseal-discord"):
            if resolve_preset_path("alt12") is not None:
                self.config.preset = "alt12"
                self.config.save()
        self.zapret = ZapretManager(zapret_dir())
        self.updater = PresetUpdater(zapret_dir())
        self.remote_presets = RemotePresetSync(self.config.presets_remote_base)
        self._app: QApplication | None = None
        self._tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._panel = None
        self._presets_sync_offline = False
        self._elevation_dialog_active = False
        self._instance: InstanceGuard | None = None
        self._shutting_down = False
        self._lock = threading.Lock()
        self._tun_lock = threading.RLock()
        self._tun_idle_toasted = False
        self._tun_ui_latched = False
        self._tun_poll_busy = False
        # Background live probes (SOCKS / TUN / DLL / readiness) — never on UI thread.
        self._live_lock = threading.Lock()
        self._live_probe_busy = False
        self._live_socks_ok = False
        self._live_tun: list[str] = []
        self._live_dll_scan = None
        self._live_readiness = None
        self.watcher = DiscordFolderWatcher(
            should_maintain=lambda: (
                self.config.tcp_proxy
                and not self.config.tun_paused
                and not self.tun_present_cached()
            ),
            socks=lambda: (self.config.socks_host, self.config.socks_port),
            proxy_enabled=lambda: (
                self.config.tcp_proxy
                and not self.config.tun_paused
                and not self.tun_present_cached()
            ),
            vendor_dir=lambda: vendor_force_proxy_dir(project_root()),
            strategy=lambda: (
                "full_proxy" if self.config.is_full_proxy else "hybrid"
            ),
            interval_sec=float(self.config.watch_interval_sec),
            on_notify=lambda title, msg: self.alerts.emit(
                Severity.WARN, "watcher", msg, toast=True
            ),
            on_latest_changed=self._on_discord_latest_changed,
            on_fresh_dll_install=self._restart_discord_after_fresh_dlls,
        )
        # Prefer real Task Scheduler state over stale config
        try:
            self.config.autostart = is_autostart_enabled()
            self.config.save()
        except OSError:
            pass
        # Keep start_tray.cmd pointed at *this* build (release vs project).
        if self.config.autostart:
            try:
                from .autostart import write_launcher

                write_launcher()
            except OSError:
                log.exception("failed to refresh autostart launcher")
        log.info(
            "app init; frozen=%s root=%s log=%s",
            getattr(sys, "frozen", False),
            project_root(),
            self.log_file,
        )
        threading.Thread(target=self._startup_preflight, name="preflight", daemon=True).start()

    def readiness(self):
        return build_readiness(
            socks_ok=socks_reachable(self.config.socks_host, self.config.socks_port),
            presets_remote_base=self.config.presets_remote_base,
            discord_dir=self._discord_dir(),
            presets_sync_offline=self._presets_sync_offline,
            strategy=self.config.proxy_strategy,
        )

    def socks_ok_cached(self) -> bool:
        with self._live_lock:
            return self._live_socks_ok

    def tun_present_cached(self) -> list[str]:
        with self._live_lock:
            return list(self._live_tun)

    def dll_scan_cached(self):
        with self._live_lock:
            return self._live_dll_scan

    def readiness_cached(self):
        with self._live_lock:
            return self._live_readiness

    def kick_live_probes(self) -> None:
        """Refresh SOCKS/TUN/DLL/readiness off the UI thread."""
        if self._live_probe_busy:
            return
        self._live_probe_busy = True
        host = self.config.socks_host
        port = self.config.socks_port
        discord_dir = self._discord_dir()
        presets_remote_base = self.config.presets_remote_base
        presets_sync_offline = self._presets_sync_offline
        strategy = self.config.proxy_strategy

        def work() -> None:
            try:
                from .force_proxy_manager import vendor_force_proxy_dir
                from .paths import project_root
                from .tun_check import suspect_tun_adapters

                ok = socks_reachable(host, port, timeout=0.5)
                tuns = suspect_tun_adapters()
                scan = scan_discord_dlls(
                    discord_dir,
                    vendor_force_proxy_dir(project_root()),
                )
                report = build_readiness(
                    socks_ok=ok,
                    presets_remote_base=presets_remote_base,
                    discord_dir=discord_dir,
                    presets_sync_offline=presets_sync_offline,
                    strategy=strategy,
                    dll_scan=scan,
                )
                with self._live_lock:
                    self._live_socks_ok = ok
                    self._live_tun = list(tuns)
                    self._live_dll_scan = scan
                    self._live_readiness = report
                if ok:
                    # Clear on main thread — AlertBus may touch UI.
                    QTimer.singleShot(0, lambda: self.alerts.clear_code("socks_down"))
            except Exception:
                log.exception("live probes failed")
            finally:
                self._live_probe_busy = False

        threading.Thread(target=work, name="live-probes", daemon=True).start()

    def _startup_preflight(self) -> None:
        report = self.readiness()
        from .vendor_check import format_missing_names

        if not report.zapret_ok and self.config.stream_desync:
            names = format_missing_names(report.zapret_missing)
            msg = self.i18n.t("state.zapretMissing")
            if names:
                msg = f"{msg}: {names}"
            self.alerts.emit(Severity.CRITICAL, "zapret_missing", msg, toast=True)
        if not report.vendor_ok and self.config.tcp_proxy:
            names = format_missing_names(report.vendor_missing)
            msg = self.i18n.t("state.vendorMissing")
            if names:
                msg = f"{msg}: {names}"
            self.alerts.emit(Severity.CRITICAL, "vendor_missing", msg, toast=True)
        if not report.discord_ok and self.config.tcp_proxy:
            self.alerts.emit(
                Severity.WARN,
                "discord_folder",
                self.i18n.t("state.discordMissing"),
            )
        if self.config.tcp_proxy and not report.socks_ok:
            self.alerts.emit(
                Severity.WARN,
                "socks_down",
                self.i18n.t("state.socksDown"),
            )
        # TUN: if modes were desired, emergency-pause (snapshot). Overlay also
        # appears later from live tun_blocks_ui() even when modes are off.
        try:
            tuns = self.tun_present()
            if tuns and (self.config.tcp_proxy or self.config.stream_desync):
                self.tun_emergency_pause(tuns, toast=False, refresh_ui=False)
        except Exception:
            log.exception("tun preflight failed")
        self._refresh_icon()

    def tun_present(self) -> list[str]:
        from .tun_check import suspect_tun_adapters

        return suspect_tun_adapters()

    def tun_blocks_ui(self) -> bool:
        """Show Modes overlay / lock Presets when TUN is up or we hold a pause snapshot."""
        try:
            if self.tun_present_cached():
                return True
        except Exception:
            pass
        return bool(self.config.tun_paused)

    def needs_dll_install(self) -> bool:
        """Discord folder needs Install: missing our DLLs or third-party hooks."""
        scan = self.dll_scan_cached()
        if scan is None:
            return False
        return scan.needs_setup

    def scan_discord_dlls(self):
        from .paths import project_root

        return scan_discord_dlls(
            self._discord_dir(),
            vendor_force_proxy_dir(project_root()),
        )

    def _restart_discord_after_fresh_dlls(self) -> None:
        """If Discord is already running, new DLLs only load after a restart."""
        if not discord_is_running():
            return
        if restart_discord():
            self.alerts.emit(
                Severity.INFO,
                "dll_restart",
                self.i18n.t("dll.discordRestarted"),
                toast=True,
            )
        else:
            self.alerts.emit(
                Severity.WARN,
                "dll_restart",
                self.i18n.t("dll.discordRestartFailed"),
                toast=True,
            )

    def _tun_soft_stop_runtime(self) -> None:
        """Always kill live proxying — no config flag changes."""
        discord_dir = self._discord_dir()
        if discord_dir is not None:
            try:
                soft_disable_force_proxy(discord_dir)
            except OSError as e:
                log.warning("tun soft-stop: %s", e)
        if self.zapret.is_running():
            self.zapret.stop()

    def poll_tun_state(self, *, force_toast: bool = False) -> None:
        """
        Single entry for timer + panel open.
        Adapter scan runs off the UI thread; pause/resume applies on the main thread.
        """
        if self._tun_poll_busy:
            return
        self._tun_poll_busy = True

        def work() -> None:
            tuns: list[str] = []
            try:
                tuns = self.tun_present()
                with self._live_lock:
                    self._live_tun = list(tuns)
            except Exception:
                log.exception("tun poll scan failed")
            finally:
                def apply() -> None:
                    self._tun_poll_busy = False
                    self._apply_tun_poll(tuns, force_toast=force_toast)

                if self._app is not None:
                    QTimer.singleShot(0, apply)
                else:
                    apply()

        threading.Thread(target=work, name="tun-poll", daemon=True).start()

    def _apply_tun_poll(self, tuns: list[str], *, force_toast: bool = False) -> None:
        """Main-thread TUN emergency pause / resume after a background scan."""
        with self._tun_lock:
            if tuns:
                self._tun_soft_stop_runtime()
                modes_on = (
                    self.config.tcp_proxy
                    or self.config.stream_desync
                    or self.zapret.is_running()
                )
                if modes_on and not self.config.tun_paused:
                    self.tun_emergency_pause(
                        tuns, toast=True, refresh_ui=True, _locked=True
                    )
                    self._tun_ui_latched = True
                elif not self.config.tun_paused:
                    # Idle + TUN: overlay via live tun_blocks_ui()
                    need_ui = force_toast or not self._tun_ui_latched
                    if force_toast or not self._tun_idle_toasted:
                        self._tun_idle_toasted = True
                        self.alerts.emit(
                            Severity.WARN,
                            "tun_idle",
                            f"{self.i18n.t('tun.idleToast')}: {', '.join(tuns[:3])}",
                            toast=bool(self._tray),
                        )
                    if need_ui:
                        self._tun_ui_latched = True
                        self._refresh_icon()
                        self._refresh_panel(full=True)
                else:
                    self._tun_ui_latched = True
                return

            self._tun_idle_toasted = False
            if self.config.tun_paused:
                self.tun_resume(toast=True, _locked=True)
                self._tun_ui_latched = False
            elif self._tun_ui_latched:
                self._tun_ui_latched = False
                self.alerts.clear_code("tun_idle")
                self._refresh_icon()
                self._refresh_panel()

    def tun_emergency_pause(
        self,
        tuns: list[str] | None = None,
        *,
        toast: bool = True,
        refresh_ui: bool = True,
        _locked: bool = False,
    ) -> None:
        """PROXY_ENABLED=0 + stop winws; remember current strategy / modes / preset."""

        def _run() -> None:
            nonlocal tuns
            tuns = tuns if tuns is not None else self.tun_present()
            names = ", ".join((tuns or ["TUN"])[:3])
            first = not self.config.tun_paused
            if first:
                self.config.resume_tcp_proxy = self.config.tcp_proxy
                self.config.resume_stream_desync = self.config.stream_desync
                self.config.resume_proxy_strategy = self.config.proxy_strategy  # type: ignore[assignment]
                self.config.resume_preset = self.config.preset
            self.config.tun_paused = True
            self.config.save()
            self._tun_soft_stop_runtime()

            log.warning(
                "TUN emergency pause adapters=%s resume tcp=%s stream=%s strategy=%s preset=%s",
                names,
                self.config.resume_tcp_proxy,
                self.config.resume_stream_desync,
                self.config.resume_proxy_strategy,
                self.config.resume_preset,
            )
            if toast or first:
                self.alerts.emit(
                    Severity.CRITICAL,
                    "tun_pause",
                    f"{self.i18n.t('tun.pauseToast')}: {names}",
                    toast=bool(self._tray),
                )
            if refresh_ui:
                self._refresh_icon()
                self._refresh_panel(full=True)

        if _locked:
            _run()
        else:
            with self._tun_lock:
                _run()

    def tun_resume(self, *, toast: bool = True, _locked: bool = False) -> None:
        """Restore last strategy / modes after TUN is gone."""

        def _run() -> None:
            if not self.config.tun_paused:
                return
            if self.tun_present():
                return

            self.config.tun_paused = False
            self.config.tcp_proxy = self.config.resume_tcp_proxy
            self.config.stream_desync = (
                self.config.resume_stream_desync
                and self.config.resume_proxy_strategy != "full_proxy"
            )
            self.config.proxy_strategy = self.config.resume_proxy_strategy  # type: ignore[assignment]
            if self.config.resume_preset:
                self.config.preset = self.config.resume_preset
            self.config.save()
            self.alerts.clear_code("tun_pause")
            self.alerts.clear_code("tun_adapter")
            self.alerts.clear_code("tun_idle")

            log.info(
                "TUN resume tcp=%s stream=%s strategy=%s preset=%s",
                self.config.tcp_proxy,
                self.config.stream_desync,
                self.config.proxy_strategy,
                self.config.preset,
            )

            if self.config.tcp_proxy:
                try:
                    self.enable_tcp_proxy()
                except Exception:
                    log.exception("TUN resume: enable_tcp failed")
            if (
                self.config.stream_desync
                and self.config.is_hybrid
                and is_admin()
            ):
                try:
                    self.enable_stream_desync()
                except Exception:
                    log.exception("TUN resume: enable_stream failed")

            if toast:
                self.alerts.emit(
                    Severity.INFO,
                    "tun_resume",
                    self.i18n.t("tun.resumeToast"),
                    toast=True,
                )
            self._refresh_icon()
            self._refresh_panel(full=True)

        if _locked:
            _run()
        else:
            with self._tun_lock:
                _run()

    def _block_if_tun(self) -> bool:
        """
        Gate for manual mode enable. If TUN is up: do not flip desired flags,
        stop runtime, show overlay, return True (caller should abort).
        """
        with self._tun_lock:
            tuns = self.tun_present()
            if not tuns:
                if self.config.tun_paused:
                    self.tun_resume(toast=True, _locked=True)
                return False

            # Reject the toggle — leave tcp/stream flags unchanged
            self._tun_soft_stop_runtime()
            names = ", ".join(tuns[:3])
            self.alerts.emit(
                Severity.CRITICAL,
                "tun_block",
                f"{self.i18n.t('tun.blockEnable')}: {names}",
                toast=True,
            )
            self._refresh_icon()
            self._refresh_panel(full=True)
            return True

    def preset_path(self) -> Path:
        path = resolve_preset_path(self.config.preset)
        if path is None:
            raise FileNotFoundError(f"preset not found: {self.config.preset}")
        return path

    def _notify(self, title: str, message: str) -> None:
        if self._tray and self._tray.isVisible():
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def _on_discord_latest_changed(self, latest: Path) -> None:
        """Point config at new app-* after Discord update."""
        self.config.discord_path = str(latest)
        self.config.save()
        log.info("discord_path -> %s", latest)

    def _discord_dir(self) -> Path | None:
        latest = latest_discord_dir()
        if latest is not None:
            return latest
        if self.config.discord_path:
            p = Path(self.config.discord_path)
            return p if p.is_dir() else None
        return None

    def stream_toggle_display(self) -> bool:
        """Visual ON for tray/panel — off without admin / in full_proxy mode."""
        if self.config.is_full_proxy:
            return False
        if getattr(self, "_elevation_dialog_active", False):
            return True
        if not is_admin():
            return False
        return self.config.stream_desync

    def presets_usable(self) -> bool:
        """Presets apply only in hybrid mode while elevated and not TUN-blocked."""
        return (
            self.config.is_hybrid
            and is_admin()
            and not self.tun_blocks_ui()
        )

    def _refresh_icon(self) -> None:
        if not self._tray:
            return
        if self.tun_blocks_ui():
            self._tray.setIcon(make_tray_icon(False, False))
            admin = "Admin" if is_admin() else "not Admin"
            mode = "full" if self.config.is_full_proxy else "hybrid"
            base = f"Discord Proxy Tray ({admin}, {mode})"
            tip = f"{base} — TUN"
            crit = self.alerts.pending_critical()
            if crit:
                tip = f"{base} — {crit.message[:100]}"
            self._tray.setToolTip(tip)
            return
        stream_on = self.stream_toggle_display()
        self._tray.setIcon(make_tray_icon(self.config.tcp_proxy, stream_on))
        admin = "Admin" if is_admin() else "not Admin"
        mode = "full" if self.config.is_full_proxy else "hybrid"
        base = f"Discord Proxy Tray ({admin}, {mode})"
        if self.config.tcp_proxy and stream_on:
            tip = f"{base} — TCP+Stream"
        elif self.config.tcp_proxy:
            tip = f"{base} — TCP" + ("+UDP" if self.config.is_full_proxy else "")
        elif stream_on:
            tip = f"{base} — Stream"
        else:
            tip = f"{base} — Off"
        crit = self.alerts.pending_critical()
        if crit:
            tip = f"{base} — {crit.message[:100]}"
        self._tray.setToolTip(tip)

    def _save_and_refresh(self) -> None:
        self.config.save()
        self._refresh_icon()
        self.refresh_tray_menu()

    def shutdown_runtime(self) -> None:
        """Stop winws + soft-disable TCP without clearing desired config flags."""
        self.zapret.stop()
        discord_dir = self._discord_dir()
        if discord_dir is not None:
            soft_disable_force_proxy(discord_dir)
        self._refresh_icon()
        log.info(
            "runtime stopped (desired tcp=%s desync=%s)",
            self.config.tcp_proxy,
            self.config.stream_desync,
        )

    def _restore_on_startup(self) -> None:
        """Retry enabling saved modes for ~60s (Discord/SOCKS may start later)."""
        # If TUN is up, emergency-pause instead of restoring runtime.
        if self.tun_present():
            if self.config.tcp_proxy or self.config.stream_desync or self.config.tun_paused:
                self.tun_emergency_pause(toast=True)
            return
        if self.config.tun_paused:
            self.tun_resume(toast=True)
            return

        want_tcp = self.config.tcp_proxy
        want_desync = self.config.stream_desync and self.config.is_hybrid
        if not want_tcp and not want_desync:
            return
        tcp_ok = not want_tcp
        desync_ok = not want_desync
        for attempt in range(12):
            if want_tcp and not tcp_ok:
                with self._lock:
                    discord_dir = self._discord_dir()
                    if discord_dir is not None:
                        try:
                            had_dlls = dlls_present(discord_dir)
                            note = install_force_proxy(
                                discord_dir,
                                self.config.socks_host,
                                self.config.socks_port,
                                vendor_force_proxy_dir(project_root()),
                                enabled=True,
                                strategy=self.config.proxy_strategy,
                            )
                            if dlls_present(discord_dir):
                                tcp_ok = True
                                log.info("startup tcp ok: %s", note)
                                if not had_dlls:
                                    self._restart_discord_after_fresh_dlls()
                        except (PermissionError, FileNotFoundError) as e:
                            log.warning("startup tcp attempt %s: %s", attempt + 1, e)
            if want_desync and not desync_ok:
                if not is_admin():
                    if attempt == 0:
                        self.alerts.emit(
                            Severity.WARN,
                            "admin_required",
                            self.i18n.t("admin.streamNeedAdmin"),
                            toast=True,
                        )
                    desync_ok = True
                else:
                    with self._lock:
                        try:
                            self.zapret.start(self.preset_path())
                            time.sleep(0.8)
                            if self.zapret.is_running():
                                desync_ok = True
                                log.info("startup desync ok")
                        except FileNotFoundError as e:
                            log.warning("startup desync attempt %s: %s", attempt + 1, e)
                        except OSError as e:
                            if elevation_error(e):
                                log.warning("startup desync needs admin")
                                desync_ok = True
                            else:
                                log.warning("startup desync attempt %s: %s", attempt + 1, e)
            if tcp_ok and desync_ok:
                self._refresh_icon()
                self.alerts.emit(
                    Severity.INFO,
                    "restore_ok",
                    "Restored: "
                    + ", ".join(
                        p
                        for p, on in (
                            ("TCP", want_tcp),
                            ("Stream", want_desync and is_admin()),
                        )
                        if on
                    ),
                    toast=True,
                )
                return
            time.sleep(5)
        self.alerts.emit(
            Severity.WARN,
            "restore_incomplete",
            "Startup restore incomplete — check Status / start v2rayN / Admin",
        )

    def toggle_autostart(self) -> None:
        with self._lock:
            try:
                if is_autostart_enabled():
                    disable_autostart()
                    self.config.autostart = False
                    self.config.save()
                    self.alerts.emit(
                        Severity.INFO, "autostart_off", "Autostart OFF", toast=True
                    )
                else:
                    enable_autostart()
                    self.config.autostart = True
                    self.config.save()
                    self.alerts.emit(
                        Severity.INFO,
                        "autostart_on",
                        "Autostart ON (logon, admin). Keep TCP/Stream as desired.",
                        toast=True,
                    )
            except PermissionError as e:
                self.alerts.emit(Severity.WARN, "autostart_admin", str(e))
            except OSError as e:
                self.alerts.emit(Severity.WARN, "autostart_error", f"Autostart error: {e}")

    def enable_tcp_proxy(self) -> bool:
        """Install/update DLLs + PROXY_ENABLED=1. Returns True on success."""
        from .vendor_check import format_missing_names

        if self.config.tun_paused:
            return False
        if self._block_if_tun():
            return False
        # Fresh Discord folder: same path as Modes → Install (Full + restart).
        if self.needs_dll_install():
            return self._bootstrap_dll_install_locked()

        missing = missing_force_proxy_vendor(strategy=self.config.proxy_strategy)
        if missing:
            self.alerts.emit(
                Severity.CRITICAL,
                "vendor_missing",
                f"{self.i18n.t('state.vendorMissing')}: "
                f"{format_missing_names(missing)}",
            )
            return False

        discord_dir = self._discord_dir()
        if discord_dir is None:
            self.alerts.emit(
                Severity.CRITICAL,
                "discord_folder",
                self.i18n.t("state.discordMissing"),
            )
            return False

        socks_ok = socks_reachable(self.config.socks_host, self.config.socks_port)
        if not socks_ok:
            self.alerts.emit(
                Severity.WARN,
                "socks_down",
                f"SOCKS {self.config.socks_host}:{self.config.socks_port} down — start v2rayN",
            )

        vendor = vendor_force_proxy_dir(project_root())
        had_dlls = dlls_present(discord_dir)
        try:
            note = install_force_proxy(
                discord_dir,
                self.config.socks_host,
                self.config.socks_port,
                vendor,
                enabled=True,
                strategy=self.config.proxy_strategy,
            )
            log.info("force-proxy: %s (%s)", note, discord_dir)
        except (PermissionError, FileNotFoundError) as e:
            self.alerts.emit(Severity.CRITICAL, "tcp_install", str(e))
            return False

        if not dlls_present(discord_dir):
            self.alerts.emit(
                Severity.CRITICAL,
                "dlls_missing",
                f"DLLs not in Discord folder (vendor={vendor})",
            )
            return False

        self.config.tcp_proxy = True
        self.alerts.clear_code("vendor_missing")
        self._save_and_refresh()
        mode = "TCP+UDP" if self.config.is_full_proxy else "TCP"
        if not had_dlls:
            self._restart_discord_after_fresh_dlls()
            self.alerts.emit(
                Severity.INFO,
                "tcp_on",
                f"{mode} proxy ON",
                toast=True,
            )
        else:
            self.alerts.emit(
                Severity.INFO,
                "tcp_on",
                f"{mode} proxy ON",
                toast=True,
            )
        return True

    def bootstrap_dll_install(self) -> bool:
        """
        Fresh install: stop Discord, copy DLLs, enable Full + TCP, start Discord.
        Used by the Modes overlay Install button.
        """
        with self._lock:
            return self._bootstrap_dll_install_locked()

    def _bootstrap_dll_install_locked(self) -> bool:
        from .vendor_check import format_missing_names

        if self.tun_blocks_ui():
            self.alerts.emit(
                Severity.WARN,
                "tun_block",
                self.i18n.t("tun.blockStrategy"),
                toast=True,
            )
            return False

        missing = missing_force_proxy_vendor(strategy="full_proxy")
        if missing:
            self.alerts.emit(
                Severity.CRITICAL,
                "vendor_missing",
                f"{self.i18n.t('state.vendorMissing')}: "
                f"{format_missing_names(missing)}",
            )
            return False

        discord_dir = self._discord_dir()
        if discord_dir is None:
            self.alerts.emit(
                Severity.CRITICAL,
                "discord_folder",
                self.i18n.t("state.discordMissing"),
            )
            return False

        if self.zapret.is_running() or self.config.stream_desync:
            self.zapret.stop()
        self.config.stream_desync = False

        stop_discord()

        # Drop drover / original force-proxy / stale injects, then put ours.
        clean_notes = clean_all_discord_injects()
        if clean_notes:
            log.info("DLL bootstrap cleaned: %s", "; ".join(clean_notes))

        vendor = vendor_force_proxy_dir(project_root())
        try:
            note = install_force_proxy(
                discord_dir,
                self.config.socks_host,
                self.config.socks_port,
                vendor,
                enabled=True,
                strategy="full_proxy",
            )
            log.info("DLL bootstrap: %s (%s)", note, discord_dir)
        except (PermissionError, FileNotFoundError) as e:
            self.alerts.emit(
                Severity.CRITICAL,
                "dll_install",
                f"{self.i18n.t('dll.installFailed')}: {e}",
            )
            return False

        if not dlls_present(discord_dir):
            self.alerts.emit(
                Severity.CRITICAL,
                "dlls_missing",
                f"{self.i18n.t('dll.installFailed')} (vendor={vendor})",
            )
            return False

        self.config.proxy_strategy = "full_proxy"  # type: ignore[assignment]
        self.config.tcp_proxy = True
        self.alerts.clear_code("vendor_missing")
        self.alerts.clear_code("dlls_missing")
        self._save_and_refresh()

        if start_discord():
            self.alerts.emit(
                Severity.INFO,
                "dll_install",
                self.i18n.t("dll.installed"),
                toast=True,
            )
        else:
            self.alerts.emit(
                Severity.WARN,
                "dll_install",
                f"{self.i18n.t('dll.installed')}. "
                f"{self.i18n.t('strategy.discordRestartFailed')}",
                toast=True,
            )
        self._refresh_panel(full=True)
        return True

    def uninstall_all_dlls(self) -> bool:
        """
        About → Remove DLL: stop proxying, remove Discord inject files,
        stop winws (WinDivert), clear tray/winws/force-proxy logs.
        """
        from .logging_setup import winws_log_path
        from .paths import runtime_dir

        with self._lock:
            if self.zapret.is_running():
                self.zapret.stop()
            self.config.stream_desync = False
            self.config.tcp_proxy = False

            stop_discord()
            notes = clean_all_our_discord_dlls()

            log_dir = runtime_dir() / "logs"
            cleared_logs: list[str] = []
            for path in (
                log_dir / "tray.log",
                log_dir / "tray.log.1",
                log_dir / "tray.log.2",
                log_dir / "tray.log.3",
                winws_log_path(),
                log_dir / "last_status.txt",
                log_dir / "elevated_relaunch.log",
            ):
                if path.is_file():
                    try:
                        path.unlink()
                        cleared_logs.append(path.name)
                    except OSError as e:
                        log.warning("cannot clear log %s: %s", path, e)

            self._save_and_refresh()
            self._refresh_panel(full=True)

            detail = "; ".join(notes) if notes else "no Discord inject files"
            if cleared_logs:
                detail = f"{detail}; logs: {', '.join(cleared_logs)}"
            self.alerts.emit(
                Severity.INFO,
                "dll_uninstall",
                f"{self.i18n.t('about.dllRemoved')}: {detail}",
                toast=True,
            )
            log.info("uninstall_all_dlls: %s", detail)
            return True

    def disable_tcp_proxy(self) -> None:
        discord_dir = self._discord_dir()
        if discord_dir is not None:
            # Both local builds honor PROXY_ENABLED soft-off.
            soft_disable_force_proxy(discord_dir)
        was_full = self.config.is_full_proxy
        self.config.tcp_proxy = False
        self._save_and_refresh()
        msg = (
            "Full proxy OFF (PROXY_ENABLED=0)"
            if was_full
            else "TCP proxy OFF (PROXY_ENABLED=0)"
        )
        self.alerts.emit(Severity.INFO, "tcp_off", msg, toast=True)

    def set_proxy_strategy(
        self, strategy: str, *, restart_discord_client: bool = False
    ) -> bool:
        """Switch hybrid ↔ full_proxy. Reinstalls DLL if TCP is on; stops winws for full."""
        if strategy not in ("hybrid", "full_proxy"):
            return False
        if strategy == self.config.proxy_strategy:
            return True
        # TUN: keep old strategy; stop runtime if it was active
        if self.tun_present() or self.config.tun_paused:
            if (
                self.config.tcp_proxy
                or self.config.stream_desync
                or self.zapret.is_running()
            ):
                self.tun_emergency_pause(toast=True)
            else:
                self.alerts.emit(
                    Severity.WARN,
                    "tun_block",
                    self.i18n.t("tun.blockStrategy"),
                    toast=True,
                )
                self._refresh_panel()
            return False

        missing = missing_force_proxy_vendor(strategy=strategy)  # type: ignore[arg-type]
        if missing:
            from .vendor_check import format_missing_names

            self.alerts.emit(
                Severity.CRITICAL,
                "vendor_missing",
                f"{self.i18n.t('state.vendorMissing')}: "
                f"{format_missing_names(missing)}",
            )
            return False

        prev = self.config.proxy_strategy
        self.config.proxy_strategy = strategy  # type: ignore[assignment]

        if strategy == "full_proxy":
            if self.zapret.is_running() or self.config.stream_desync:
                self.zapret.stop()
            self.config.stream_desync = False

        if self.config.tcp_proxy:
            discord_dir = self._discord_dir()
            if discord_dir is None:
                self.config.proxy_strategy = prev  # type: ignore[assignment]
                self.alerts.emit(
                    Severity.CRITICAL, "discord_folder", "Discord folder not found"
                )
                return False
            try:
                had_dlls = dlls_present(discord_dir)
                note = install_force_proxy(
                    discord_dir,
                    self.config.socks_host,
                    self.config.socks_port,
                    vendor_force_proxy_dir(project_root()),
                    enabled=True,
                    strategy=strategy,  # type: ignore[arg-type]
                )
                log.info("strategy switch %s -> %s: %s", prev, strategy, note)
                if not had_dlls and dlls_present(discord_dir):
                    # Strategy UI may already restart; avoid double restart below.
                    if not restart_discord_client:
                        self._restart_discord_after_fresh_dlls()
            except (PermissionError, FileNotFoundError) as e:
                self.config.proxy_strategy = prev  # type: ignore[assignment]
                self.alerts.emit(Severity.CRITICAL, "strategy_switch", str(e))
                return False

        self._save_and_refresh()
        label = (
            self.i18n.t("strategy.full")
            if strategy == "full_proxy"
            else self.i18n.t("strategy.hybrid")
        )
        if restart_discord_client:
            if restart_discord():
                self.alerts.emit(
                    Severity.INFO,
                    "strategy",
                    f"{label}. {self.i18n.t('strategy.discordRestarted')}",
                    toast=True,
                )
            else:
                self.alerts.emit(
                    Severity.WARN,
                    "strategy",
                    f"{label}. {self.i18n.t('strategy.discordRestartFailed')}",
                    toast=True,
                )
        else:
            self.alerts.emit(Severity.INFO, "strategy", label, toast=True)
        self._refresh_panel(full=True)
        return True

    def toggle_tcp_proxy(self) -> None:
        with self._lock:
            if self.config.tcp_proxy:
                self.disable_tcp_proxy()
            else:
                self.enable_tcp_proxy()
        self._refresh_panel()

    def update_socks(self, host: str, port: str | int) -> bool:
        """Persist SOCKS settings; rewrite proxy.txt when TCP proxy is on."""
        host = host.strip()
        if not host:
            self.alerts.emit(Severity.WARN, "socks_invalid", "SOCKS host is empty")
            return False
        try:
            port_i = int(port)
        except (TypeError, ValueError):
            self.alerts.emit(Severity.WARN, "socks_invalid", "SOCKS port must be a number")
            return False
        if port_i < 1 or port_i > 65535:
            self.alerts.emit(Severity.WARN, "socks_invalid", "SOCKS port out of range")
            return False

        self.config.socks_host = host
        self.config.socks_port = port_i
        self.config.save()

        if self.config.tcp_proxy:
            discord_dir = self._discord_dir()
            if discord_dir is not None:
                enabled = proxy_enabled_value(discord_dir)
                write_proxy_txt(
                    discord_dir,
                    host,
                    port_i,
                    enabled=True if enabled is None else enabled,
                )
        self.kick_live_probes()
        return True

    def set_locale(self, locale: str) -> None:
        loc = "ru" if locale == "ru" else "en"
        if self.config.locale == loc:
            return
        self.config.locale = loc
        self.config.save()
        self.i18n.set_locale(loc)
        if self._panel is not None:
            self._panel.i18n.set_locale(loc)
        if self._tray is not None:
            self._tray_menu = self._build_tray_menu()
        self._refresh_panel(full=True)
        self.refresh_tray_menu()

    def _refresh_panel(self, *, full: bool = False) -> None:
        panel = getattr(self, "_panel", None)
        if panel is None:
            return

        def _run() -> None:
            if panel.isVisible():
                if full:
                    panel.refresh(full=True)
                else:
                    panel.refresh_light()

        QTimer.singleShot(0, _run)

    def _graceful_shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        log.info("graceful shutdown")
        self._elevation_dialog_active = False
        if self._instance is not None:
            self._instance.release()
        if self._tray:
            self._tray.hide()
        if self._panel is not None:
            self._panel.hide()
        self.watcher.stop()
        with self._lock:
            self.shutdown_runtime()
        if self._app:
            self._app.quit()

    def _yield_to_elevated(self) -> None:
        """Fast handoff — hide tray and release socket before heavy cleanup."""
        if self._shutting_down:
            return
        self._shutting_down = True
        log.info("takeover — yielding to elevated instance")
        self._elevation_dialog_active = False
        if self._instance is not None:
            self._instance.release()
        if self._tray:
            self._tray.hide()
        if self._panel is not None:
            self._panel.hide()
            self._panel.deleteLater()
            self._panel = None
        QTimer.singleShot(50, self._finish_takeover_shutdown)

    def _finish_takeover_shutdown(self) -> None:
        self.watcher.stop()
        with self._lock:
            self.shutdown_runtime()
        if self._app:
            self._app.quit()

    def _on_instance_message(self, cmd: str) -> None:
        if cmd == TAKEOVER:
            QTimer.singleShot(0, self._yield_to_elevated)
        elif cmd == SHOW_PANEL:
            self.open_control_panel()

    def _quit_for_relaunch(self) -> None:
        self._graceful_shutdown()

    def _relaunch_watchdog(self) -> None:
        if self._shutting_down:
            return
        log.warning("takeover not received within 20s — shutting down stale instance")
        self._graceful_shutdown()

    def _handle_elevation_choice(self, yes: bool) -> None:
        self._elevation_dialog_active = False
        if yes:
            self.config.stream_desync = True
            self.config.save()
            if relaunch_as_admin():
                log.info("elevated process spawned — waiting for TAKEOVER")
                QTimer.singleShot(20000, self._relaunch_watchdog)
            else:
                self.config.stream_desync = False
                self.config.save()
                self.alerts.emit(
                    Severity.WARN,
                    "admin_relaunch",
                    self.i18n.t("admin.relaunchFailed"),
                )
                self._refresh_panel()
        else:
            self.config.stream_desync = False
            self.config.save()
            self._refresh_panel()

    def _prompt_stream_elevation(self) -> bool:
        """Ask to relaunch as admin on the Qt main thread."""
        self._elevation_dialog_active = True

        if threading.current_thread() is not threading.main_thread():
            self.alerts.emit(
                Severity.WARN,
                "admin_required",
                self.i18n.t("admin.streamBody"),
                toast=True,
            )

        def ask() -> None:
            if self._panel is not None:
                self._panel.show_panel()
            parent = self._panel
            yes = (
                QMessageBox.question(
                    parent,
                    self.i18n.t("admin.title"),
                    self.i18n.t("admin.streamBody"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )
            self._handle_elevation_choice(yes)

        QTimer.singleShot(0, ask)
        return False

    def refresh_tray_menu(self) -> None:
        if self._tray and self._tray_menu is not None:
            self._sync_tray_menu_checks()

    def _sync_tray_menu_checks(self) -> None:
        if self._tray_menu is None:
            return
        for act in self._tray_menu.actions():
            if act.isCheckable():
                act.blockSignals(True)
                key = act.property("trayKey")
                if key == "tcp":
                    act.setChecked(self.config.tcp_proxy)
                elif key == "stream":
                    act.setChecked(self.stream_toggle_display())
                    act.setEnabled(self.config.is_hybrid)
                elif key == "autostart":
                    act.setChecked(self.config.autostart)
                    act.setEnabled(is_admin())
                act.blockSignals(False)
            elif act.menu() is not None:
                self._sync_preset_menu_checks(act.menu())

    def _sync_preset_menu_checks(self, menu: QMenu) -> None:
        usable = self.presets_usable()
        for act in menu.actions():
            if act.isCheckable() and act.property("presetName"):
                act.blockSignals(True)
                act.setChecked(self.config.preset == act.property("presetName"))
                act.setEnabled(usable)
                act.blockSignals(False)

    def _on_tray_tcp(self, checked: bool) -> None:
        if checked and not self.config.tcp_proxy:
            self.enable_tcp_proxy()
        elif not checked and self.config.tcp_proxy:
            self.disable_tcp_proxy()
        self._sync_tray_menu_checks()

    def _on_tray_stream(self, checked: bool) -> None:
        if checked and not self.stream_toggle_display():
            self.enable_stream_desync()
        elif not checked and self.config.stream_desync:
            self.disable_stream_desync()
        self._sync_tray_menu_checks()

    def _on_tray_autostart(self, checked: bool) -> None:
        if not is_admin():
            self._sync_tray_menu_checks()
            return
        if checked != self.config.autostart:
            self.toggle_autostart()
        self._sync_tray_menu_checks()

    def enable_stream_desync(self) -> bool:
        """Start winws with current preset. Returns True on success."""
        from .vendor_check import format_missing_names, missing_preset_bins

        if self.config.tun_paused:
            return False
        if self._block_if_tun():
            return False

        if self.config.is_full_proxy:
            self.alerts.emit(
                Severity.WARN,
                "strategy",
                self.i18n.t("strategy.streamDisabled"),
                toast=True,
            )
            return False
        missing = missing_zapret_bin()
        if missing:
            self.alerts.emit(
                Severity.CRITICAL,
                "zapret_missing",
                f"{self.i18n.t('state.zapretMissing')}: "
                f"{format_missing_names(missing)}",
            )
            return False

        try:
            path = self.preset_path()
        except FileNotFoundError as e:
            self.alerts.emit(Severity.CRITICAL, "preset_missing", str(e))
            return False

        bin_miss = missing_preset_bins(path)
        if bin_miss:
            self.alerts.emit(
                Severity.CRITICAL,
                "preset_bins",
                f"{self.i18n.t('state.presetBinsMissing')}: "
                f"{format_missing_names(bin_miss)}",
            )
            return False

        if not is_admin():
            return self._prompt_stream_elevation()

        try:
            self.zapret.start(path)
        except FileNotFoundError as e:
            self.alerts.emit(Severity.CRITICAL, "winws_start", str(e))
            return False
        except OSError as e:
            if elevation_error(e):
                return self._prompt_stream_elevation()
            self.alerts.emit(Severity.CRITICAL, "winws_start", str(e))
            return False

        time.sleep(0.8)
        if not self.zapret.is_running():
            msg = (
                f"winws exited immediately (code={self.zapret.last_exit_code}). "
                "See winws.log"
            )
            self.alerts.emit(Severity.CRITICAL, "winws_dead", msg)
            return False

        self.config.stream_desync = True
        self.alerts.clear_code("zapret_missing")
        self.alerts.clear_code("preset_bins")
        self._save_and_refresh()
        self.alerts.emit(
            Severity.INFO,
            "desync_on",
            f"Stream desync ON (preset={self.config.preset})",
            toast=True,
        )
        return True

    def disable_stream_desync(self) -> None:
        self.zapret.stop()
        self.config.stream_desync = False
        self._save_and_refresh()
        self.alerts.emit(Severity.INFO, "desync_off", "Stream desync OFF", toast=True)

    def toggle_stream_desync(self) -> None:
        with self._lock:
            if self.config.stream_desync:
                self.disable_stream_desync()
            else:
                self.enable_stream_desync()
        self._refresh_panel()

    def disable_all(self) -> None:
        with self._lock:
            self.zapret.stop()
            discord_dir = self._discord_dir()
            if discord_dir is not None:
                soft_disable_force_proxy(discord_dir)
            self.config.tcp_proxy = False
            self.config.stream_desync = False
            self._save_and_refresh()
            log.info("disabled all")

    def show_status(self) -> None:
        socks_ok = socks_reachable(self.config.socks_host, self.config.socks_port)
        text = build_status(
            self.config,
            self.zapret,
            socks_ok,
            watcher=self.watcher,
            alerts=self.alerts,
        )
        log.info("status:\n%s", text)
        status_file = runtime_dir() / "logs" / "last_status.txt"
        status_file.write_text(text, encoding="utf-8")
        subprocess.Popen(["notepad.exe", str(status_file)])

    def ack_critical_alert(self) -> None:
        if self.alerts.ack_critical():
            self._refresh_icon()
            self._refresh_panel()

    def open_logs(self) -> None:
        log_dir = runtime_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)  # noqa: S606

    def open_vendor_folder(self) -> None:
        path = vendor_folder()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # noqa: S606

    def open_zapret_folder(self) -> None:
        path = zapret_folder()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # noqa: S606

    def reopen_control_panel(self) -> None:
        if self._app is None:
            return

        def _run() -> None:
            from .ui.panel import ControlPanel

            if self._panel is not None:
                self._panel.close()
                self._panel.deleteLater()
            self._panel = ControlPanel(self)
            self._panel.show_panel()

        QTimer.singleShot(0, _run)

    def set_preset(self, name: str) -> None:
        if self.config.tun_paused or self.tun_present():
            self.alerts.emit(
                Severity.WARN,
                "tun_pause",
                self.i18n.t("tun.presetsLocked"),
                toast=True,
            )
            return
        if self.config.is_full_proxy:
            self.alerts.emit(
                Severity.WARN,
                "strategy",
                self.i18n.t("strategy.presetsDisabled"),
                toast=True,
            )
            return
        path = resolve_preset_path(name)
        if path is None:
            self.alerts.emit(Severity.WARN, "preset_missing", f"Missing {name}.json")
            return
        self.config.preset = name
        self.config.save()
        log.info("preset -> %s (%s)", name, path)

        want_winws = self.zapret.is_running() or self.stream_toggle_display()
        if want_winws:
            if not is_admin():
                self.alerts.emit(
                    Severity.INFO,
                    "preset_saved",
                    self.i18n.t("preset.selectNeedAdmin"),
                    toast=True,
                )
                self._refresh_panel()
                self.refresh_tray_menu()
                return
            with self._lock:
                self.zapret.stop()
                try:
                    self.zapret.start(path)
                except FileNotFoundError as e:
                    self.config.stream_desync = False
                    self._save_and_refresh()
                    self.alerts.emit(Severity.CRITICAL, "preset_winws", str(e))
                    return
                except OSError as e:
                    if elevation_error(e):
                        self.alerts.emit(
                            Severity.WARN,
                            "admin_required",
                            self.i18n.t("admin.streamNeedAdmin"),
                            toast=True,
                        )
                        self._refresh_panel()
                        return
                    self.alerts.emit(Severity.CRITICAL, "preset_winws", str(e))
                    return
                time.sleep(0.5)
                if not self.zapret.is_running():
                    self.config.stream_desync = False
                    self._save_and_refresh()
                    self.alerts.emit(
                        Severity.CRITICAL,
                        "preset_winws",
                        f"winws exited (code={self.zapret.last_exit_code})",
                    )
                    return
                self.config.stream_desync = True
                self._save_and_refresh()
        self.alerts.emit(Severity.INFO, "preset", f"Selected {name}")
        self._refresh_panel()
        self.refresh_tray_menu()

    def save_last_working_preset(self) -> None:
        name = self.config.preset
        try:
            save_preset_as_local(name)
        except FileNotFoundError as e:
            self.alerts.emit(Severity.WARN, "save_preset", str(e))
            return
        self.config.last_working_preset = name
        self.config.save()
        self.alerts.emit(
            Severity.INFO,
            "last_working",
            f"Saved last working: {name} (presets/local)",
        )

    def use_last_working_preset(self) -> None:
        name = self.config.last_working_preset
        if not name:
            self.alerts.emit(Severity.WARN, "last_working", "No last working preset yet")
            return
        self.set_preset(name)

    def check_updates(self) -> None:
        """Manual zapret engine update (Flowseal zip → bin/)."""
        try:
            need, local, remote = self.updater.needs_update()
        except Exception as e:
            self.alerts.emit(
                Severity.WARN, "zapret_update", f"Update check failed: {e}"
            )
            return
        if remote is None:
            self.alerts.emit(
                Severity.WARN, "zapret_update", "Could not fetch remote zapret version"
            )
            return
        if not need:
            self.alerts.emit(
                Severity.INFO,
                "zapret_update",
                f"Up to date: {self.updater.local_display()}",
                toast=True,
            )
            mark_zapret_checked_today()
            return
        self._apply_zapret_update(force=True)

    def _apply_zapret_update(self, *, force: bool = False) -> None:
        was_running = self.zapret.is_running()
        preset_name = self.config.preset
        if was_running:
            log.info("zapret update — stopping stream desync first")
            self.zapret.stop()
        try:
            changed, msg = self.updater.apply_update(force=force)
            mark_zapret_checked_today()
        except Exception as e:
            mark_zapret_checked_today()
            self.alerts.emit(Severity.WARN, "zapret_update", f"Update failed: {e}")
            if was_running:
                try:
                    self.zapret.start(self.preset_path())
                except Exception:
                    log.exception("failed to restart winws after update error")
            self._refresh_panel()
            return

        if changed:
            self.alerts.emit(Severity.INFO, "zapret_update", msg, toast=True)
        else:
            self.alerts.emit(Severity.INFO, "zapret_update", msg)

        if was_running:
            try:
                path = self.preset_path()
                self.zapret.start(path)
                self.alerts.emit(
                    Severity.INFO,
                    "zapret_update",
                    f"Stream restarted ({preset_name})",
                    toast=True,
                )
            except Exception as e:
                self.config.stream_desync = False
                self._save_and_refresh()
                self.alerts.emit(
                    Severity.CRITICAL,
                    "zapret_update",
                    f"Updated but stream restart failed: {e}",
                )
        self._refresh_panel()
        self.refresh_tray_menu()

    def _sync_zapret_on_startup(self) -> None:
        if zapret_checked_today():
            log.info("zapret: skip auto-check (already checked today)")
            return
        need, local, remote = self.updater.needs_update()
        if remote is None:
            mark_zapret_checked_today()
            log.info("zapret: remote version unavailable")
            return
        if not need:
            mark_zapret_checked_today()
            log.info("zapret up to date (%s)", self.updater.local_display())
            return
        log.info("zapret auto-update %s -> %s", local, remote)
        self._apply_zapret_update(force=False)

    def set_last_working_preset(self, name: str) -> None:
        if resolve_preset_path(name) is None:
            self.alerts.emit(Severity.WARN, "last_working", f"Missing {name}")
            return
        self.config.last_working_preset = name
        self.config.save()
        self.alerts.emit(
            Severity.INFO,
            "last_working",
            f"Last working: {name}",
            toast=True,
        )
        self._refresh_panel()
        self.refresh_tray_menu()

    def delete_local_preset(self, name: str) -> None:
        if not remove_local_preset_file(name):
            self.alerts.emit(Severity.WARN, "delete_preset", f"Not in local: {name}")
            return
        if self.config.last_working_preset == name:
            self.config.last_working_preset = self.config.preset
            self.config.save()
        self.alerts.emit(
            Severity.INFO,
            "delete_preset",
            f"Deleted local preset: {name}",
            toast=True,
        )
        self._refresh_panel()
        self.refresh_tray_menu()

    def open_control_panel(self) -> None:
        if self._app is None:
            log.warning("open_control_panel: no QApplication")
            return
        if self._shutting_down:
            log.warning("open_control_panel: app is shutting down")
            return

        def _open() -> None:
            try:
                from .ui.panel import ControlPanel

                log.info("open_control_panel: showing panel")
                panel = self._panel
                if panel is not None:
                    try:
                        panel.show_panel()
                        log.info(
                            "open_control_panel: panel visible=%s active=%s",
                            panel.isVisible(),
                            panel.isActiveWindow(),
                        )
                        return
                    except RuntimeError:
                        self._panel = None
                self._panel = ControlPanel(self)
                self._panel.show_panel()
                log.info(
                    "open_control_panel: panel visible=%s active=%s",
                    self._panel.isVisible(),
                    self._panel.isActiveWindow(),
                )
            except Exception:
                log.exception("open_control_panel failed")
                self._panel = None

        if threading.current_thread() is threading.main_thread():
            _open()
        else:
            QTimer.singleShot(0, _open)

    def sync_remote_presets(self, *, force: bool = False, quiet: bool = False) -> None:
        try:
            changed, msg, meta = self.remote_presets.sync_with_meta(force=force)
            mark_presets_checked_today()
        except Exception as e:
            mark_presets_checked_today()
            self.alerts.emit(Severity.WARN, "presets_sync", f"Preset sync failed: {e}")
            return
        if changed:
            self.alerts.emit(Severity.INFO, "presets_sync", msg, toast=True)
            self._presets_sync_offline = False
            self._apply_breaking_manifest(meta)
        elif not quiet:
            sev = Severity.WARN if "unavailable" in msg else Severity.INFO
            self.alerts.emit(sev, "presets_sync", msg, toast=sev == Severity.WARN)
            self._presets_sync_offline = "unavailable" in msg
        self._refresh_panel()
        self.refresh_tray_menu()

    def _apply_breaking_manifest(self, meta: dict) -> None:
        """If remote pack marks breaking, reset active preset once per version."""
        if not meta.get("breaking"):
            return
        ver = meta.get("version")
        if not isinstance(ver, str) or not ver:
            return
        if self.config.presets_breaking_acked == ver:
            return
        default = meta.get("default_preset") or "alt12-discord-only"
        if not isinstance(default, str):
            default = "alt12-discord-only"
        prev = self.config.preset
        self.config.presets_breaking_acked = ver
        self.config.save()
        self.alerts.emit(
            Severity.WARN,
            "presets_breaking",
            self.i18n.t("preset.breakingReset").format(
                prev=prev, name=default, ver=ver
            ),
            toast=True,
        )
        if self.config.is_hybrid:
            self.set_preset(default)
        else:
            self.config.preset = default
            self.config.save()

    def suggest_from_discord_logs(self) -> None:
        """Analyze renderer_js.log and toast a strategy/preset hint."""
        from .strategy_hint import analyze_renderer_log

        hint = analyze_renderer_log(strategy=self.config.proxy_strategy)
        msg = self.i18n.t(hint.message_key)
        if hint.detail:
            msg = f"{msg} ({hint.detail})"
        sev = Severity.INFO if hint.code in ("ok", "no_log") else Severity.WARN
        self.alerts.emit(sev, "strategy_hint", msg, toast=True)

    def _sync_presets_on_startup(self) -> None:
        # At most once per calendar day (manual "Check updates" still force=True).
        if presets_checked_today():
            log.info("presets: skip auto-check (already checked today)")
            return
        self.sync_remote_presets(quiet=True)

    def on_exit(self) -> None:
        self.watcher.stop()
        with self._lock:
            self.shutdown_runtime()
        if self._tray:
            self._tray.hide()
        if self._app:
            self._app.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self._sync_tray_menu_checks()
            if self._tray_menu is not None:
                self._tray_menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_control_panel()

    def _build_tray_menu(self) -> QMenu:
        t = self._tray_label
        menu = QMenu()
        menu.aboutToShow.connect(self._sync_tray_menu_checks)

        tcp = QAction(t("tray.tcp"), menu)
        tcp.setProperty("trayKey", "tcp")
        tcp.setCheckable(True)
        tcp.triggered.connect(self._on_tray_tcp)
        menu.addAction(tcp)

        stream = QAction(t("tray.stream"), menu)
        stream.setProperty("trayKey", "stream")
        stream.setCheckable(True)
        stream.triggered.connect(self._on_tray_stream)
        menu.addAction(stream)

        menu.addSeparator()

        autostart = QAction(t("tray.autostart"), menu)
        autostart.setProperty("trayKey", "autostart")
        autostart.setCheckable(True)
        autostart.triggered.connect(self._on_tray_autostart)
        menu.addAction(autostart)

        menu.addSeparator()
        menu.addAction(
            t("tray.panel"),
            lambda: QTimer.singleShot(0, self.open_control_panel),
        )
        menu.addAction(t("tray.status"), self.show_status)
        menu.addAction(t("tray.logs"), self.open_logs)
        menu.addMenu(self._preset_menu())
        menu.addMenu(self._updates_menu())
        menu.addSeparator()
        menu.addAction(t("tray.exit"), self.on_exit)
        self._sync_tray_menu_checks()
        return menu

    def _updates_menu(self) -> QMenu:
        t = self._tray_label
        ver = self.remote_presets.local_version() or "-"
        pack_label = t("tray.packCheck").replace("{version}", ver)
        sub = QMenu(t("tray.updates"))
        sub.addAction(t("tray.zapretCheck"), self.check_updates)
        sub.addAction(
            pack_label,
            lambda: self.sync_remote_presets(force=False, quiet=False),
        )
        sub.addAction(t("tray.strategyHint"), self.suggest_from_discord_logs)
        return sub

    def _preset_menu(self) -> QMenu:
        t = self._tray_label
        sub = QMenu(t("tray.preset"))
        sub.addAction(t("tray.saveLast"), self.save_last_working_preset)
        use_last = sub.addAction(t("tray.useLast"), self.use_last_working_preset)
        use_last.setEnabled(bool(self.config.last_working_preset))
        sub.addSeparator()

        labels = {
            "alt12": "alt12 (full Flowseal)",
            "alt12-discord-only": "alt12-discord-only (recommended)",
            "flowseal-discord": "flowseal-discord",
            "discord-udp-only": "discord-udp-only (weak, avoid)",
        }
        for name in list_preset_names():
            label = labels.get(name, name)
            if self.config.last_working_preset == name:
                label = f"{label} ★"
            act = sub.addAction(label, lambda checked=False, n=name: self.set_preset(n))
            act.setProperty("presetName", name)
            act.setCheckable(True)
            act.setChecked(self.config.preset == name)
        return sub

    def _tray_label(self, key: str) -> str:
        i18n = getattr(self, "i18n", None)
        return i18n.t(key) if i18n else key

    def _install_app_icon(self) -> None:
        """Taskbar / Alt-Tab icon (Windows needs AppUserModelID + .ico)."""
        if self._app is None:
            return
        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "DiscordProxyTray.App.1"
                )
            except (AttributeError, OSError):
                pass
        from PySide6.QtGui import QIcon

        from .paths import project_root

        candidates = [
            Path(__file__).resolve().parent / "ui" / "assets" / "app.ico",
            project_root() / "src" / "discord_proxy_tray" / "ui" / "assets" / "app.ico",
        ]
        # Frozen: icon lives next to packaged assets under _internal
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.insert(
                    0, Path(meipass) / "discord_proxy_tray" / "ui" / "assets" / "app.ico"
                )
        for path in candidates:
            if path.is_file():
                icon = QIcon(str(path))
                if not icon.isNull():
                    self._app.setWindowIcon(icon)
                    log.info("app icon: %s", path)
                    return
        # Fallback: rendered tray mark
        self._app.setWindowIcon(
            make_tray_icon(self.config.tcp_proxy, self.stream_toggle_display())
        )

    def run(self) -> None:
        self.i18n.set_locale(self.config.locale)
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("Discord Proxy Tray")
        self._app.setOrganizationName("DiscordProxyTray")
        self._app.setQuitOnLastWindowClosed(False)
        self._install_app_icon()
        apply_application_theme(self._app)

        self._instance = InstanceGuard()
        self._instance.message.connect(self._on_instance_message)
        if not self._instance.acquire():
            sys.exit(0)

        self.alerts.set_toast(self._notify)
        if self.config.watch_discord:
            self.watcher.start()
        if self.config.presets_check_on_start:
            threading.Thread(
                target=self._sync_presets_on_startup,
                name="presets-sync",
                daemon=True,
            ).start()
            threading.Thread(
                target=self._sync_zapret_on_startup,
                name="zapret-sync",
                daemon=True,
            ).start()
        if self.config.tcp_proxy or self.config.stream_desync or self.config.tun_paused:
            threading.Thread(
                target=self._restore_on_startup,
                name="startup-restore",
                daemon=True,
            ).start()

        self._tun_timer = QTimer()
        self._tun_timer.setInterval(10_000)
        self._tun_timer.timeout.connect(lambda: self.poll_tun_state())
        self._tun_timer.start()

        self._live_timer = QTimer()
        self._live_timer.setInterval(3000)
        self._live_timer.timeout.connect(self.kick_live_probes)
        self._live_timer.start()
        self.kick_live_probes()

        self._tray = QSystemTrayIcon(
            make_tray_icon(self.config.tcp_proxy, self.stream_toggle_display()),
            self._app,
        )
        self._tray_menu = self._build_tray_menu()
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        self._refresh_icon()

        if "--open-panel" in sys.argv:
            QTimer.singleShot(200, self.open_control_panel)

        log.info(
            "tray started (PySide6); admin=%s open_panel=%s log=%s",
            is_admin(),
            "--open-panel" in sys.argv,
            self.log_file,
        )
        exit_code = self._app.exec()
        self.watcher.stop()
        with self._lock:
            self.shutdown_runtime()
        sys.exit(exit_code)


def main() -> None:
    TrayApp().run()
