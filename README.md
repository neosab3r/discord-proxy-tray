# Discord Proxy Tray (MVP2)

Tray app: **drover** (TCP → SOCKS) + **winws** (UDP desync), no console window for zapret.

Spec: `../mvp2-discord-tray.md`

---

## What you need to install

### 1. Python (already OK if 3.10+)

You have **Python 3.14**. Check:

```powershell
python --version
```

If missing: https://www.python.org/downloads/ — tick **Add python.exe to PATH**.

### 2. Project venv + dependencies

```powershell
cd C:\Users\user\Desktop\discordproxy\discord-proxy-tray
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If Activate is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3. Zapret binaries (required for winws)

Download latest release zip:

https://github.com/Flowseal/zapret-discord-youtube/releases/latest

Unpack so that you have:

```text
%APPDATA%\DiscordProxyTray\zapret\
  bin\winws.exe
  bin\WinDivert.dll
  bin\WinDivert64.sys
  bin\ACTIVE_DISCORD_UDP.bin   (and other .bin)
  lists\...
  version.txt                  (optional, e.g. 1.10.2)
```

Or copy from your existing folder:

```powershell
$dst = "$env:APPDATA\DiscordProxyTray\zapret"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Recurse "C:\Users\user\Desktop\discordproxy\zapret-discord-youtube-main\bin" $dst\
Copy-Item -Recurse "C:\Users\user\Desktop\discordproxy\zapret-discord-youtube-main\lists" $dst\
Copy-Item "C:\Users\user\Desktop\discordproxy\zapret-discord-youtube-main\.service\version.txt" $dst\ -ErrorAction SilentlyContinue
```

> `bin` must exist next to the release; if your local clone has no `bin`, take it from the **release zip**, not only from the source repo.

### 4. Drover DLL (for TCP proxy)

Download **version.dll** from drover releases:

https://github.com/hdk5/Drover/releases  
(or the fork you already use)

Put it at:

```text
C:\Users\user\Desktop\discordproxy\discord-proxy-tray\vendor\drover\version.dll
```

Until this file is present, tray still writes `drover.ini`, but Discord won’t load the proxy without the DLL.

### 5. Runtime (when testing)

| Component | Role |
|-----------|------|
| **v2rayN** | SOCKS `127.0.0.1:10808`, UDP ON, system proxy Clear |
| **This tray** | Run **as Administrator** (WinDivert / winws) |
| **Discord** | Restart after drover.ini / version.dll are installed |

---

## Run (dev)

```powershell
cd C:\Users\user\Desktop\discordproxy\discord-proxy-tray
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
# Prefer elevated PowerShell for winws:
python -m discord_proxy_tray
```

Tray menu: **Enable** / **Disable** / **Check zapret updates** / **Exit**.

- **Enable** → writes `drover.ini`, starts `winws.exe` **without a window**
- **Disable** → stops `winws`, removes `drover.ini` (DLL kept by default)

Config: `%APPDATA%\DiscordProxyTray\config.json`

---

## Project layout

```text
discord-proxy-tray/
  requirements.txt
  presets/discord-udp-only.json
  src/discord_proxy_tray/
    app.py              # tray UI
    drover_manager.py
    zapret_manager.py   # hidden winws
    preset_updater.py   # version check (auto-download later)
    config.py
    paths.py
  vendor/drover/        # put version.dll here
```

---

## Not required yet

- PyInstaller (for `.exe` later)
- Building zapret from source
- Visual Studio / C++ toolchain
