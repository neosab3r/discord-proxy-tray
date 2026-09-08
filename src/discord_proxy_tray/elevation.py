"""Windows administrator elevation helpers."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_SHELL_EXECUTE_SUCCESS = 32
SW_HIDE = 0
CREATE_NO_WINDOW = 0x08000000


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _pythonw_exe() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        pw = exe.with_name("pythonw.exe")
        if pw.is_file():
            return str(pw)
    return str(exe)


def _write_dev_launcher(project_root: Path) -> Path:
    """Small bootstrap script so elevated process finds src/ without PYTHONPATH."""
    launcher = project_root / "data" / "_elevated_relaunch.py"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    src = str(project_root / "src")
    log_file = str(project_root / "data" / "logs" / "elevated_relaunch.log")
    launcher.write_text(
        "import sys\n"
        "import traceback\n"
        "from pathlib import Path\n\n"
        f"_LOG = Path({log_file!r})\n\n"
        "def _log(msg: str) -> None:\n"
        "    try:\n"
        "        _LOG.parent.mkdir(parents=True, exist_ok=True)\n"
        "        with _LOG.open('a', encoding='utf-8') as f:\n"
        "            f.write(msg + '\\n')\n"
        "    except OSError:\n"
        "        pass\n\n"
        "try:\n"
        f"    sys.path.insert(0, {src!r})\n"
        "    for _flag in ('--takeover', '--open-panel'):\n"
        "        if _flag not in sys.argv:\n"
        "            sys.argv.append(_flag)\n"
        "    from discord_proxy_tray.app import main\n"
        "    _log('elevated relaunch starting')\n"
        "    main()\n"
        "except Exception:\n"
        "    _log(traceback.format_exc())\n"
        "    raise\n",
        encoding="utf-8",
    )
    return launcher


def _elevated_launch_spec() -> tuple[str, str, str]:
    """Return executable, parameters, working directory."""
    from .paths import project_root

    root = project_root()
    cwd = str(root)

    if getattr(sys, "frozen", False):
        # Must pass --takeover so the elevated copy asks the old instance to quit
        # and binds the single-instance socket (empty params = SHOW_PANEL then exit).
        params = subprocess.list2cmdline(["--takeover", "--open-panel"])
        return sys.executable, params, cwd

    launcher = _write_dev_launcher(root)
    exe = _pythonw_exe()
    params = subprocess.list2cmdline([str(launcher)])
    return exe, params, cwd


def relaunch_as_admin() -> bool:
    """Start a new elevated instance (no console). Returns False if UAC declined."""
    if os.name != "nt":
        return False
    if is_admin():
        return True

    exe, params, cwd = _elevated_launch_spec()
    log.info("elevated relaunch exe=%s cwd=%s", exe, cwd)

    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        params,
        cwd,
        SW_HIDE,
    )
    if rc <= _SHELL_EXECUTE_SUCCESS:
        log.warning("elevation declined or failed (code=%s)", rc)
        return False
    return True


def elevation_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 740:
        return True
    return False
