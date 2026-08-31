"""Windows logon autostart via Task Scheduler (highest privileges)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from .paths import project_root, runtime_dir

log = logging.getLogger(__name__)

TASK_NAME = "DiscordProxyTray"


def _run_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def is_autostart_enabled() -> bool:
    r = _run_schtasks(["/Query", "/TN", TASK_NAME])
    return r.returncode == 0


def _launcher_path() -> Path:
    return runtime_dir() / "start_tray.cmd"


def write_launcher() -> Path:
    """Write start_tray.cmd with absolute paths (dev venv or frozen exe)."""
    path = _launcher_path()
    if getattr(sys, "frozen", False):
        body = f'@echo off\r\nstart "" "{sys.executable}"\r\n'
    else:
        root = project_root()
        py = Path(sys.executable)
        pythonw = py.with_name("pythonw.exe")
        exe = pythonw if pythonw.is_file() else py
        src = root / "src"
        body = (
            "@echo off\r\n"
            f'cd /d "{root}"\r\n'
            f'set "PYTHONPATH={src}"\r\n'
            f'start "" "{exe}" -m discord_proxy_tray\r\n'
        )
    path.write_text(body, encoding="utf-8")
    log.info("wrote launcher %s", path)
    return path


def enable_autostart() -> None:
    """Create ONLOGON task with highest privileges (needs admin once)."""
    launcher = write_launcher()
    # /RL HIGHEST so winws/WinDivert can start without a second UAC prompt
    r = _run_schtasks(
        [
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            str(launcher),
            "/SC",
            "ONLOGON",
            "/RL",
            "HIGHEST",
            "/F",
        ]
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        log.error("schtasks create failed: %s", err)
        raise PermissionError(
            "Cannot create autostart task (need Administrator once). "
            f"{err or 'schtasks failed'}"
        )
    log.info("autostart task created: %s", TASK_NAME)


def disable_autostart() -> None:
    if not is_autostart_enabled():
        return
    r = _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        log.error("schtasks delete failed: %s", err)
        raise PermissionError(
            "Cannot remove autostart task (try Run as Administrator). "
            f"{err or 'schtasks failed'}"
        )
    log.info("autostart task deleted: %s", TASK_NAME)
