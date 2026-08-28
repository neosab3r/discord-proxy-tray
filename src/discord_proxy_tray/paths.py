"""App data and vendor paths."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "DiscordProxyTray"


def app_data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def zapret_dir() -> Path:
    path = app_data_dir() / "zapret"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_presets_dir() -> Path:
    return project_root() / "presets"
