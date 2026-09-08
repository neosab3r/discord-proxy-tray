# Copy force-proxy dual DLLs into discord-proxy-tray/vendor.
# Usage (from force-proxy or tray repo):
#   powershell -ExecutionPolicy Bypass -File scripts/sync_force_proxy_vendor.ps1

param(
    [string]$ForceProxyRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ForceProxyRoot) {
    $here = Split-Path -Parent $PSScriptRoot
    # Prefer sibling ../force-proxy when run from tray; else this repo is force-proxy
    $sibling = Join-Path (Split-Path -Parent $here) "force-proxy"
    if (Test-Path (Join-Path $sibling "force-proxy.sln")) {
        $ForceProxyRoot = $sibling
        $Vendor = Join-Path $here "vendor"
    } elseif (Test-Path (Join-Path $here "force-proxy.sln")) {
        $ForceProxyRoot = $here
        $Vendor = Join-Path (Split-Path -Parent $here) "discord-proxy-tray\vendor"
    } else {
        throw "Cannot locate force-proxy.sln — pass -ForceProxyRoot"
    }
} else {
    $Vendor = Join-Path (Split-Path -Parent $ForceProxyRoot) "discord-proxy-tray\vendor"
}

$tcp = Join-Path $ForceProxyRoot "x64\Release\force-proxy-tcp.dll"
$full = Join-Path $ForceProxyRoot "x64\ReleaseFull\force-proxy-full.dll"

if (-not (Test-Path $tcp)) { throw "Missing $tcp — build Release|x64 first" }
if (-not (Test-Path $full)) { throw "Missing $full — build ReleaseFull|x64 first" }
if (-not (Test-Path $Vendor)) { throw "Missing vendor dir: $Vendor" }

Copy-Item $tcp (Join-Path $Vendor "force-proxy-tcp.dll") -Force
Copy-Item $full (Join-Path $Vendor "force-proxy-full.dll") -Force
Copy-Item $tcp (Join-Path $Vendor "force-proxy.dll") -Force

Write-Host "Synced:"
Get-ChildItem (Join-Path $Vendor "force-proxy*.dll") | ForEach-Object {
    Write-Host ("  {0}  {1:N0} bytes" -f $_.Name, $_.Length)
}
