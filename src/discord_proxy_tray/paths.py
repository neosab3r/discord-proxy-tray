"""App data, portable data/, and vendor paths."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "DiscordProxyTray"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_data_dir() -> Path:
    """Roaming AppData fallback (non-portable)."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_dir() -> Path:
    """Prefer portable `data/` next to the project/exe; else AppData.

    Set DISCORD_PROXY_TRAY_APPDATA=1 to force AppData.
    """
    if os.environ.get("DISCORD_PROXY_TRAY_APPDATA", "").strip() in ("1", "true", "yes"):
        return app_data_dir()
    portable = project_root() / "data"
    portable.mkdir(parents=True, exist_ok=True)
    (portable / "logs").mkdir(parents=True, exist_ok=True)
    (portable / "presets" / "local").mkdir(parents=True, exist_ok=True)
    (portable / "presets" / "remote").mkdir(parents=True, exist_ok=True)
    return portable


def config_path() -> Path:
    return runtime_dir() / "config.json"


def zapret_dir() -> Path:
    """Prefer vendor/zapret (bundled winws); else data/zapret."""
    vendor = project_root() / "vendor" / "zapret"
    if (vendor / "bin" / "winws.exe").is_file():
        return vendor
    path = runtime_dir() / "zapret"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_presets_dir() -> Path:
    """Offline preset pack shipped with the app (git: bundle_presets/)."""
    root = project_root()
    for name in ("bundle_presets", "presets"):
        path = root / name
        if path.is_dir():
            return path
    path = root / "bundle_presets"
    path.mkdir(parents=True, exist_ok=True)
    return path
