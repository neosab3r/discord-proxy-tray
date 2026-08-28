"""Install / uninstall drover DLL + drover.ini into Discord folder."""

from __future__ import annotations

import os
from pathlib import Path


def find_discord_app_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord"
    if not local.is_dir():
        return []
    return sorted(local.glob("app-*"), key=lambda p: p.name, reverse=True)


def latest_discord_dir() -> Path | None:
    dirs = find_discord_app_dirs()
    return dirs[0] if dirs else None


def write_drover_ini(discord_dir: Path, socks_host: str, socks_port: int) -> Path:
    ini = discord_dir / "drover.ini"
    text = (
        "[drover]\n"
        f"proxy = socks5://{socks_host}:{socks_port}\n"
    )
    ini.write_text(text, encoding="utf-8")
    return ini


def drover_dll_present(discord_dir: Path) -> bool:
    return (discord_dir / "version.dll").is_file()


def install_drover(
    discord_dir: Path,
    socks_host: str,
    socks_port: int,
    dll_source: Path | None = None,
) -> None:
    """Write drover.ini. Copy version.dll if dll_source is provided."""
    write_drover_ini(discord_dir, socks_host, socks_port)
    if dll_source is None:
        return
    if not dll_source.is_file():
        raise FileNotFoundError(f"drover DLL not found: {dll_source}")
    target = discord_dir / "version.dll"
    target.write_bytes(dll_source.read_bytes())


def uninstall_drover(discord_dir: Path, remove_dll: bool = True) -> None:
    ini = discord_dir / "drover.ini"
    if ini.exists():
        ini.unlink()
    if remove_dll:
        dll = discord_dir / "version.dll"
        if dll.exists():
            dll.unlink()
