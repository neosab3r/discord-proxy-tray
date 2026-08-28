"""System tray UI: ON/OFF drover + hidden winws."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .config import AppConfig
from .drover_manager import install_drover, latest_discord_dir, uninstall_drover
from .paths import bundled_presets_dir, project_root, zapret_dir
from .preset_updater import PresetUpdater
from .zapret_manager import ZapretManager


def _make_icon(on: bool) -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    color = (80, 200, 120) if on else (180, 80, 80)
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
        self.config = AppConfig.load()
        self.zapret = ZapretManager(zapret_dir())
        self.updater = PresetUpdater(zapret_dir())
        self.icon: pystray.Icon | None = None
        self._lock = threading.Lock()

    def preset_path(self) -> Path:
        return bundled_presets_dir() / f"{self.config.preset}.json"

    def _notify(self, title: str, message: str) -> None:
        if self.icon:
            self.icon.notify(message, title)

    def enable(self) -> None:
        with self._lock:
            discord_dir = (
                Path(self.config.discord_path)
                if self.config.discord_path
                else latest_discord_dir()
            )
            if discord_dir is None or not discord_dir.is_dir():
                self._notify("DiscordProxyTray", "Discord folder not found")
                return

            if not socks_reachable(self.config.socks_host, self.config.socks_port):
                self._notify(
                    "DiscordProxyTray",
                    f"SOCKS {self.config.socks_host}:{self.config.socks_port} not reachable. Start v2rayN.",
                )
                # still continue — user may start v2rayN later

            dll = project_root() / "vendor" / "drover" / "version.dll"
            install_drover(
                discord_dir,
                self.config.socks_host,
                self.config.socks_port,
                dll_source=dll if dll.is_file() else None,
            )
            if not dll.is_file():
                self._notify(
                    "DiscordProxyTray",
                    "drover.ini written; put version.dll in vendor/drover/",
                )

            try:
                self.zapret.start(self.preset_path())
            except FileNotFoundError as e:
                self._notify("DiscordProxyTray", str(e))
                return

            self.config.enabled = True
            self.config.save()
            if self.icon:
                self.icon.icon = _make_icon(True)
            self._notify("DiscordProxyTray", "Enabled (drover.ini + winws)")

    def disable(self) -> None:
        with self._lock:
            self.zapret.stop()
            discord_dir = (
                Path(self.config.discord_path)
                if self.config.discord_path
                else latest_discord_dir()
            )
            if discord_dir and discord_dir.is_dir():
                # Keep DLL if user already had drover; only clear ini for now
                uninstall_drover(discord_dir, remove_dll=False)
            self.config.enabled = False
            self.config.save()
            if self.icon:
                self.icon.icon = _make_icon(False)
            self._notify("DiscordProxyTray", "Disabled (winws stopped)")

    def check_updates(self) -> None:
        need, local, remote = self.updater.needs_update()
        if remote is None:
            self._notify("Updates", "Could not fetch remote version")
            return
        if need:
            self._notify(
                "Updates",
                f"New zapret: {remote} (local: {local or 'none'}). See {self.updater.release_page()}",
            )
        else:
            self._notify("Updates", f"Up to date: {local}")

    def on_exit(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.disable()
        icon.stop()

    def run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                "Enable",
                lambda: self.enable(),
                checked=lambda _: self.config.enabled,
            ),
            pystray.MenuItem("Disable", lambda: self.disable()),
            pystray.MenuItem("Check zapret updates", lambda: self.check_updates()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.on_exit),
        )
        self.icon = pystray.Icon(
            "DiscordProxyTray",
            _make_icon(self.config.enabled),
            "Discord Proxy Tray",
            menu,
        )
        self.icon.run()


def main() -> None:
    TrayApp().run()
