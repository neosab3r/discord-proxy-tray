# Discord Proxy Tray

Tray app for desktop Discord on Windows: **TCP → local SOCKS** and **UDP voice/streams → DPI desync**, without system-wide TUN.

[English](README.en.md)

Repository: https://github.com/neosab3r/discord-proxy-tray

---

## Features

- Separate toggles: **TCP proxy** and **Stream desync**
- Installs `DWrite.dll` + `force-proxy.dll` into Discord `app-*` and keeps them after Discord updates
- Soft TCP off via `PROXY_ENABLED` (DLL stay on disk; no fragile delete while Discord is running)
- Autostart via Task Scheduler (logon, highest privileges) with delayed restore of last modes
- Desync presets: bundled pack, GitHub sync, local “last working”
- Status checks, toasts for critical/warn events, logs under `data/logs/`
- Portable layout: runtime state in `data/`, binaries in `vendor/`

---

## How it works

```text
Discord.exe
  ├─ TCP  → DWrite.dll → force-proxy.dll → 127.0.0.1:10808 → v2rayN / Happ → VPN
  └─ UDP  → direct path + winws (WinDivert desync) → Discord media
```

Chat, API, CDN and uploads are mostly **TCP**. Voice, Go Live and WebRTC media are mostly **UDP**.  
This project is a hybrid: SOCKS for TCP, zapret/winws desync for UDP — not “put all of Discord into TUN”.

`force-proxy` here is **TCP-only**, so UDP is left for winws.

---

## Requirements

1. Windows 10/11; run the tray **as Administrator** (WinDivert).
2. VPN client with **local SOCKS** (default `127.0.0.1:10808`), **TUN off**, system proxy Clear:
   - **v2rayN** — SOCKS/mixed inbound
   - **Happ** — Start + local proxy
3. Desktop Discord.

Vendor binaries are included under `vendor/` (see [licenses/NOTICE.md](licenses/NOTICE.md)).

---

## Quick start

```powershell
cd discord-proxy-tray
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
# Prefer an elevated PowerShell:
python -m discord_proxy_tray
```

Enable **TCP proxy**, restart Discord once after the first DLL install.  
Enable **Stream desync** for voice/streams. Pick a preset if the default does not work.

---

## Modes

| TCP | Stream | Typical result |
|-----|--------|----------------|
| ON | ON | Chat + voice/streams (recommended) |
| ON | OFF | Chat OK; guild voice often “No route” |
| OFF | ON | Desync only; TCP may still be blocked |
| OFF | OFF | Soft TCP off (`PROXY_ENABLED=0`) + winws stopped |

Icon: green = both, blue = TCP only, yellow = desync only, red = off.

Do not combine this hybrid with VPN **TUN** mode — it fights DLL + winws routing.

---

## Presets

| Layer | Where |
|-------|--------|
| Repo / CI | `presets/` — source of truth; Action updates daily |
| App cache | `data/presets/remote/` — downloaded when GitHub `version.txt` is newer |
| Yours | `data/presets/local/` — last working and manual copies |

Resolve order: **local → remote → shipped `presets/`**.  
The repo folder is only an offline fallback; you do not need to refresh it on every app release — the client syncs from GitHub.

Default URL: `…/master/presets`. CI: `.github/workflows/update-presets.yml` from [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

---

## Architecture

```text
Tray (Python)
  ├─ force-proxy install / soft PROXY_ENABLED + Discord app-* watcher
  └─ winws process + preset args + WinDivert
```

Runtime config and logs: `data/`.  
Sidecars: `vendor/DWrite.dll`, `vendor/force-proxy.dll`, `vendor/zapret/`.

---

## Stack

| Layer | Tech |
|-------|------|
| App | Python 3.11+, pystray, Pillow, customtkinter, httpx, psutil |
| TCP path | discord-voice-proxy `DWrite.dll` + force-proxy-tcp-only |
| UDP path | winws + WinDivert (Flowseal/bol-van zapret pack) |

The tray does not build those DLLs; it vendors and orchestrates them.

---

## Errors and status

| Level | Examples | User-facing |
|-------|----------|-------------|
| CRITICAL | Missing vendor DLL / winws, Discord folder missing, winws dies immediately | Toast + Status + `data/logs/tray.log` |
| WARN | Autostart needs admin once, SOCKS down, DLL locked by Discord | Toast (debounced) + Status |
| INFO | Restore OK, preset saved, Discord folder patched | Log (+ optional toast) |

---

## Layout

```text
discord-proxy-tray/
  src/                 # application
  presets/             # desync JSON; CI updates; offline fallback
  vendor/              # DWrite, force-proxy, zapret bin/lists
  licenses/            # third-party texts + NOTICE
  data/                # created at runtime (not in git)
  scripts/             # preset generator for CI
  .github/workflows/   # preset update workflow
```

---

## Licenses

- **This project:** [MIT](LICENSE)
- **Third-party binaries and attribution:** [licenses/NOTICE.md](licenses/NOTICE.md)

Notable terms: force-proxy and DWrite loader are **GPLv3** (sources linked in NOTICE); WinDivert is **LGPLv3 / GPLv2**; zapret/winws is **MIT**.

---

## Disclaimer

Tooling for accessing Discord under network restrictions. Use at your own risk. Authors of zapret, WinDivert, force-proxy and discord-voice-proxy are not affiliated with this tray wrapper.
