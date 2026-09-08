# Discord Proxy Tray

Tray app for desktop Discord on Windows: **TCP → local SOCKS** and **UDP voice/streams → DPI desync** (or all Discord traffic via SOCKS), without system-wide TUN.

[Русский](README.md)

Repository: https://github.com/neosab3r/discord-proxy-tray

---

## Features

- Strategies **Hybrid** (TCP DLL + winws) and **Full** (TCP+UDP via SOCKS)
- Separate toggles **TCP proxy** / **Stream desync** (Stream disabled in Full)
- Installs `DWrite.dll` + `force-proxy.dll` into Discord `app-*` (**Install** when missing or foreign)
- Conflict detection: **drover** (`version.dll` / `drover.ini`) and other force-proxy (SHA256 vs `vendor`)
- Soft TCP off via `PROXY_ENABLED` (DLLs stay on disk)
- Emergency **TUN** pause: soft-stop + Modes overlay + restore when TUN is gone
- Watcher for Discord `app-*` updates; restarts Discord after a first-time DLL install when needed
- Autostart via Task Scheduler (logon, highest) with delayed mode restore
- Desync presets: shipped pack + GitHub sync + local “last working”
- Status, Alerts (sticky CRITICAL / one-shot WARN toasts), logs under `data/logs/`
- About → **Remove DLL** (our Discord files only + stop winws + clear tray logs)
- Portable: runtime in `data/`, binaries in `vendor/`

---

## How it works

```text
Hybrid:
  Discord.exe
    ├─ TCP  → DWrite.dll → force-proxy-tcp → 127.0.0.1:10808 → v2rayN / Happ
    └─ UDP  → direct + winws (WinDivert desync) → Discord media

Full:
  Discord.exe
    └─ TCP+UDP → DWrite.dll → force-proxy-full → SOCKS5 (incl. UDP ASSOCIATE)
```

Chat/API/CDN are mostly **TCP**. Voice / Go Live / WebRTC are mostly **UDP**.

On disk in Discord the names are always `DWrite.dll` + `force-proxy.dll`; `vendor/` ships two builds: `force-proxy-tcp.dll` and `force-proxy-full.dll` ([force-proxy-with-logs](https://github.com/neosab3r/force-proxy-with-logs)).

---

## Requirements

1. Windows 10/11; Stream desync / WinDivert needs **Administrator**.
2. VPN client with **local SOCKS** (default `127.0.0.1:10808`), **TUN off**, system proxy Clear:
   - **v2rayN** — SOCKS/mixed inbound
   - **Happ** — Start + local proxy
3. Desktop Discord.

Vendor binaries live under `vendor/` (see [licenses/NOTICE.md](licenses/NOTICE.md)).

---

## Quick start

```powershell
cd discord-proxy-tray
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
# Prefer elevated PowerShell:
python -m discord_proxy_tray
```

If Discord has no our DLLs — **Modes** overlay → **Install** (restarts Discord, enables Full).  
Then switch to **Hybrid** and enable Stream desync + a preset if you want the desync path.

### Portable release

Download the zip from [Releases](https://github.com/neosab3r/discord-proxy-tray/releases), extract, run `DiscordProxyTray.exe` (prefer Administrator for Stream / WinDivert). A shortcut with `--open-panel` is included. Runtime state lives in `data/` next to the exe.

From source: `powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1 -Zip`.

---

## Modes

| Strategy | TCP | Stream | Typical result |
|----------|-----|--------|----------------|
| Hybrid | ON | ON | Chat via SOCKS + voice/streams via winws |
| Hybrid | ON | OFF | Chat OK; guild voice often “No route” |
| Full | ON | — | Chat + voice via SOCKS UDP ASSOCIATE (presets unused) |
| any | OFF | OFF | Soft TCP off + winws stopped |

**Voice:** guild voice is usually more stable with **Hybrid + Stream + a preset like `alt12`** (full list-general, not only `*-discord-only`). Full often joins the channel but audio/video over SOCKS UDP can be flaky — a common UDP ASSOCIATE limit in clients, not just this tray.

SOCKS host:port on Modes saves on **Enter** or focus loss; status polling does not overwrite the field while you type.

Do not combine with VPN **TUN** — the app emergency-pauses.

---

## Presets

| Layer | Where |
|-------|--------|
| Repo / CI | `presets/` — source of truth; daily Action |
| App cache | `data/presets/remote/` — pulled when GitHub `version.txt` is newer |
| Yours | `data/presets/local/` — last working and manual copies |

Resolve order: **local → remote → shipped `presets/`**.  
Default URL: `…/master/presets`. CI: `.github/workflows/update-presets.yml` from [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

---

## Architecture

```text
Tray (Python / PySide6)
  ├─ install / soft PROXY_ENABLED + Discord app-* watcher
  ├─ TUN check + emergency pause
  └─ winws + presets + WinDivert (Hybrid only)
```

Runtime: `data/`.  
Sidecars: `vendor/DWrite.dll`, `vendor/force-proxy-*.dll`, `vendor/zapret/`.

---

## Stack

| Layer | Tech |
|-------|------|
| App | Python 3.11+, PySide6, httpx, psutil |
| TCP / Full | discord-voice-proxy `DWrite.dll` + [force-proxy-with-logs](https://github.com/neosab3r/force-proxy-with-logs) |
| UDP (Hybrid) | winws + WinDivert (Flowseal / bol-van zapret) |

---

## Errors and status

| Level | Examples | Where |
|-------|----------|--------|
| CRITICAL | Missing vendor / winws, Discord folder missing | Toast + sticky tooltip + Status |
| WARN | SOCKS down, TUN, DLL locked | Toast (once per session per code) + Status |
| INFO | Restore, DLL install, strategy change | Log / toast |

---

## Layout

```text
discord-proxy-tray/
  src/
  presets/
  vendor/              # DWrite, force-proxy-tcp/full, zapret
  licenses/
  data/                # runtime (not in git)
  scripts/
  .github/workflows/
```

---

## Licenses

- **This project:** [MIT](LICENSE)
- **Third-party:** [licenses/NOTICE.md](licenses/NOTICE.md)

force-proxy and `DWrite.dll` are **GPLv3**; WinDivert **LGPLv3 / GPLv2**; zapret/winws **MIT**.

---

## Disclaimer

Tooling for accessing Discord under network restrictions. Use at your own risk. Authors of zapret, WinDivert, force-proxy and discord-voice-proxy are not affiliated with this tray wrapper.
