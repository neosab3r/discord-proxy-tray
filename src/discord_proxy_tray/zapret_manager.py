"""Start / stop winws.exe without a console window."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


class ZapretManager:
    def __init__(self, zapret_root: Path) -> None:
        self.zapret_root = zapret_root
        self.bin_dir = zapret_root / "bin"
        self.winws = self.bin_dir / "winws.exe"
        self._proc: subprocess.Popen[bytes] | None = None

    def is_ready(self) -> bool:
        return self.winws.is_file()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def load_preset_args(self, preset_path: Path) -> list[str]:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
        raw: list[str] = data["winws_args"]
        bin_str = str(self.bin_dir).replace("\\", "/")
        return [arg.replace("{bin}", bin_str) for arg in raw]

    def start(self, preset_path: Path) -> None:
        if self.is_running():
            return
        if not self.is_ready():
            raise FileNotFoundError(
                f"winws.exe not found in {self.bin_dir}. "
                "Download zapret-discord-youtube release into %APPDATA%\\DiscordProxyTray\\zapret\\"
            )
        args = self.load_preset_args(preset_path)
        cmd = [str(self.winws), *args]
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.bin_dir),
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
