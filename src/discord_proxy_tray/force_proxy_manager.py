"""Install DWrite.dll + force-proxy.dll + proxy.txt into Discord folder."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DWRITE_NAME = "DWrite.dll"
FORCE_PROXY_NAME = "force-proxy.dll"
PROXY_TXT_NAME = "proxy.txt"


def find_discord_app_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord"
    if not local.is_dir():
        return []
    return sorted(local.glob("app-*"), key=lambda p: p.name, reverse=True)


def latest_discord_dir() -> Path | None:
    dirs = find_discord_app_dirs()
    return dirs[0] if dirs else None


def vendor_force_proxy_dir(project_root: Path) -> Path:
    """Prefer vendor/force-proxy/, fall back to flat vendor/."""
    nested = project_root / "vendor" / "force-proxy"
    if (nested / DWRITE_NAME).is_file() or (nested / FORCE_PROXY_NAME).is_file():
        return nested
    return project_root / "vendor"


def dlls_present(discord_dir: Path) -> bool:
    return (discord_dir / DWRITE_NAME).is_file() and (
        discord_dir / FORCE_PROXY_NAME
    ).is_file()


def proxy_enabled_value(discord_dir: Path) -> bool | None:
    """Read PROXY_ENABLED from proxy.txt; None if missing/unreadable."""
    path = discord_dir / PROXY_TXT_NAME
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip().upper() != "PROXY_ENABLED":
            continue
        v = value.strip().lower()
        return v not in ("0", "false", "off", "no")
    return True


def write_proxy_txt(
    discord_dir: Path,
    socks_host: str,
    socks_port: int,
    *,
    enabled: bool = True,
    log_enabled: bool = True,
) -> Path:
    path = discord_dir / PROXY_TXT_NAME
    text = (
        f"SOCKS5_PROXY_ADDRESS={socks_host}\n"
        f"SOCKS5_PROXY_PORT={socks_port}\n"
        f"PROXY_ENABLED={'1' if enabled else '0'}\n"
        f"PROXY_LOG={'1' if log_enabled else '0'}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def set_proxy_enabled(discord_dir: Path, enabled: bool) -> None:
    """Update PROXY_ENABLED in place; rewrite file if missing keys."""
    path = discord_dir / PROXY_TXT_NAME
    if not path.is_file():
        write_proxy_txt(discord_dir, "127.0.0.1", 10808, enabled=enabled)
        return

    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        log.warning("cannot read proxy.txt: %s", e)
        return

    lines = text.splitlines()
    found = False
    out: list[str] = []
    flag = "1" if enabled else "0"
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", ";")) and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key.upper() == "PROXY_ENABLED":
                out.append(f"PROXY_ENABLED={flag}")
                found = True
                continue
        out.append(line.rstrip("\r"))
    if not found:
        out.append(f"PROXY_ENABLED={flag}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_dll(source: Path, target: Path) -> str:
    """Copy DLL if missing/different. Returns short note."""
    if not source.is_file():
        raise FileNotFoundError(f"vendor DLL not found: {source}")

    if target.is_file():
        try:
            if _file_sha256(target) == _file_sha256(source):
                return f"{target.name} up to date"
        except OSError as e:
            log.warning("cannot hash %s (%s) — leave in place", target.name, e)
            return f"{target.name} locked (left as-is)"

    try:
        target.write_bytes(source.read_bytes())
        return f"{target.name} copied"
    except PermissionError:
        if target.is_file():
            log.warning(
                "Permission denied writing %s (Discord running) — keeping existing",
                target.name,
            )
            return f"{target.name} locked (left as-is)"
        raise PermissionError(
            f"Cannot write {target}: Discord is running and DLL is missing. "
            "Close Discord, Enable again, then restart Discord."
        ) from None


def _remove_drover_leftovers(discord_dir: Path) -> None:
    """Best-effort remove old drover files so they do not conflict."""
    for name in ("drover.ini", "version.dll"):
        path = discord_dir / name
        if not path.exists():
            continue
        try:
            path.unlink()
            log.info("removed leftover %s", name)
        except PermissionError:
            log.warning("cannot remove leftover %s — close Discord if TCP looks wrong", name)


def install_force_proxy(
    discord_dir: Path,
    socks_host: str,
    socks_port: int,
    vendor_dir: Path,
    *,
    enabled: bool = True,
) -> str:
    """Write proxy.txt and copy DWrite.dll + force-proxy.dll from vendor_dir."""
    _remove_drover_leftovers(discord_dir)
    write_proxy_txt(discord_dir, socks_host, socks_port, enabled=enabled)

    notes: list[str] = ["proxy.txt ok"]
    for name in (DWRITE_NAME, FORCE_PROXY_NAME):
        notes.append(_copy_dll(vendor_dir / name, discord_dir / name))
    return "; ".join(notes)


def soft_disable_force_proxy(discord_dir: Path) -> None:
    """PROXY_ENABLED=0; keep DLLs on disk (safe while Discord is running)."""
    set_proxy_enabled(discord_dir, False)


def uninstall_force_proxy(discord_dir: Path, *, remove_dlls: bool = False) -> None:
    soft_disable_force_proxy(discord_dir)
    if not remove_dlls:
        return
    for name in (DWRITE_NAME, FORCE_PROXY_NAME, PROXY_TXT_NAME):
        path = discord_dir / name
        if not path.exists():
            continue
        try:
            path.unlink()
        except PermissionError:
            log.warning("cannot remove %s — close Discord first", name)
