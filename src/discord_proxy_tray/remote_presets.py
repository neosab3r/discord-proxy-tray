"""Download preset pack from GitHub raw into data/presets/remote/."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import httpx

from .presets import remote_presets_dir
from .paths import runtime_dir
from .pack_version import parse_pack_version_text, read_pack_version

log = logging.getLogger(__name__)

# Default: presets/ on the tray repo (CI updates daily; client caches into data/presets/remote/).
DEFAULT_PRESETS_BASE = (
    "https://raw.githubusercontent.com/neosab3r/discord-proxy-tray/master/presets"
)

_CHECK_STAMP = "presets_last_check_day.txt"


def presets_checked_today() -> bool:
    stamp = runtime_dir() / _CHECK_STAMP
    if not stamp.is_file():
        return False
    try:
        return stamp.read_text(encoding="utf-8").strip() == date.today().isoformat()
    except OSError:
        return False


def mark_presets_checked_today() -> None:
    stamp = runtime_dir() / _CHECK_STAMP
    try:
        stamp.write_text(date.today().isoformat() + "\n", encoding="utf-8")
    except OSError as e:
        log.warning("could not write presets check stamp: %s", e)


class RemotePresetSync:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_PRESETS_BASE).rstrip("/")
        self.dir = remote_presets_dir()
        self.version_file = self.dir / "version.txt"

    def local_version(self) -> str | None:
        pack = read_pack_version(self.version_file)
        return pack.version if pack else None

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

    def remote_version_text(self) -> str | None:
        return self.fetch_text("version.txt")

    def remote_version(self) -> str | None:
        text = self.remote_version_text()
        if text is None:
            return None
        pack = parse_pack_version_text(text)
        return pack.version if pack else None

    def needs_update(self) -> tuple[bool, str | None, str | None]:
        local = self.local_version()
        remote = self.remote_version()
        if remote is None:
            return False, local, None
        if local is None:
            return True, local, remote
        return local != remote, local, remote

    def sync(self, *, force: bool = False) -> tuple[bool, str]:
        changed, msg, _meta = self.sync_with_meta(force=force)
        return changed, msg

    def sync_with_meta(self, *, force: bool = False) -> tuple[bool, str, dict]:
        """
        Ensure data/presets/remote matches GitHub pack.
        Returns (changed, message, meta) — meta may include breaking/version/default_preset.
        """
        empty: dict = {}
        self.dir.mkdir(parents=True, exist_ok=True)
        version_raw = self.remote_version_text()
        remote_pack = parse_pack_version_text(version_raw) if version_raw else None
        remote = remote_pack.version if remote_pack else None
        local = self.local_version()
        if remote is None:
            return (
                False,
                "remote presets unavailable (repo/presets not published yet?)",
                empty,
            )
        need = local is None or local != remote
        if not need and not force and (self.dir / "manifest.json").is_file():
            return False, f"presets up to date ({local})", empty

        manifest_raw = self.fetch_text("manifest.json")
        if not manifest_raw:
            return False, "manifest.json missing on remote", empty
        try:
            manifest = json.loads(manifest_raw)
        except json.JSONDecodeError:
            return False, "manifest.json invalid", empty

        files = manifest.get("files") or []
        if not isinstance(files, list) or not files:
            return False, "manifest has no files[]", empty

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
        self.version_file.write_text(
            version_raw if version_raw.endswith("\n") else version_raw + "\n",
            encoding="utf-8",
        )
        label = remote_pack.display() if remote_pack else remote
        msg = f"presets remote updated {local or 'none'} -> {label} ({ok} files)"
        log.info(msg)
        default_preset = manifest.get("default_preset")
        if not isinstance(default_preset, str) or not default_preset.strip():
            default_preset = None
        else:
            default_preset = default_preset.strip()
        return True, msg, {
            "breaking": bool(manifest.get("breaking")),
            "version": remote,
            "default_preset": default_preset,
        }
