"""Detect likely VPN TUN adapters (they fight hybrid DLL + winws)."""

from __future__ import annotations

import logging

import psutil

log = logging.getLogger(__name__)

# Substrings matched against adapter *names* (case-insensitive).
_TUN_NAME_HINTS = (
    "wintun",
    "wireguard",
    "wg-tun",
    "tap-windows",
    "tap0901",
    "tap-win",
    "outline-tap",
    "outline",
    "sing-tun",
    "singtun",
    "tun2socks",
    "meta",
    "mihomo",
    "clash",
    "v2raytun",
    "v2ray",
    "happ",
    "hiddify",
    "nekoray",
    "cloudflarewarp",
    "cloudflare warp",
    "warp",
    "wfp",
    "utun",
    "tun",
)

# Exact-ish names / substrings that are usually fine / not a VPN TUN.
_IGNORE_SUBSTR = (
    "teredo",
    "isatap",
    "6to4",
    "bluetooth",
    "loopback",
    "virtualbox",
    "vmware",
    "hyper-v",
    "vethernet",
)


def suspect_tun_adapters(*, only_up: bool = True) -> list[str]:
    """Return adapter names that look like an active VPN TUN."""
    try:
        stats = psutil.net_if_stats()
        names = list(psutil.net_if_addrs().keys())
    except Exception as e:
        log.debug("net_if lookup failed: %s", e)
        return []

    found: list[str] = []
    for name in names:
        low = name.lower().strip()
        if not low:
            continue
        if any(x in low for x in _IGNORE_SUBSTR):
            continue
        if not any(h in low for h in _TUN_NAME_HINTS):
            continue
        st = stats.get(name)
        if only_up and st is not None and not st.isup:
            continue
        found.append(name)
    return found
