"""Install DWrite.dll + force-proxy.dll + proxy.txt into Discord folder."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

DWRITE_NAME = "DWrite.dll"
FORCE_PROXY_NAME = "force-proxy.dll"
FORCE_PROXY_TCP_NAME = "force-proxy-tcp.dll"
FORCE_PROXY_FULL_NAME = "force-proxy-full.dll"
PROXY_TXT_NAME = "proxy.txt"

DROVER_MARKERS = ("version.dll", "drover.ini")

# Full cleanup (Install / conflict): ours + drover + stray WinDivert in Discord
DISCORD_INJECT_NAMES = (
    DWRITE_NAME,
    FORCE_PROXY_NAME,
    FORCE_PROXY_TCP_NAME,
    FORCE_PROXY_FULL_NAME,
    PROXY_TXT_NAME,
    "force-proxy.log",
    "proxy.log",
    "WinDivert.dll",
    "WinDivert64.sys",
    "WinDivert.sys",
    *DROVER_MARKERS,
)

# About → Remove DLL: only files this app installs
OUR_DISCORD_NAMES = (
    DWRITE_NAME,
    FORCE_PROXY_NAME,
    FORCE_PROXY_TCP_NAME,
    FORCE_PROXY_FULL_NAME,
    PROXY_TXT_NAME,
    "force-proxy.log",
    "proxy.log",
)

ProxyStrategy = Literal["hybrid", "full_proxy"]


def _app_version_key(name: str) -> tuple[int, ...]:
    """Parse app-1.0.9257 → (1, 0, 9257) for numeric ordering (not lexicographic)."""
    if not name.lower().startswith("app-"):
        return (0,)
    parts = name.split("-", 1)[1].split(".")
    nums: list[int] = []
    for part in parts:
        try:
            nums.append(int(part))
        except ValueError:
            digits = "".join(c for c in part if c.isdigit())
            nums.append(int(digits) if digits else 0)
    return tuple(nums) if nums else (0,)


def find_discord_app_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord"
    if not local.is_dir():
        return []
    dirs = [p for p in local.glob("app-*") if p.is_dir()]
    return sorted(dirs, key=lambda p: _app_version_key(p.name), reverse=True)


def running_discord_app_dir() -> Path | None:
    """app-* folder of a live Discord.exe (preferred target for DLL installs)."""
    try:
        import psutil
    except ImportError:
        return None
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name not in ("discord.exe", "discordptb.exe", "discordcanary.exe"):
                continue
            exe = proc.info.get("exe")
            if not exe:
                continue
            parent = Path(exe).resolve().parent
            if parent.name.lower().startswith("app-") and parent.is_dir():
                return parent
        except (psutil.Error, OSError, TypeError, ValueError):
            continue
    return None


def latest_discord_dir() -> Path | None:
    """Prefer the running client folder; else newest app-* that has Discord.exe."""
    running = running_discord_app_dir()
    if running is not None:
        return running
    dirs = find_discord_app_dirs()
    if not dirs:
        return None
    with_exe = [d for d in dirs if (d / "Discord.exe").is_file()]
    return (with_exe or dirs)[0]


def vendor_force_proxy_dir(project_root: Path) -> Path:
    """Prefer vendor/force-proxy/, fall back to flat vendor/."""
    nested = project_root / "vendor" / "force-proxy"
    if (nested / DWRITE_NAME).is_file() or (nested / FORCE_PROXY_NAME).is_file():
        return nested
    return project_root / "vendor"


def resolve_force_proxy_dll(vendor_dir: Path, strategy: ProxyStrategy) -> Path:
    """
    Pick vendor DLL for strategy.
    hybrid → force-proxy-tcp.dll (fallback force-proxy.dll)
    full_proxy → force-proxy-full.dll
    """
    if strategy == "full_proxy":
        full = vendor_dir / FORCE_PROXY_FULL_NAME
        if full.is_file():
            return full
        raise FileNotFoundError(
            f"vendor DLL not found: {full} (TCP+UDP force-proxy build)"
        )
    tcp = vendor_dir / FORCE_PROXY_TCP_NAME
    if tcp.is_file():
        return tcp
    legacy = vendor_dir / FORCE_PROXY_NAME
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(
        f"vendor DLL not found: {tcp} or {legacy} (TCP-only force-proxy)"
    )


def dlls_present(discord_dir: Path) -> bool:
    return (discord_dir / DWRITE_NAME).is_file() and (
        discord_dir / FORCE_PROXY_NAME
    ).is_file()


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def vendor_known_hashes(vendor_dir: Path) -> dict[str, set[str]]:
    """SHA256 sets for DWrite and force-proxy variants shipped with the tray."""
    dwrite: set[str] = set()
    force: set[str] = set()
    dpath = vendor_dir / DWRITE_NAME
    if dpath.is_file():
        try:
            dwrite.add(_file_sha256(dpath))
        except OSError:
            pass
    for name in (FORCE_PROXY_TCP_NAME, FORCE_PROXY_FULL_NAME, FORCE_PROXY_NAME):
        path = vendor_dir / name
        if not path.is_file():
            continue
        try:
            force.add(_file_sha256(path))
        except OSError:
            pass
    return {"dwrite": dwrite, "force": force}


@dataclass(frozen=True)
class DiscordDllScan:
    discord_dir: Path | None
    ours_ok: bool
    missing: bool
    drover: bool
    foreign_force_proxy: bool

    @property
    def has_conflict(self) -> bool:
        return self.drover or self.foreign_force_proxy

    @property
    def needs_setup(self) -> bool:
        """Show Install overlay: missing ours or conflicting third-party hooks."""
        if self.discord_dir is None:
            return False
        return self.missing or self.has_conflict


def scan_discord_dlls(
    discord_dir: Path | None,
    vendor_dir: Path,
) -> DiscordDllScan:
    """
    Detect our DLLs vs drover (version.dll / drover.ini) vs original force-proxy.

    Original force-proxy uses the same filenames (DWrite.dll + force-proxy.dll).
    We tell it apart by SHA256 vs vendor copies (tcp / full / legacy).
    """
    if discord_dir is None or not discord_dir.is_dir():
        return DiscordDllScan(
            discord_dir=None,
            ours_ok=False,
            missing=True,
            drover=False,
            foreign_force_proxy=False,
        )

    drover = any((discord_dir / name).is_file() for name in DROVER_MARKERS)
    known = vendor_known_hashes(vendor_dir)
    dwrite_path = discord_dir / DWRITE_NAME
    force_path = discord_dir / FORCE_PROXY_NAME
    has_pair = dwrite_path.is_file() and force_path.is_file()

    dwrite_ours = False
    force_ours = False
    if dwrite_path.is_file() and known["dwrite"]:
        try:
            dwrite_ours = _file_sha256(dwrite_path) in known["dwrite"]
        except OSError:
            dwrite_ours = False

    if force_path.is_file() and known["force"]:
        try:
            force_ours = _file_sha256(force_path) in known["force"]
        except OSError:
            force_ours = False

    ours_ok = bool(has_pair and dwrite_ours and force_ours and not drover)

    # Foreign: same names (or partial) but hash ≠ our vendor builds
    foreign = False
    if not ours_ok:
        if has_pair and not (dwrite_ours and force_ours):
            foreign = True
        elif dwrite_path.is_file() and not dwrite_ours:
            foreign = True
        elif force_path.is_file() and not force_ours:
            foreign = True

    missing = not has_pair and not foreign and not drover

    return DiscordDllScan(
        discord_dir=discord_dir,
        ours_ok=ours_ok,
        missing=missing,
        drover=drover,
        foreign_force_proxy=foreign and not drover,
    )


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


def _unlink_best_effort(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        path.unlink()
        log.info("removed %s", path)
        return True
    except PermissionError:
        log.warning("cannot remove %s — close Discord first", path.name)
        return False


def remove_drover_leftovers(discord_dir: Path) -> list[str]:
    """Remove drover version.dll / drover.ini. Returns removed names."""
    removed: list[str] = []
    for name in DROVER_MARKERS:
        if _unlink_best_effort(discord_dir / name):
            removed.append(name)
    return removed


def clean_discord_inject_dir(discord_dir: Path) -> list[str]:
    """Remove our/foreign inject files from one Discord app-* folder."""
    removed: list[str] = []
    for name in DISCORD_INJECT_NAMES:
        if _unlink_best_effort(discord_dir / name):
            removed.append(name)
    return removed


def clean_our_discord_dir(discord_dir: Path) -> list[str]:
    """Remove only this app’s Discord inject files (not drover / foreign extras)."""
    removed: list[str] = []
    for name in OUR_DISCORD_NAMES:
        if _unlink_best_effort(discord_dir / name):
            removed.append(name)
    return removed


def clean_all_discord_injects() -> list[str]:
    """Clean inject files from every Discord app-* folder."""
    notes: list[str] = []
    for app_dir in find_discord_app_dirs():
        gone = clean_discord_inject_dir(app_dir)
        if gone:
            notes.append(f"{app_dir.name}: {', '.join(gone)}")
    return notes


def clean_all_our_discord_dlls() -> list[str]:
    """Remove only our DLLs/logs from every Discord app-* folder."""
    notes: list[str] = []
    for app_dir in find_discord_app_dirs():
        gone = clean_our_discord_dir(app_dir)
        if gone:
            notes.append(f"{app_dir.name}: {', '.join(gone)}")
    return notes


def install_force_proxy(
    discord_dir: Path,
    socks_host: str,
    socks_port: int,
    vendor_dir: Path,
    *,
    enabled: bool = True,
    strategy: ProxyStrategy = "hybrid",
) -> str:
    """Write proxy.txt and copy DWrite.dll + strategy-specific force-proxy.dll."""
    drover_gone = remove_drover_leftovers(discord_dir)
    write_proxy_txt(discord_dir, socks_host, socks_port, enabled=enabled)

    notes: list[str] = [f"proxy.txt ok ({strategy})"]
    if drover_gone:
        notes.append("removed drover: " + ", ".join(drover_gone))
    notes.append(_copy_dll(vendor_dir / DWRITE_NAME, discord_dir / DWRITE_NAME))
    src_fp = resolve_force_proxy_dll(vendor_dir, strategy)
    notes.append(_copy_dll(src_fp, discord_dir / FORCE_PROXY_NAME))
    notes.append(f"variant={src_fp.name}")
    return "; ".join(notes)


def soft_disable_force_proxy(discord_dir: Path) -> None:
    """PROXY_ENABLED=0; keep DLLs on disk (safe while Discord is running)."""
    set_proxy_enabled(discord_dir, False)


def uninstall_force_proxy(discord_dir: Path, *, remove_dlls: bool = False) -> None:
    soft_disable_force_proxy(discord_dir)
    if not remove_dlls:
        return
    clean_our_discord_dir(discord_dir)
