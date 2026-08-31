"""Collect status for tray: force-proxy / SOCKS / winws / Discord sockets."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from .config import AppConfig
from .alerts import Severity
from .force_proxy_manager import (
    dlls_present,
    latest_discord_dir,
    proxy_enabled_value,
)
from .paths import runtime_dir, zapret_dir
from .vendor_check import missing_force_proxy_vendor, missing_zapret_bin
from .zapret_manager import ZapretManager

if TYPE_CHECKING:
    from .alerts import AlertBus
    from .discord_watcher import DiscordFolderWatcher


def _discord_pids() -> list[int]:
    pids: list[int] = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info["name"] or "").lower()
        except (psutil.Error, TypeError):
            continue
        if name in ("discord.exe", "discordptb.exe", "discordcanary.exe"):
            pids.append(p.info["pid"])
    return pids


def count_discord_tcp_to_socks(host: str, port: int) -> int:
    """Discord TCP connections to local SOCKS = force-proxy is proxying."""
    pids = set(_discord_pids())
    if not pids:
        return 0
    count = 0
    for c in psutil.net_connections(kind="tcp"):
        if c.pid not in pids or not c.raddr:
            continue
        if c.raddr.port != port:
            continue
        if c.raddr.ip not in (host, "127.0.0.1", "::1"):
            continue
        if c.status in ("ESTABLISHED", "SYN_SENT", "SYN_RECV"):
            count += 1
    return count


def count_discord_udp() -> int:
    """UDP sockets owned by Discord (media likely active; not proof of desync)."""
    pids = set(_discord_pids())
    if not pids:
        return 0
    return sum(1 for c in psutil.net_connections(kind="udp") if c.pid in pids)


def winws_running_in_system() -> bool:
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() == "winws.exe":
                return True
        except (psutil.Error, TypeError):
            continue
    return False


def build_status(
    config: AppConfig,
    zapret: ZapretManager,
    socks_ok: bool,
    watcher: DiscordFolderWatcher | None = None,
    alerts: AlertBus | None = None,
) -> str:
    discord_dir = Path(config.discord_path) if config.discord_path else latest_discord_dir()
    vendor_miss = missing_force_proxy_vendor()
    zapret_miss = missing_zapret_bin()
    lines = [
        f"tcp_proxy={config.tcp_proxy}",
        f"stream_desync={config.stream_desync}",
        f"preset={config.preset}",
        f"last_working_preset={config.last_working_preset or '-'}",
        f"socks={config.socks_host}:{config.socks_port} reachable={socks_ok}",
        f"winws_managed={zapret.is_running()} exit={zapret.last_exit_code}",
        f"winws_in_system={winws_running_in_system()}",
        f"zapret_ready={zapret.is_ready()} root={zapret_dir()}",
        f"vendor_ok={not vendor_miss}"
        + (f" missing={','.join(Path(p).name for p in vendor_miss)}" if vendor_miss else ""),
        f"zapret_bin_ok={not zapret_miss}"
        + (f" missing={','.join(Path(p).name for p in zapret_miss)}" if zapret_miss else ""),
        f"watch_discord={config.watch_discord} interval={config.watch_interval_sec}s",
        f"autostart={config.autostart}",
    ]
    try:
        from .remote_presets import RemotePresetSync

        rp = RemotePresetSync(config.presets_remote_base)
        lines.append(
            f"presets_remote_local={rp.local_version() or '-'} "
            f"dir={rp.dir}"
        )
    except Exception:
        pass
    if watcher is not None:
        lines.append(
            f"watcher_app={watcher.last_app_name} ok={watcher.last_check_ok} "
            f"note={watcher.last_note or '-'}"
        )
    if alerts is not None:
        crit = alerts.latest(Severity.CRITICAL)
        warn = alerts.latest(Severity.WARN)
        if crit:
            lines.append(f"alert_critical=[{crit.code}] {crit.message}")
        if warn:
            lines.append(f"alert_warn=[{warn.code}] {warn.message}")
        last = alerts.latest()
        if last and last not in (crit, warn):
            lines.append(
                f"alert_last=[{last.severity.value}:{last.code}] {last.message}"
            )
    if discord_dir:
        proxy_on = proxy_enabled_value(discord_dir)
        lines.append(f"discord_dir={discord_dir}")
        lines.append(f"DWrite.dll={(discord_dir / 'DWrite.dll').is_file()}")
        lines.append(f"force-proxy.dll={(discord_dir / 'force-proxy.dll').is_file()}")
        lines.append(f"dlls_ok={dlls_present(discord_dir)}")
        lines.append(f"proxy.txt={(discord_dir / 'proxy.txt').is_file()}")
        lines.append(f"PROXY_ENABLED={proxy_on if proxy_on is not None else 'n/a'}")
    else:
        lines.append("discord_dir=NOT FOUND")

    discord_pids = _discord_pids()
    lines.append(f"discord_pids={discord_pids or 'none (start Discord)'}")
    if discord_pids:
        tcp = count_discord_tcp_to_socks(config.socks_host, config.socks_port)
        udp = count_discord_udp()
        lines.append(
            f"discord_tcp_to_socks={tcp}  (0 => proxy off / restart Discord)"
        )
        lines.append(
            f"discord_udp_sockets={udp}  (0 on stream => media not opening sockets)"
        )

    lines.append(f"logs={runtime_dir() / 'logs'}")
    return "\n".join(lines)
