# Vendor

Sidecar binaries used by the tray (included in this repository).

```text
vendor/
  DWrite.dll                 # discord-voice-proxy loader
  force-proxy.dll            # TCP-only force-proxy
  zapret/
    bin/                     # winws, WinDivert, fake payloads, cygwin1.dll
    lists/                   # hostlists / ipsets for presets
    version.txt
```

Optional layout also supported by the code: `vendor/force-proxy/DWrite.dll` + `force-proxy.dll`.

## Upstream sources (updates)

| File | Source |
|------|--------|
| `DWrite.dll` | [runetfreedom/discord-voice-proxy releases](https://github.com/runetfreedom/discord-voice-proxy/releases) |
| `force-proxy.dll` | [neosab3r/force-proxy-tcp-only](https://github.com/neosab3r/force-proxy-tcp-only) |
| `zapret/bin`, `zapret/lists` | [Flowseal/zapret-discord-youtube releases](https://github.com/Flowseal/zapret-discord-youtube/releases) |

License texts and attribution: [licenses/NOTICE.md](../licenses/NOTICE.md).
