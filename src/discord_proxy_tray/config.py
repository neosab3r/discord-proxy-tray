from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .paths import config_path

# hybrid = TCP-only DLL + winws stream desync
# full_proxy = TCP+UDP through force-proxy (no winws / presets)
ProxyStrategy = Literal["hybrid", "full_proxy"]


@dataclass
class AppConfig:
    socks_host: str = "127.0.0.1"
    socks_port: int = 10808
    preset: str = "alt12-discord-only"
    last_working_preset: str | None = None
    # Last remote pack version for which we already applied manifest.breaking reset
    presets_breaking_acked: str | None = None
    discord_path: str | None = None
    tcp_proxy: bool = False
    stream_desync: bool = False
    # How Discord traffic is handled when TCP proxy is involved.
    proxy_strategy: ProxyStrategy = "hybrid"
    watch_discord: bool = True
    watch_interval_sec: int = 15
    autostart: bool = False
    zapret_source: str = "flowseal"  # flowseal | local path later
    # Raw GitHub folder with version.txt + manifest.json + *.json (CI-updated)
    presets_remote_base: str = (
        "https://raw.githubusercontent.com/neosab3r/discord-proxy-tray/master/presets"
    )
    presets_check_on_start: bool = True
    locale: str = "en"  # en | ru
    # Emergency TUN pause — runtime stopped; resume_* remembers last desired state
    tun_paused: bool = False
    resume_tcp_proxy: bool = False
    resume_stream_desync: bool = False
    resume_proxy_strategy: ProxyStrategy = "hybrid"
    resume_preset: str = ""

    @property
    def any_enabled(self) -> bool:
        return self.tcp_proxy or self.stream_desync

    @property
    def is_hybrid(self) -> bool:
        return self.proxy_strategy != "full_proxy"

    @property
    def is_full_proxy(self) -> bool:
        return self.proxy_strategy == "full_proxy"

    def save(self, path: Path | None = None) -> None:
        target = path or config_path()
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
        data = json.loads(target.read_text(encoding="utf-8-sig"))
        if "enabled" in data:
            legacy = bool(data.pop("enabled"))
            data.setdefault("tcp_proxy", legacy)
            data.setdefault("stream_desync", legacy)
        base = data.get("presets_remote_base")
        if isinstance(base, str) and (
            "/bundle_presets" in base or "/main/presets" in base
        ):
            data["presets_remote_base"] = cls.presets_remote_base
        if data.get("proxy_strategy") not in ("hybrid", "full_proxy"):
            data["proxy_strategy"] = "hybrid"
        if data.get("proxy_strategy") == "full_proxy":
            data["stream_desync"] = False
        if data.get("resume_proxy_strategy") not in ("hybrid", "full_proxy"):
            data["resume_proxy_strategy"] = data.get("proxy_strategy") or "hybrid"
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
