"""Update vendor/zapret from Flowseal release zip (selective extract)."""

from __future__ import annotations

import io
import logging
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx

from .pack_version import PackVersion, read_pack_version, write_pack_version
from .paths import runtime_dir

log = logging.getLogger(__name__)

VERSION_URL = (
    "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"
)
RELEASES_API = (
    "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest"
)
RELEASES_PAGE = "https://github.com/Flowseal/zapret-discord-youtube/releases/latest"

_UA = "DiscordProxyTray"
_CHECK_STAMP = "zapret_last_check_day.txt"

# Files we keep from the Flowseal zip under bin/
_BIN_NAMES = {
    "winws.exe",
    "windivert.dll",
    "windivert64.sys",
    "windivert32.sys",
}


def zapret_checked_today() -> bool:
    stamp = runtime_dir() / _CHECK_STAMP
    if not stamp.is_file():
        return False
    try:
        return stamp.read_text(encoding="utf-8").strip() == date.today().isoformat()
    except OSError:
        return False


def mark_zapret_checked_today() -> None:
    stamp = runtime_dir() / _CHECK_STAMP
    try:
        stamp.write_text(date.today().isoformat() + "\n", encoding="utf-8")
    except OSError as e:
        log.warning("could not write zapret check stamp: %s", e)


def _parse_github_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        # 2026-08-15T12:34:56Z
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _want_bin_member(name: str) -> bool:
    base = Path(name).name.lower()
    if base in _BIN_NAMES:
        return True
    return base.endswith(".bin")


class PresetUpdater:
    """Flowseal zapret engine updater (winws + WinDivert + .bin)."""

    def __init__(self, zapret_root: Path) -> None:
        self.zapret_root = zapret_root
        self.version_file = zapret_root / "version.txt"
        self.bin_dir = zapret_root / "bin"

    def local_pack(self) -> PackVersion | None:
        return read_pack_version(self.version_file)

    def local_version(self) -> str | None:
        pack = self.local_pack()
        return pack.version if pack else None

    def local_display(self) -> str:
        pack = self.local_pack()
        return pack.display() if pack else "-"

    def remote_version(self, timeout: float = 10.0) -> str | None:
        try:
            r = httpx.get(
                VERSION_URL,
                timeout=timeout,
                headers={"Cache-Control": "no-cache", "User-Agent": _UA},
                follow_redirects=True,
            )
            r.raise_for_status()
            return r.text.strip().splitlines()[0].strip() or None
        except Exception:
            return None

    def fetch_latest_release(
        self, timeout: float = 20.0
    ) -> tuple[str, date | None, str] | None:
        """Return (tag, published_date, zipball_url) or None."""
        try:
            r = httpx.get(
                RELEASES_API,
                timeout=timeout,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": _UA,
                },
                follow_redirects=True,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("zapret releases API failed: %s", e)
            return None
        tag = (data.get("tag_name") or "").strip()
        if not tag:
            return None
        published = _parse_github_date(data.get("published_at"))
        # Prefer source zipball — always has bin/
        zip_url = (data.get("zipball_url") or "").strip()
        if not zip_url:
            zip_url = (
                f"https://github.com/Flowseal/zapret-discord-youtube/archive/refs/tags/{tag}.zip"
            )
        return tag, published, zip_url

    def needs_update(self) -> tuple[bool, str | None, str | None]:
        local = self.local_version()
        info = self.fetch_latest_release()
        if info is None:
            remote = self.remote_version()
            if remote is None:
                return False, local, None
            return (local is None or local != remote), local, remote
        remote = info[0]
        return (local is None or local != remote), local, remote

    def release_page(self) -> str:
        return RELEASES_PAGE

    def apply_update(self, *, force: bool = False) -> tuple[bool, str]:
        """
        Download Flowseal zip and extract winws + WinDivert + *.bin into zapret_root/bin.
        Returns (changed, message).
        """
        info = self.fetch_latest_release()
        if info is None:
            return False, "could not resolve Flowseal latest release"
        tag, published, zip_url = info
        local = self.local_version()
        if not force and local == tag:
            label = self.local_display()
            return False, f"zapret up to date ({label})"

        log.info("zapret update downloading %s", zip_url)
        try:
            with httpx.stream(
                "GET",
                zip_url,
                timeout=120.0,
                headers={"User-Agent": _UA},
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                data = b"".join(resp.iter_bytes())
        except Exception as e:
            return False, f"download failed: {e}"

        extracted = 0
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                members = [n for n in zf.namelist() if _want_bin_member(n)]
                if not members:
                    return False, "zip has no bin/winws or .bin files"
                # Stage into temp then swap — avoid half-written bin/
                with tempfile.TemporaryDirectory(prefix="zapret_upd_") as tmp:
                    tmp_bin = Path(tmp) / "bin"
                    tmp_bin.mkdir()
                    for name in members:
                        base = Path(name).name
                        if not base or base.endswith("/"):
                            continue
                        target = tmp_bin / base
                        with zf.open(name) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted += 1
                    # Replace files in place
                    for src in tmp_bin.iterdir():
                        dest = self.bin_dir / src.name
                        shutil.copy2(src, dest)
        except zipfile.BadZipFile:
            return False, "downloaded file is not a valid zip"
        except OSError as e:
            return False, f"extract failed: {e}"

        pack = PackVersion(version=tag, released=published)
        write_pack_version(self.version_file, pack)
        msg = f"zapret updated {local or 'none'} -> {pack.display()} ({extracted} files)"
        log.info(msg)
        return True, msg
