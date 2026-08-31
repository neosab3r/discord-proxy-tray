"""Check Flowseal zapret-discord-youtube version (pack update stub)."""

from __future__ import annotations

from pathlib import Path

import httpx

VERSION_URL = (
    "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"
)
RELEASES_URL = "https://github.com/Flowseal/zapret-discord-youtube/releases/latest"


class PresetUpdater:
    def __init__(self, zapret_root: Path) -> None:
        self.zapret_root = zapret_root
        self.version_file = zapret_root / "version.txt"

    def local_version(self) -> str | None:
        if not self.version_file.exists():
            return None
        return self.version_file.read_text(encoding="utf-8").strip()

    def remote_version(self, timeout: float = 10.0) -> str | None:
        try:
            r = httpx.get(VERSION_URL, timeout=timeout, headers={"Cache-Control": "no-cache"})
            r.raise_for_status()
            return r.text.strip()
        except Exception:
            return None

    def needs_update(self) -> tuple[bool, str | None, str | None]:
        local = self.local_version()
        remote = self.remote_version()
        if remote is None:
            return False, local, None
        if local is None:
            return True, local, remote
        return local != remote, local, remote

    def release_page(self) -> str:
        return RELEASES_URL
