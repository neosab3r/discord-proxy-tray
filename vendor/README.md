# Vendor

Sidecar binaries used by the tray (included in this repository).

```text
vendor/
  DWrite.dll                 # discord-voice-proxy loader
  force-proxy.dll            # legacy alias (= force-proxy-tcp.dll)
  force-proxy-tcp.dll        # TCP-only (Hybrid + winws) — PROXY_ENABLED / PROXY_LOG
  force-proxy-full.dll       # TCP+UDP SOCKS — same soft toggles
  zapret/
    bin/                     # winws, WinDivert, fake payloads
    lists/
    version.txt
```

## Strategies

| Mode | DLL copied into Discord as `force-proxy.dll` | Stream / presets |
|------|----------------------------------------------|------------------|
| **Hybrid** | `force-proxy-tcp.dll` | winws + presets (admin) |
| **Full** | `force-proxy-full.dll` | disabled |

Both DLLs are built from [`force-proxy-with-logs`](https://github.com/neosab3r/force-proxy-with-logs) (local tree often at `../force-proxy/`):

```powershell
msbuild force-proxy.sln /p:Configuration=Release /p:Platform=x64
msbuild force-proxy.sln /p:Configuration=ReleaseFull /p:Platform=x64
```

Outputs: `force-proxy\x64\Release\force-proxy-tcp.dll` and
`force-proxy\x64\ReleaseFull\force-proxy-full.dll`.

Sync into this folder (from tray repo root):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_force_proxy_vendor.ps1
```

## Other sources

| File | Source |
|------|--------|
| `DWrite.dll` | [runetfreedom/discord-voice-proxy](https://github.com/runetfreedom/discord-voice-proxy/releases) |
| `zapret/bin` | [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube/releases) |

License texts: [licenses/NOTICE.md](../licenses/NOTICE.md).
