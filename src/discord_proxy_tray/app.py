"""System tray UI: TCP proxy + stream desync toggles + diagnostics."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .alerts import AlertBus, Severity
from .autostart import (
    disable_autostart,
    enable_autostart,
    is_autostart_enabled,
)
from .config import AppConfig
from .diagnostics import build_status
from .discord_watcher import DiscordFolderWatcher
from .force_proxy_manager import (
    dlls_present,
    install_force_proxy,
    latest_discord_dir,
    soft_disable_force_proxy,
    vendor_force_proxy_dir,
)
from .logging_setup import setup_logging
from .paths import project_root, runtime_dir, zapret_dir
from .preset_updater import PresetUpdater
from .presets import list_preset_names, resolve_preset_path, save_preset_as_local
from .remote_presets import RemotePresetSync
from .vendor_check import missing_force_proxy_vendor, missing_zapret_bin
from .zapret_manager import ZapretManager

log = logging.getLogger(__name__)


def _make_icon(tcp: bool, desync: bool) -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    if tcp and desync:
        color = (80, 200, 120)
    elif tcp:
        color = (80, 160, 220)
    elif desync:
        color = (220, 180, 60)
    else:
        color = (180, 80, 80)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return img


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
        self.alerts = AlertBus()
        # Prefer ALT12 (user-verified for streams)
        if self.config.preset in ("discord-udp-only", "flowseal-discord"):
            if resolve_preset_path("alt12") is not None:
                self.config.preset = "alt12"
                self.config.save()
        self.zapret = ZapretManager(zapret_dir())
        self.updater = PresetUpdater(zapret_dir())
        self.remote_presets = RemotePresetSync(self.config.presets_remote_base)
        self.icon: pystray.Icon | None = None
        self._lock = threading.Lock()
        self.watcher = DiscordFolderWatcher(
            should_maintain=lambda: self.config.tcp_proxy,
            socks=lambda: (self.config.socks_host, self.config.socks_port),
            proxy_enabled=lambda: self.config.tcp_proxy,
            vendor_dir=lambda: vendor_force_proxy_dir(project_root()),
            interval_sec=float(self.config.watch_interval_sec),
            on_notify=lambda title, msg: self.alerts.emit(
                Severity.WARN, "watcher", msg, toast=True
            ),
            on_latest_changed=self._on_discord_latest_changed,
        )
        # Prefer real Task Scheduler state over stale config
        try:
            self.config.autostart = is_autostart_enabled()
            self.config.save()
        except OSError:
            pass
        log.info("tray started; log=%s", self.log_file)

    def preset_path(self) -> Path:
        path = resolve_preset_path(self.config.preset)
        if path is None:
            raise FileNotFoundError(f"preset not found: {self.config.preset}")
        return path

    def _notify(self, title: str, message: str) -> None:
        if self.icon:
            self.icon.notify(message, title)

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

    def _refresh_icon(self) -> None:
        if self.icon:
            self.icon.icon = _make_icon(
                self.config.tcp_proxy, self.config.stream_desync
            )

    def _save_and_refresh(self) -> None:
        self.config.save()
        self._refresh_icon()

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
        want_tcp = self.config.tcp_proxy
        want_desync = self.config.stream_desync
        if not want_tcp and not want_desync:
            return
        log.info("startup restore tcp=%s desync=%s", want_tcp, want_desync)
        tcp_ok = not want_tcp
        desync_ok = not want_desync
        for attempt in range(12):
            if want_tcp and not tcp_ok:
                with self._lock:
                    discord_dir = self._discord_dir()
                    if discord_dir is not None:
                        try:
                            note = install_force_proxy(
                                discord_dir,
                                self.config.socks_host,
                                self.config.socks_port,
                                vendor_force_proxy_dir(project_root()),
                                enabled=True,
                            )
                            if dlls_present(discord_dir):
                                tcp_ok = True
                                log.info("startup tcp ok: %s", note)
                        except (PermissionError, FileNotFoundError) as e:
                            log.warning("startup tcp attempt %s: %s", attempt + 1, e)
            if want_desync and not desync_ok:
                with self._lock:
                    try:
                        self.zapret.start(self.preset_path())
                        time.sleep(0.8)
                        if self.zapret.is_running():
                            desync_ok = True
                            log.info("startup desync ok")
                    except FileNotFoundError as e:
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
                            ("Stream", want_desync),
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
        missing = missing_force_proxy_vendor()
        if missing:
            self.alerts.emit(
                Severity.CRITICAL,
                "vendor_missing",
                "Missing vendor DLLs: " + "; ".join(Path(p).name for p in missing),
            )
            return False

        discord_dir = self._discord_dir()
        if discord_dir is None:
            self.alerts.emit(
                Severity.CRITICAL, "discord_folder", "Discord folder not found"
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
        try:
            note = install_force_proxy(
                discord_dir,
                self.config.socks_host,
                self.config.socks_port,
                vendor,
                enabled=True,
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
        self._save_and_refresh()
        self.alerts.emit(
            Severity.INFO,
            "tcp_on",
            "TCP proxy ON. Restart Discord if it was already running.",
            toast=True,
        )
        return True

    def disable_tcp_proxy(self) -> None:
        discord_dir = self._discord_dir()
        if discord_dir is not None:
            soft_disable_force_proxy(discord_dir)
        self.config.tcp_proxy = False
        self._save_and_refresh()
        self.alerts.emit(
            Severity.INFO, "tcp_off", "TCP proxy OFF (PROXY_ENABLED=0)", toast=True
        )

    def toggle_tcp_proxy(self) -> None:
        with self._lock:
            if self.config.tcp_proxy:
                self.disable_tcp_proxy()
            else:
                self.enable_tcp_proxy()

    def enable_stream_desync(self) -> bool:
        """Start winws with current preset. Returns True on success."""
        missing = missing_zapret_bin()
        if missing:
            self.alerts.emit(
                Severity.CRITICAL,
                "zapret_missing",
                "Missing zapret bin: " + "; ".join(Path(p).name for p in missing),
            )
            return False

        try:
            path = self.preset_path()
        except FileNotFoundError as e:
            self.alerts.emit(Severity.CRITICAL, "preset_missing", str(e))
            return False

        try:
            self.zapret.start(path)
        except FileNotFoundError as e:
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

    def open_logs(self) -> None:
        log_dir = runtime_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)  # noqa: S606

    def set_preset(self, name: str) -> None:
        path = resolve_preset_path(name)
        if path is None:
            self.alerts.emit(Severity.WARN, "preset_missing", f"Missing {name}.json")
            return
        self.config.preset = name
        self.config.save()
        log.info("preset -> %s (%s)", name, path)
        if self.config.stream_desync or self.zapret.is_running():
            with self._lock:
                self.zapret.stop()
                try:
                    self.zapret.start(path)
                except FileNotFoundError as e:
                    self.config.stream_desync = False
                    self._save_and_refresh()
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
        need, local, remote = self.updater.needs_update()
        if remote is None:
            self.alerts.emit(
                Severity.WARN, "zapret_update", "Could not fetch remote zapret version"
            )
            return
        if need:
            self.alerts.emit(
                Severity.WARN,
                "zapret_update",
                f"New zapret: {remote} (local: {local or 'none'})",
            )
        else:
            self.alerts.emit(Severity.INFO, "zapret_update", f"Up to date: {local}")

    def sync_remote_presets(self, *, force: bool = False, quiet: bool = False) -> None:
        try:
            changed, msg = self.remote_presets.sync(force=force)
        except Exception as e:
            self.alerts.emit(Severity.WARN, "presets_sync", f"Preset sync failed: {e}")
            return
        if changed:
            self.alerts.emit(Severity.INFO, "presets_sync", msg, toast=True)
        elif not quiet:
            sev = Severity.WARN if "unavailable" in msg else Severity.INFO
            self.alerts.emit(sev, "presets_sync", msg, toast=sev == Severity.WARN)

    def _sync_presets_on_startup(self) -> None:
        self.sync_remote_presets(quiet=True)

    def on_exit(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.watcher.stop()
        with self._lock:
            self.shutdown_runtime()
        icon.stop()

    def _preset_menu(self) -> pystray.Menu:
        items: list[pystray.MenuItem] = [
            pystray.MenuItem(
                "Save current as last working",
                lambda: self.save_last_working_preset(),
            ),
            pystray.MenuItem(
                "Use last working",
                lambda: self.use_last_working_preset(),
                enabled=lambda _: bool(self.config.last_working_preset),
            ),
            pystray.Menu.SEPARATOR,
        ]
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
            items.append(
                pystray.MenuItem(
                    label,
                    # pystray calls action(icon, item) — bind name via default kw only
                    lambda _icon, _item, n=name: self.set_preset(n),
                    checked=lambda _item, n=name: self.config.preset == n,
                )
            )
        return pystray.Menu(*items)

    def run(self) -> None:
        self.alerts.set_toast(self._notify)
        if self.config.watch_discord:
            self.watcher.start()
        if self.config.presets_check_on_start:
            threading.Thread(
                target=self._sync_presets_on_startup,
                name="presets-sync",
                daemon=True,
            ).start()
        if self.config.tcp_proxy or self.config.stream_desync:
            threading.Thread(
                target=self._restore_on_startup,
                name="startup-restore",
                daemon=True,
            ).start()
        menu = pystray.Menu(
            pystray.MenuItem(
                "TCP proxy",
                lambda: self.toggle_tcp_proxy(),
                checked=lambda _: self.config.tcp_proxy,
            ),
            pystray.MenuItem(
                "Stream desync",
                lambda: self.toggle_stream_desync(),
                checked=lambda _: self.config.stream_desync,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start with Windows",
                lambda: self.toggle_autostart(),
                checked=lambda _: self.config.autostart,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status (TCP/UDP check)", lambda: self.show_status()),
            pystray.MenuItem("Open logs folder", lambda: self.open_logs()),
            pystray.MenuItem("Preset", self._preset_menu()),
            pystray.MenuItem("Check zapret updates", lambda: self.check_updates()),
            pystray.MenuItem(
                "Check preset updates",
                lambda: self.sync_remote_presets(force=False, quiet=False),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.on_exit),
        )
        self.icon = pystray.Icon(
            "DiscordProxyTray",
            _make_icon(self.config.tcp_proxy, self.config.stream_desync),
            "Discord Proxy Tray",
            menu,
        )
        self.icon.run()


def main() -> None:
    TrayApp().run()
