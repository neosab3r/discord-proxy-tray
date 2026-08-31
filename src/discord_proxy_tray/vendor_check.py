"""Lightweight vendor / zapret readiness checks."""

from __future__ import annotations

from pathlib import Path

from .force_proxy_manager import DWRITE_NAME, FORCE_PROXY_NAME, vendor_force_proxy_dir
from .paths import project_root, zapret_dir


def missing_force_proxy_vendor(vendor_dir: Path | None = None) -> list[str]:
    root = vendor_dir or vendor_force_proxy_dir(project_root())
    missing: list[str] = []
    for name in (DWRITE_NAME, FORCE_PROXY_NAME):
        if not (root / name).is_file():
            missing.append(str(root / name))
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
