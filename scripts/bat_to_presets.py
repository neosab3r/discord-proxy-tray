"""Convert Flowseal general*.bat → tray preset JSON (full + discord-only).

Example:
  python scripts/bat_to_presets.py ^
    --zapret ..\\zapret-discord-youtube-main ^
    --out presets ^
    --discord-only-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


DISCORD_KEEP_SUBSTRINGS = (
    "filter-l7=discord",
    "hostlist-domains=discord.media",
    "active_discord_udp",
    "19294-19344",
    "50000-50100",
)


def _slug_from_bat(name: str) -> str:
    # "general (ALT12).bat" -> "alt12"
    # "general (FAKE TLS AUTO ALT).bat" -> "fake-tls-auto-alt"
    stem = Path(name).stem
    m = re.search(r"general\s*\((.+)\)", stem, re.I)
    raw = m.group(1) if m else stem
    slug = raw.strip().lower()
    slug = slug.replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-]+", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "general"


def _join_continued_lines(text: str) -> str:
    # Merge lines ending with ^ (cmd continuation)
    lines = text.splitlines()
    out: list[str] = []
    buf = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.endswith("^"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)


def extract_winws_command(bat_text: str) -> str | None:
    text = _join_continued_lines(bat_text)
    # Find start "winws.exe" ... rest of args on same logical line
    m = re.search(r'winws\.exe"\s+(.+)$', text, re.I | re.M)
    if not m:
        m = re.search(r"winws\.exe\s+(.+)$", text, re.I | re.M)
    if not m:
        return None
    return m.group(1).strip()


def tokenize_args(cmd: str) -> list[str]:
    # Replace Flowseal path vars with placeholders first
    cmd = cmd.replace('"%BIN%', '"{bin}/').replace("%BIN%", "{bin}/")
    cmd = cmd.replace('"%LISTS%', '"{lists}/').replace("%LISTS%", "{lists}/")
    cmd = cmd.replace('"', "")
    # Collapse GameFilter leftovers later
    parts = [p for p in cmd.split() if p]
    # Fix accidental "{bin}/quic..." already ok; fix double slashes
    fixed: list[str] = []
    for p in parts:
        p = p.replace("{bin}//", "{bin}/").replace("{lists}//", "{lists}/")
        # "%BIN%file" style sometimes becomes {bin}/file without slash issues
        fixed.append(p)
    return fixed


def split_strategies(args: list[str]) -> list[list[str]]:
    strategies: list[list[str]] = []
    cur: list[str] = []
    for a in args:
        if a == "--new":
            if cur:
                strategies.append(cur)
            cur = []
            continue
        cur.append(a)
    if cur:
        strategies.append(cur)
    return strategies


def is_wf_strategy(strat: list[str]) -> bool:
    return any(a.startswith("--wf-") for a in strat)


def is_game_strategy(strat: list[str]) -> bool:
    joined = " ".join(strat)
    return "GameFilter" in joined or "ACTIVE_GAME_UDP" in joined


def is_discord_strategy(strat: list[str]) -> bool:
    if is_wf_strategy(strat) or is_game_strategy(strat):
        return False
    joined = " ".join(strat).lower()
    return any(m in joined for m in DISCORD_KEEP_SUBSTRINGS)


def strip_gamefilter_from_wf(args: list[str]) -> list[str]:
    out: list[str] = []
    for a in args:
        if a.startswith("--wf-tcp="):
            ports = a.split("=", 1)[1]
            parts = [p for p in ports.split(",") if p and "GameFilter" not in p]
            a = "--wf-tcp=" + ",".join(parts)
        elif a.startswith("--wf-udp="):
            ports = a.split("=", 1)[1]
            parts = [p for p in ports.split(",") if p and "GameFilter" not in p]
            a = "--wf-udp=" + ",".join(parts)
        out.append(a)
    return out


def wf_for_discord_only(strats: list[list[str]]) -> list[str]:
    """Build minimal --wf-tcp / --wf-udp from kept discord strategies."""
    tcp: set[str] = set()
    udp: set[str] = set()
    for s in strats:
        joined = " ".join(s)
        for a in s:
            if a.startswith("--filter-tcp="):
                for p in a.split("=", 1)[1].split(","):
                    if p and "GameFilter" not in p:
                        tcp.add(p)
            if a.startswith("--filter-udp="):
                for p in a.split("=", 1)[1].split(","):
                    if p and "GameFilter" not in p:
                        udp.add(p)
        if "discord.media" in joined:
            for p in ("2053", "2083", "2087", "2096", "8443"):
                tcp.add(p)
        if "filter-l7=discord" in joined or "stun" in joined:
            udp.update(["19294-19344", "50000-50100"])
            if "--filter-udp=443" in joined or "filter-udp=443," in joined:
                udp.add("443")

    def port_key(x: str) -> tuple:
        if "-" in x:
            return (0, int(x.split("-")[0]), x)
        try:
            return (0, int(x), x)
        except ValueError:
            return (1, 0, x)

    wf: list[str] = []
    if tcp:
        wf.append("--wf-tcp=" + ",".join(sorted(tcp, key=port_key)))
    if udp:
        wf.append("--wf-udp=" + ",".join(sorted(udp, key=port_key)))
    return wf


def strategies_to_args(strats: list[list[str]], *, wf: list[str] | None = None) -> list[str]:
    args: list[str] = []
    if wf:
        args.extend(wf)
    for i, s in enumerate(strats):
        if i > 0 or wf:
            # after wf block, first strat needs --new before it if wf present
            if wf or i > 0:
                if args and args[-1] != "--new":
                    # insert --new between strategies
                    pass
        if args and not is_wf_strategy(s):
            # if previous ended strategy, add --new
            if args and not args[-1].startswith("--wf-") and args[-1] != "--new":
                # check if we're starting a new non-wf after wf-only prefix
                pass
    # Cleaner rebuild:
    args = []
    if wf:
        args.extend(wf)
    for i, s in enumerate(strats):
        if args:
            args.append("--new")
        args.extend(s)
    return args


def bat_to_presets(
    bat_path: Path,
    *,
    discord_only: bool,
) -> dict | None:
    raw = bat_path.read_text(encoding="utf-8", errors="replace")
    cmd = extract_winws_command(raw)
    if not cmd:
        return None
    args = strip_gamefilter_from_wf(tokenize_args(cmd))
    strats = split_strategies(args)
    # Drop game strategies always for our product defaults
    strats = [s for s in strats if not is_game_strategy(s)]

    slug = _slug_from_bat(bat_path.name)
    if discord_only:
        body = [s for s in strats if is_discord_strategy(s)]
        if not body:
            return None
        wf = wf_for_discord_only(body)
        winws = strategies_to_args(body, wf=wf)
        name = f"{slug}-discord-only"
        desc = f"Discord/STUN (+ discord.media) only - trimmed from {bat_path.name}"
    else:
        # Keep wf line(s) + all non-game strategies
        wf_strats = [strip_gamefilter_from_wf(s) for s in strats if is_wf_strategy(s)]
        body = [s for s in strats if not is_wf_strategy(s)]
        wf_args: list[str] = []
        for w in wf_strats:
            wf_args.extend(w)
        if not wf_args and body:
            # synthesize from first args if bat had wf mixed — already in first strat sometimes
            pass
        winws = list(wf_args)
        for i, s in enumerate(body):
            if winws:
                winws.append("--new")
            winws.extend(s)
        name = slug
        desc = f"Full Flowseal profile from {bat_path.name} (games filters removed)"

    return {
        "name": name,
        "description": desc,
        "version": "1.0",
        "source": bat_path.name,
        "discord_only": discord_only,
        "winws_args": winws,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--zapret",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "zapret-discord-youtube-main",
        help="Flowseal zapret-discord-youtube folder with general*.bat",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "presets",
        help="Output presets directory",
    )
    ap.add_argument(
        "--discord-only-only",
        action="store_true",
        help="Write only *-discord-only.json (recommended for tray default set)",
    )
    ap.add_argument(
        "--also-full",
        action="store_true",
        help="Also write full (non-trimmed) presets",
    )
    ap.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional bat name substrings to include (e.g. ALT12 FAKE)",
    )
    ap.add_argument(
        "--version",
        default="",
        help="Preset pack version (Flowseal tag). Written to version.txt + manifest.",
    )
    ap.add_argument(
        "--released",
        default="",
        help="ISO release date YYYY-MM-DD for version.txt second line (default: today UTC).",
    )
    ap.add_argument(
        "--clean-out",
        action="store_true",
        help="Delete existing *.json in --out before writing (keeps version.txt until rewritten)",
    )
    args = ap.parse_args()

    zapret: Path = args.zapret
    if not zapret.is_dir():
        print(f"zapret folder not found: {zapret}", file=sys.stderr)
        return 1

    bats = sorted(zapret.glob("general*.bat"))
    if not bats:
        print(f"no general*.bat in {zapret}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    if args.clean_out:
        for old in args.out.glob("*.json"):
            old.unlink(missing_ok=True)

    written_files: list[str] = []
    for bat in bats:
        if args.only and not any(s.lower() in bat.name.lower() for s in args.only):
            continue
        want_full = args.also_full or not args.discord_only_only
        want_discord = True
        if args.discord_only_only:
            want_full = False
            want_discord = True
            # Allow --also-full to still emit full profiles for --only matches
            if args.also_full:
                want_full = True

        if want_discord:
            preset = bat_to_presets(bat, discord_only=True)
            if preset:
                path = args.out / f"{preset['name']}.json"
                path.write_text(
                    json.dumps(preset, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"wrote {path.name} ({len(preset['winws_args'])} args)")
                written_files.append(path.name)
        if want_full:
            preset = bat_to_presets(bat, discord_only=False)
            if preset:
                path = args.out / f"{preset['name']}.json"
                path.write_text(
                    json.dumps(preset, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"wrote {path.name} ({len(preset['winws_args'])} args)")
                written_files.append(path.name)

    pack_version = (args.version or "").strip() or "dev"
    released_raw = (args.released or "").strip()
    if released_raw:
        released_line = released_raw
    else:
        from datetime import datetime, timezone

        released_line = datetime.now(timezone.utc).date().isoformat()
    (args.out / "version.txt").write_text(
        f"{pack_version}\n{released_line}\n", encoding="utf-8"
    )

    # Manifest lists everything currently in out/ (supports multi-pass CI runs)
    written_files = sorted(
        p.name
        for p in args.out.glob("*.json")
        if p.name.lower() != "manifest.json"
    )
    manifest = {
        "version": pack_version,
        "released": released_line,
        "source": "Flowseal/zapret-discord-youtube general*.bat",
        "count": len(written_files),
        "files": written_files,
        "note": "Client prefers local -> remote -> bundled. last_working never auto-deleted.",
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"done, {len(written_files)} presets version={pack_version} "
        f"released={released_line} -> {args.out}"
    )
    return 0 if written_files else 2


if __name__ == "__main__":
    raise SystemExit(main())
