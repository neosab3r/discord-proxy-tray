"""Parse pack version.txt (version + optional release date).

Format:
  1.10.2
  2026-08-15

First line = semver/tag (used for comparisons).
Second line = ISO date YYYY-MM-DD (optional).
Legacy single-line files still work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class PackVersion:
    version: str
    released: date | None = None

    def display(self, *, date_fmt: str = "%d.%m.%Y") -> str:
        if self.released is None:
            return self.version
        return f"{self.version} · {self.released.strftime(date_fmt)}"

    def write_text(self) -> str:
        lines = [self.version.strip()]
        if self.released is not None:
            lines.append(self.released.isoformat())
        return "\n".join(lines) + "\n"


def parse_pack_version_text(text: str) -> PackVersion | None:
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return None
    version = lines[0]
    released: date | None = None
    if len(lines) >= 2:
        raw = lines[1]
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                released = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
    return PackVersion(version=version, released=released)


def read_pack_version(path: Path) -> PackVersion | None:
    if not path.is_file():
        return None
    try:
        return parse_pack_version_text(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return None


def write_pack_version(path: Path, pack: PackVersion) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pack.write_text(), encoding="utf-8")
