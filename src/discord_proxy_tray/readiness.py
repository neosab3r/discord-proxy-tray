"""Unified readiness for Status card and inline banners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .force_proxy_manager import (
    latest_discord_dir,
    scan_discord_dlls,
    vendor_force_proxy_dir,
)
from .paths import project_root, zapret_dir
from .presets import list_presets_by_source, remote_presets_dir
from .remote_presets import RemotePresetSync
from .vendor_check import missing_force_proxy_vendor, missing_zapret_bin


@dataclass(frozen=True)
class ReadinessReport:
    vendor_ok: bool
    vendor_missing: tuple[str, ...]
    zapret_ok: bool
    zapret_missing: tuple[str, ...]
    discord_dir: Path | None
    discord_ok: bool
    dll_ok: bool
    socks_ok: bool
    preset_remote_offline: bool
    preset_first_run: bool
    preset_local_version: str | None
    presets_sync_offline: bool = False


def build_readiness(
    *,
    socks_ok: bool,
    presets_remote_base: str,
    discord_dir: Path | None = None,
    presets_sync_offline: bool = False,
    strategy: str = "hybrid",
    dll_scan=None,
) -> ReadinessReport:
    strat = "full_proxy" if strategy == "full_proxy" else "hybrid"
    vendor_missing = tuple(missing_force_proxy_vendor(strategy=strat))
    zapret_missing = tuple(missing_zapret_bin())
    discord_dir = discord_dir or latest_discord_dir()
    scan = dll_scan if dll_scan is not None else scan_discord_dlls(
        discord_dir, vendor_force_proxy_dir(project_root())
    )
    dll_ok = scan.ours_ok
    rp = RemotePresetSync(presets_remote_base)
    local_ver = rp.local_version()
    remote_dir = remote_presets_dir()
    has_cache = (remote_dir / "manifest.json").is_file()
    shipped_count = len(list_presets_by_source()["shipped"])
    preset_first_run = not has_cache and shipped_count > 0

    return ReadinessReport(
        vendor_ok=not vendor_missing,
        vendor_missing=vendor_missing,
        zapret_ok=not zapret_missing,
        zapret_missing=zapret_missing,
        discord_dir=discord_dir,
        discord_ok=discord_dir is not None,
        dll_ok=dll_ok,
        socks_ok=socks_ok,
        preset_remote_offline=presets_sync_offline and has_cache,
        preset_first_run=preset_first_run and local_ver is None,
        preset_local_version=local_ver,
        presets_sync_offline=presets_sync_offline,
    )


def vendor_folder() -> Path:
    from .force_proxy_manager import vendor_force_proxy_dir

    return vendor_force_proxy_dir(project_root())


def zapret_folder() -> Path:
    return zapret_dir()
