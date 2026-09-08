"""Emergency TUN pause: soft-disable DLL + stop winws, restore when clear."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger(__name__)

ProxyStrategy = Literal["hybrid", "full_proxy"]


@dataclass(frozen=True)
class TunSnapshot:
    tcp_proxy: bool
    stream_desync: bool
    proxy_strategy: ProxyStrategy
    preset: str


def snapshot_from_config(cfg) -> TunSnapshot:
    strat: ProxyStrategy = (
        "full_proxy" if cfg.proxy_strategy == "full_proxy" else "hybrid"
    )
    return TunSnapshot(
        tcp_proxy=bool(cfg.tcp_proxy),
        stream_desync=bool(cfg.stream_desync),
        proxy_strategy=strat,
        preset=str(cfg.preset or ""),
    )
