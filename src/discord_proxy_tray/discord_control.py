"""Start / stop / restart Discord desktop client."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

import psutil

log = logging.getLogger(__name__)

_DISCORD_EXES = frozenset(
    {"discord.exe", "discordptb.exe", "discordcanary.exe", "update.exe"}
)
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def discord_install_root() -> Path | None:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord"
    return local if local.is_dir() else None


def discord_pids(*, include_updater: bool = False) -> list[int]:
    names = _DISCORD_EXES if include_updater else (
        {"discord.exe", "discordptb.exe", "discordcanary.exe"}
    )
    pids: list[int] = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info["name"] or "").lower()
        except (psutil.Error, TypeError):
            continue
        if name in names:
            pids.append(int(p.info["pid"]))
    return pids


def discord_is_running() -> bool:
    return bool(discord_pids())


def stop_discord(*, timeout_sec: float = 12.0) -> bool:
    """Terminate Discord client processes. Returns True if none left running."""
    pids = discord_pids(include_updater=False)
    if not pids:
        return True
    procs: list[psutil.Process] = []
    for pid in pids:
        try:
            procs.append(psutil.Process(pid))
        except psutil.Error:
            continue
    for p in procs:
        try:
            log.info("stopping Discord pid=%s", p.pid)
            p.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout_sec)
    for p in alive:
        try:
            log.warning("killing Discord pid=%s", p.pid)
            p.kill()
        except psutil.Error:
            pass
    time.sleep(0.4)
    return not discord_is_running()


def start_discord() -> bool:
    """Launch Discord via Update.exe when possible."""
    root = discord_install_root()
    if root is None:
        log.warning("Discord install root not found")
        return False
    update = root / "Update.exe"
    if update.is_file():
        try:
            subprocess.Popen(
                [str(update), "--processStart", "Discord.exe"],
                cwd=str(root),
                creationflags=_CREATE_NO_WINDOW,
            )
            log.info("started Discord via Update.exe")
            return True
        except OSError as e:
            log.warning("Update.exe launch failed: %s", e)
    # Fallback: newest app-*/Discord.exe
    apps = sorted(root.glob("app-*/Discord.exe"), key=lambda p: p.parent.name, reverse=True)
    if not apps:
        log.warning("Discord.exe not found under %s", root)
        return False
    exe = apps[0]
    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=_CREATE_NO_WINDOW)
        log.info("started Discord via %s", exe)
        return True
    except OSError as e:
        log.warning("Discord.exe launch failed: %s", e)
        return False


def restart_discord() -> bool:
    """Stop Discord, then start it again. Returns True if start was attempted OK."""
    stop_discord()
    return start_discord()
