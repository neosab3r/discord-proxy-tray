"""Start / stop winws.exe without a console window; log stdout/stderr."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .logging_setup import winws_log_path

log = logging.getLogger(__name__)
CREATE_NO_WINDOW = 0x08000000


class ZapretManager:
    def __init__(self, zapret_root: Path) -> None:
        self.zapret_root = zapret_root
        self.bin_dir = zapret_root / "bin"
        self.lists_dir = zapret_root / "lists"
        self.winws = self.bin_dir / "winws.exe"
        self._proc: subprocess.Popen[bytes] | None = None
        self._log_fp = None
        self.last_exit_code: int | None = None
        self.last_cmd: list[str] = []

    def is_ready(self) -> bool:
        return self.winws.is_file()

    def is_running(self) -> bool:
        if self._proc is None:
            return False
        code = self._proc.poll()
        if code is not None:
            self.last_exit_code = code
            return False
        return True

    def ensure_optional_lists(self) -> None:
        """Flowseal bats create empty *-user.txt; winws fails if path missing."""
        self.lists_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "list-general-user.txt",
            "list-exclude-user.txt",
            "ipset-exclude-user.txt",
        ):
            path = self.lists_dir / name
            if not path.exists():
                path.write_text("", encoding="utf-8")

    def load_preset_args(self, preset_path: Path) -> list[str]:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
        raw: list[str] = data["winws_args"]
        bin_str = str(self.bin_dir).replace("\\", "/")
        lists_str = str(self.lists_dir).replace("\\", "/")
        out: list[str] = []
        for arg in raw:
            out.append(
                arg.replace("{bin}", bin_str).replace("{lists}", lists_str)
            )
        return out

    def start(self, preset_path: Path) -> None:
        if self.is_running():
            log.info("winws already running pid=%s", self._proc.pid if self._proc else None)
            return
        if not self.is_ready():
            raise FileNotFoundError(
                f"winws.exe not found in {self.bin_dir}. "
                "Download zapret-discord-youtube into %APPDATA%\\DiscordProxyTray\\zapret\\"
            )
        self.ensure_optional_lists()
        args = self.load_preset_args(preset_path)
        cmd = [str(self.winws), *args]
        self.last_cmd = cmd
        log_path = winws_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fp = open(log_path, "ab", buffering=0)
        header = f"\n===== start {preset_path.name} =====\n{' '.join(cmd)}\n".encode("utf-8", errors="replace")
        self._log_fp.write(header)
        log.info("starting winws preset=%s", preset_path.name)
        log.debug("cmd: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.bin_dir),
            creationflags=CREATE_NO_WINDOW,
            stdout=self._log_fp,
            stderr=subprocess.STDOUT,
        )
        log.info("winws started pid=%s", self._proc.pid)

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            log.info("stopping winws pid=%s", self._proc.pid)
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=3)
        self.last_exit_code = self._proc.poll()
        self._proc = None
        if self._log_fp is not None:
            try:
                self._log_fp.close()
            except OSError:
                pass
            self._log_fp = None
        log.info("winws stopped exit=%s", self.last_exit_code)
