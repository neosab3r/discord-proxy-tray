# Third-party notices

Discord Proxy Tray (MIT) ships and orchestrates the following components.
Full license texts live in this folder.

| Component | Files (typical) | License | Source |
|-----------|-----------------|---------|--------|
| This project | `src/`, docs, scripts | MIT — see root `LICENSE` | this repository |
| zapret / winws | `vendor/zapret/bin/winws.exe`, `*.bin`, lists | MIT — `zapret-MIT.txt` | [bol-van/zapret](https://github.com/bol-van/zapret), Windows pack [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) |
| WinDivert | `WinDivert.dll`, `WinDivert64.sys` | LGPLv3 or GPLv2 — `WinDivert-LICENSE.txt`, `LGPL-3.0.txt`, `GPL-2.0.txt` | [basil00/WinDivert](https://github.com/basil00/WinDivert) |
| force-proxy (TCP-only fork) | `vendor/force-proxy.dll` | GPLv3 — `GPL-3.0.txt` | [neosab3r/force-proxy-tcp-only](https://github.com/neosab3r/force-proxy-tcp-only) (based on [runetfreedom/force-proxy](https://github.com/runetfreedom/force-proxy)) |
| discord-voice-proxy loader | `vendor/DWrite.dll` | GPLv3 — `GPL-3.0.txt` | [runetfreedom/discord-voice-proxy](https://github.com/runetfreedom/discord-voice-proxy) |
| Cygwin runtime (as shipped with Flowseal pack) | `vendor/zapret/bin/cygwin1.dll` | Cygwin / respective notices | Flowseal zapret-discord-youtube release |

## Aggregate distribution

The tray application does not statically link GPL libraries. It copies and launches
sidecar binaries. Modified GPL components (force-proxy TCP-only) must keep source
available at the repository links above.

WinDivert is redistributed unmodified as separate files next to `winws.exe`.
