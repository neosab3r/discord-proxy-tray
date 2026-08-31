"""Resolve and manage winws presets (bundled / remote / local)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .paths import bundled_presets_dir, runtime_dir

log = logging.getLogger(__name__)


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
    """Prefer local → remote → bundled. `name` without .json."""
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


def list_preset_names() -> list[str]:
    names: set[str] = set()
    for folder in (local_presets_dir(), remote_presets_dir(), bundled_presets_dir()):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            if path.stem.lower() in SKIP_PRESET_NAMES:
                continue
            # Real presets must declare winws_args
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or "winws_args" not in data:
                continue
            names.add(path.stem)
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
