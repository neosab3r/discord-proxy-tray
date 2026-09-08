"""Resolve and manage winws presets (local / remote cache / shipped)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Literal

from .paths import bundled_presets_dir, runtime_dir

log = logging.getLogger(__name__)

PresetSource = Literal["local", "remote", "shipped"]
PRESET_SOURCES: tuple[PresetSource, ...] = ("local", "remote", "shipped")


def local_presets_dir() -> Path:
    path = runtime_dir() / "presets" / "local"
    path.mkdir(parents=True, exist_ok=True)
    return path


def remote_presets_dir() -> Path:
    path = runtime_dir() / "presets" / "remote"
    path.mkdir(parents=True, exist_ok=True)
    return path


SKIP_PRESET_NAMES = frozenset({"manifest", "README", "index"})


def resolve_preset_path(name: str) -> Path | None:
    """Prefer local → remote cache → shipped presets/. `name` without .json."""
    if not isinstance(name, str):
        return None
    stem = name.removesuffix(".json")
    if stem.lower() in SKIP_PRESET_NAMES:
        return None
    for folder in (local_presets_dir(), remote_presets_dir(), bundled_presets_dir()):
        path = folder / f"{stem}.json"
        if path.is_file():
            return path
    return None


def _valid_preset_names(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    names: list[str] = []
    for path in folder.glob("*.json"):
        if path.stem.lower() in SKIP_PRESET_NAMES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "winws_args" not in data:
            continue
        names.append(path.stem)
    return sorted(names)


def list_presets_by_source() -> dict[PresetSource, list[str]]:
    return {
        "local": _valid_preset_names(local_presets_dir()),
        "remote": _valid_preset_names(remote_presets_dir()),
        "shipped": _valid_preset_names(bundled_presets_dir()),
    }


def resolve_preset_source(name: str) -> PresetSource | None:
    """Where `name` resolves first (local → remote → shipped)."""
    stem = name.removesuffix(".json")
    if stem.lower() in SKIP_PRESET_NAMES:
        return None
    for src, folder in (
        ("local", local_presets_dir()),
        ("remote", remote_presets_dir()),
        ("shipped", bundled_presets_dir()),
    ):
        if (folder / f"{stem}.json").is_file():
            return src
    return None


def delete_local_preset(name: str) -> bool:
    stem = name.removesuffix(".json")
    path = local_presets_dir() / f"{stem}.json"
    if not path.is_file():
        return False
    path.unlink()
    log.info("deleted local preset %s", path)
    return True


def preset_pack_version() -> str:
    """Human-readable pack label (version · date if known)."""
    from .pack_version import read_pack_version

    for folder in (remote_presets_dir(), bundled_presets_dir()):
        pack = read_pack_version(folder / "version.txt")
        if pack is not None and pack.version:
            return pack.display()
    return "-"


def preset_pack_version_raw() -> str | None:
    """First-line version only (for comparisons)."""
    from .pack_version import read_pack_version

    for folder in (remote_presets_dir(), bundled_presets_dir()):
        pack = read_pack_version(folder / "version.txt")
        if pack is not None and pack.version:
            return pack.version
    return None


def list_preset_names() -> list[str]:
    names: set[str] = set()
    for names_in_src in list_presets_by_source().values():
        names.update(names_in_src)
    return sorted(names)


def save_preset_as_local(name: str, source: Path | None = None) -> Path:
    """Copy preset into presets/local (never auto-deleted)."""
    stem = name.removesuffix(".json")
    src = source or resolve_preset_path(stem)
    if src is None or not src.is_file():
        raise FileNotFoundError(f"preset not found: {stem}")
    dest = local_presets_dir() / f"{stem}.json"
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    log.info("saved local preset %s <- %s", dest, src)
    return dest


def preset_meta(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
