from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import config_path


@dataclass
class AppConfig:
    socks_host: str = "127.0.0.1"
    socks_port: int = 10808
    preset: str = "alt12-discord-only"
    last_working_preset: str | None = None
    discord_path: str | None = None
    tcp_proxy: bool = False
    stream_desync: bool = False
    watch_discord: bool = True
    watch_interval_sec: int = 15
    autostart: bool = False
    zapret_source: str = "flowseal"  # flowseal | local path later
    # Raw GitHub folder with version.txt + manifest.json + *.json (CI-updated)
    presets_remote_base: str = (
        "https://raw.githubusercontent.com/neosab3r/discord-proxy-tray/master/presets"
    )
    presets_check_on_start: bool = True

    @property
    def any_enabled(self) -> bool:
        return self.tcp_proxy or self.stream_desync

    def save(self, path: Path | None = None) -> None:
        target = path or config_path()
        # utf-8 without BOM (PowerShell Set-Content utf8 often adds BOM)
        target.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        target = path or config_path()
        if not target.exists():
            cfg = cls()
            cfg.save(target)
            return cfg
        # utf-8-sig strips BOM if present
        data = json.loads(target.read_text(encoding="utf-8-sig"))
        # Migrate old single "enabled" flag
        if "enabled" in data:
            legacy = bool(data.pop("enabled"))
            data.setdefault("tcp_proxy", legacy)
            data.setdefault("stream_desync", legacy)
        # Migrate old presets raw URL (main/bundle_presets → master/presets)
        base = data.get("presets_remote_base")
        if isinstance(base, str) and (
            "/bundle_presets" in base or "/main/presets" in base
        ):
            data["presets_remote_base"] = cls.presets_remote_base
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
