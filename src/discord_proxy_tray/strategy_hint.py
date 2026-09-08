"""Suggest strategy / preset from recent Discord renderer_js.log."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_FAIL_RE = re.compile(
    r"stream-view-high-packet-loss|stream-view-low-fps|"
    r"video-stream-receiver-ready-timeout|AVError|"
    r"stream-send-network-quality",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StrategyHint:
    code: str
    message_key: str  # i18n key
    detail: str = ""


def renderer_js_log_path() -> Path | None:
    roaming = Path(os.environ.get("APPDATA", "")) / "discord" / "logs" / "renderer_js.log"
    return roaming if roaming.is_file() else None


def analyze_renderer_log(
    *,
    strategy: str,
    path: Path | None = None,
    max_bytes: int = 512_000,
) -> StrategyHint:
    """
    Lightweight heuristic:
    - many stream-failure markers + full_proxy → suggest hybrid
    - many stream-failure markers + hybrid → suggest try other presets / wizard
    - no log / no failures → ok / inconclusive
    """
    log_path = path or renderer_js_log_path()
    if log_path is None:
        return StrategyHint("no_log", "hint.noLog")

    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return StrategyHint("no_log", "hint.noLog")

    fails = len(_FAIL_RE.findall(data))
    if fails == 0:
        return StrategyHint("ok", "hint.noStreamErrors", detail="0")

    if strategy == "full_proxy":
        return StrategyHint(
            "try_hybrid",
            "hint.tryHybrid",
            detail=str(fails),
        )
    return StrategyHint(
        "try_presets",
        "hint.tryPresets",
        detail=str(fails),
    )
