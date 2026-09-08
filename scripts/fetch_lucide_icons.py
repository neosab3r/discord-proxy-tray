"""Download Lucide SVG icons into ui/assets/icons/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ICONS = (
    "info",
    "check",
    "folder-open",
    "refresh-cw",
    "copy",
    "triangle-alert",
    "chevron-down",
    "chevron-right",
    "circle-dot",
    "star",
    "trash-2",
    "loader-2",  # lucide: loader-circle (saved as loader-2.svg)
)

BASE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "discord_proxy_tray"
    / "ui"
    / "assets"
    / "icons"
)


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    # lucide renamed loader-2 → loader-circle on main branch
    aliases = {"loader-2": "loader-circle"}
    for name in ICONS:
        src = aliases.get(name, name)
        url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{src}.svg"
        data = urllib.request.urlopen(url, timeout=30).read()
        out = BASE / f"{name}.svg"
        out.write_bytes(data)
        print(f"wrote {out.name} ({len(data)} bytes, from {src})")


if __name__ == "__main__":
    main()
