"""Poll Discord app-* folders and reinstall force-proxy after updates."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .force_proxy_manager import (
    PROXY_TXT_NAME,
    ProxyStrategy,
    dlls_present,
    find_discord_app_dirs,
    install_force_proxy,
    latest_discord_dir,
)

log = logging.getLogger(__name__)


class DiscordFolderWatcher:
    """Background poller: new/missing app-* install while TCP proxy should stay on."""

    def __init__(
        self,
        *,
        should_maintain: Callable[[], bool],
        socks: Callable[[], tuple[str, int]],
        proxy_enabled: Callable[[], bool],
        vendor_dir: Callable[[], Path],
        strategy: Callable[[], ProxyStrategy] | None = None,
        interval_sec: float = 15.0,
        on_notify: Callable[[str, str], None] | None = None,
        on_latest_changed: Callable[[Path], None] | None = None,
        on_fresh_dll_install: Callable[[], None] | None = None,
    ) -> None:
        self._should_maintain = should_maintain
        self._socks = socks
        self._proxy_enabled = proxy_enabled
        self._vendor_dir = vendor_dir
        self._strategy = strategy or (lambda: "hybrid")
        self.interval_sec = max(5.0, float(interval_sec))
        self._on_notify = on_notify
        self._on_latest_changed = on_latest_changed
        self._on_fresh_dll_install = on_fresh_dll_install
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_app_name: str | None = None
        self.last_check_ok: bool = True
        self.last_note: str = ""
        self._last_notify_key: str | None = None
        self._last_notify_at = 0.0
        # Auto-restart Discord at most once per app-* (avoids update wipe loops).
        self._restarted_for: set[str] = set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        # Seed with current latest so we don't false-notify on first tick
        latest = latest_discord_dir()
        if latest is not None:
            self.last_app_name = latest.name
        self._thread = threading.Thread(
            target=self._loop,
            name="discord-folder-watcher",
            daemon=True,
        )
        self._thread.start()
        log.info(
            "discord watcher started interval=%.0fs last_app=%s",
            self.interval_sec,
            self.last_app_name,
        )

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None
        log.info("discord watcher stopped")

    def _notify(self, title: str, message: str, *, key: str) -> None:
        now = time.monotonic()
        if key == self._last_notify_key and now - self._last_notify_at < 60:
            return
        self._last_notify_key = key
        self._last_notify_at = now
        if self._on_notify:
            self._on_notify(title, message)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_sec):
            try:
                self.tick()
            except Exception:
                log.exception("discord watcher tick failed")
                self.last_check_ok = False

    def tick(self) -> None:
        """One poll. Safe to call from tests."""
        latest = latest_discord_dir()
        apps = find_discord_app_dirs()
        if latest is None:
            self.last_note = "no app-* folder"
            self.last_check_ok = True
            return

        # Skip incomplete update folders (Update.exe still extracting).
        if not (latest / "Discord.exe").is_file():
            self.last_note = f"wait {latest.name} (no Discord.exe yet)"
            self.last_check_ok = True
            return

        new_folder = (
            self.last_app_name is not None and latest.name != self.last_app_name
        )
        if self.last_app_name != latest.name:
            prev = self.last_app_name
            self.last_app_name = latest.name
            if prev is not None and self._on_latest_changed:
                self._on_latest_changed(latest)
            if new_folder:
                log.info("discord app folder changed: %s -> %s", prev, latest.name)

        if not self._should_maintain():
            self.last_note = f"idle (tcp off) latest={latest.name} apps={len(apps)}"
            self.last_check_ok = True
            return

        had_dlls = dlls_present(latest)
        missing = not had_dlls or not (latest / PROXY_TXT_NAME).is_file()
        if not new_folder and not missing:
            self.last_note = f"ok {latest.name}"
            self.last_check_ok = True
            return

        host, port = self._socks()
        vendor = self._vendor_dir()
        strat = self._strategy()
        try:
            note = install_force_proxy(
                latest,
                host,
                port,
                vendor,
                enabled=self._proxy_enabled(),
                strategy=strat,
            )
            self.last_note = note
            self.last_check_ok = True
            log.info("watcher install %s: %s", latest.name, note)
            fresh_dlls = not had_dlls and dlls_present(latest)
            if fresh_dlls and self._on_fresh_dll_install:
                if latest.name not in self._restarted_for:
                    self._restarted_for.add(latest.name)
                    log.info(
                        "auto-restart Discord once after fresh DLLs in %s",
                        latest.name,
                    )
                    self._on_fresh_dll_install()
                else:
                    # Discord updates often wipe a new app-* after first launch.
                    # Re-copy DLLs quietly; do not kill the client in a loop.
                    log.warning(
                        "DLLs missing again in %s after prior auto-restart — "
                        "reinstalled without restart",
                        latest.name,
                    )
                    self._notify(
                        "DiscordProxyTray",
                        f"DLLs restored in {latest.name} again. "
                        "If TCP fails, restart Discord once manually "
                        "(Modes → after update finishes).",
                        key=f"rerestore:{latest.name}",
                    )
            elif new_folder:
                self._notify(
                    "DiscordProxyTray",
                    f"New Discord folder {latest.name}: DLLs updated. "
                    "Restart Discord if TCP fails.",
                    key=f"new:{latest.name}",
                )
            elif missing:
                self._notify(
                    "DiscordProxyTray",
                    f"Restored DLLs in {latest.name}",
                    key=f"restore:{latest.name}",
                )
            if "locked" in note and missing:
                self._notify(
                    "DiscordProxyTray",
                    "Discord holds DLL locks — close Discord so TCP can reinstall.",
                    key=f"lock:{latest.name}",
                )
        except (PermissionError, FileNotFoundError) as e:
            self.last_note = str(e)
            self.last_check_ok = False
            log.warning("watcher install failed: %s", e)
            self._notify(
                "DiscordProxyTray",
                str(e),
                key=f"err:{type(e).__name__}",
            )
