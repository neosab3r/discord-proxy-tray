"""Download preset pack from GitHub raw into data/presets/remote/."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from .presets import remote_presets_dir

log = logging.getLogger(__name__)

# Default: presets/ on the tray repo (CI updates daily; client caches into data/presets/remote/).
DEFAULT_PRESETS_BASE = (
    "https://raw.githubusercontent.com/neosab3r/discord-proxy-tray/master/presets"
)


class RemotePresetSync:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_PRESETS_BASE).rstrip("/")
        self.dir = remote_presets_dir()
        self.version_file = self.dir / "version.txt"

    def local_version(self) -> str | None:
        if not self.version_file.is_file():
            return None
        return self.version_file.read_text(encoding="utf-8-sig").strip() or None

    def fetch_text(self, name: str, timeout: float = 15.0) -> str | None:
        url = f"{self.base_url}/{name}"
        try:
            r = httpx.get(
                url,
                timeout=timeout,
                headers={"Cache-Control": "no-cache", "User-Agent": "DiscordProxyTray"},
                follow_redirects=True,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.warning("preset fetch %s failed: %s", name, e)
            return None

    def remote_version(self) -> str | None:
        text = self.fetch_text("version.txt")
        if text is None:
            return None
        return text.strip() or None

    def needs_update(self) -> tuple[bool, str | None, str | None]:
        local = self.local_version()
        remote = self.remote_version()
        if remote is None:
            return False, local, None
        if local is None:
            return True, local, remote
        return local != remote, local, remote

    def sync(self, *, force: bool = False) -> tuple[bool, str]:
        """
        Ensure data/presets/remote matches GitHub pack.
        Returns (changed, message).
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        need, local, remote = self.needs_update()
        if remote is None:
            return False, "remote presets unavailable (repo/presets not published yet?)"
        if not need and not force and (self.dir / "manifest.json").is_file():
            return False, f"presets up to date ({local})"

        manifest_raw = self.fetch_text("manifest.json")
        if not manifest_raw:
            return False, "manifest.json missing on remote"
        try:
            manifest = json.loads(manifest_raw)
        except json.JSONDecodeError:
            return False, "manifest.json invalid"

        files = manifest.get("files") or []
        if not isinstance(files, list) or not files:
            # Fallback: only version known — cannot list files
            return False, "manifest has no files[]"

        ok = 0
        for name in files:
            if not isinstance(name, str) or not name.endswith(".json"):
                continue
            if name.lower() == "manifest.json":
                continue
            body = self.fetch_text(name)
            if body is None:
                log.warning("skip missing remote preset %s", name)
                continue
            (self.dir / name).write_text(body, encoding="utf-8")
            ok += 1

        (self.dir / "manifest.json").write_text(manifest_raw, encoding="utf-8")
        self.version_file.write_text(remote + "\n", encoding="utf-8")
        msg = f"presets remote updated {local or 'none'} -> {remote} ({ok} files)"
        log.info(msg)
        return True, msg
