"""Lightweight vendor / zapret readiness checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from .force_proxy_manager import (
    DWRITE_NAME,
    FORCE_PROXY_FULL_NAME,
    FORCE_PROXY_NAME,
    FORCE_PROXY_TCP_NAME,
    vendor_force_proxy_dir,
)
from .paths import project_root, zapret_dir

ProxyStrategy = Literal["hybrid", "full_proxy"]

_BIN_REF = re.compile(r"\{bin\}[/\\]([^;\s\"']+\.bin)", re.IGNORECASE)


def missing_force_proxy_vendor(
    vendor_dir: Path | None = None,
    *,
    strategy: ProxyStrategy = "hybrid",
) -> list[str]:
    root = vendor_dir or vendor_force_proxy_dir(project_root())
    missing: list[str] = []
    if not (root / DWRITE_NAME).is_file():
        missing.append(str(root / DWRITE_NAME))
    if strategy == "full_proxy":
        if not (root / FORCE_PROXY_FULL_NAME).is_file():
            missing.append(str(root / FORCE_PROXY_FULL_NAME))
    else:
        tcp = root / FORCE_PROXY_TCP_NAME
        legacy = root / FORCE_PROXY_NAME
        if not tcp.is_file() and not legacy.is_file():
            missing.append(str(tcp))
    return missing


def missing_zapret_bin() -> list[str]:
    root = zapret_dir()
    bin_dir = root / "bin"
    required = ("winws.exe", "WinDivert.dll", "WinDivert64.sys")
    missing: list[str] = []
    for name in required:
        if not (bin_dir / name).is_file():
            missing.append(str(bin_dir / name))
    return missing


def preset_bin_refs(preset_path: Path) -> list[str]:
    """Basenames referenced as ``{bin}/….bin`` in preset winws_args."""
    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    args = data.get("winws_args")
    if not isinstance(args, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for arg in args:
        if not isinstance(arg, str):
            continue
        for m in _BIN_REF.finditer(arg):
            name = Path(m.group(1)).name
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names


def missing_preset_bins(
    preset_path: Path,
    bin_dir: Path | None = None,
) -> list[str]:
    """Return absolute paths of .bin files required by the preset but absent."""
    root = bin_dir or (zapret_dir() / "bin")
    missing: list[str] = []
    for name in preset_bin_refs(preset_path):
        path = root / name
        if not path.is_file():
            missing.append(str(path))
    return missing


def format_missing_names(paths: list[str] | tuple[str, ...], *, limit: int = 4) -> str:
    names = [Path(p).name for p in paths]
    if not names:
        return ""
    if len(names) <= limit:
        return ", ".join(names)
    shown = ", ".join(names[:limit])
    return f"{shown} (+{len(names) - limit})"
