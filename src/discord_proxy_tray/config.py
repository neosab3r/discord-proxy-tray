from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import config_path


@dataclass
class AppConfig:
    socks_host: str = "127.0.0.1"
    socks_port: int = 10808
    preset: str = "discord-udp-only"
    discord_path: str | None = None
    enabled: bool = False
    zapret_source: str = "flowseal"  # flowseal | local path later

    def save(self, path: Path | None = None) -> None:
        target = path or config_path()
        target.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        target = path or config_path()
        if not target.exists():
            cfg = cls()
            cfg.save(target)
            return cfg
        data = json.loads(target.read_text(encoding="utf-8"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
