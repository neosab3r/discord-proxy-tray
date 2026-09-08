# Build Discord Proxy Tray release folder (Windows).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1 -Zip

param(
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step($msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$Version = (Get-Content -Path "VERSION" -Raw).Trim()
$ReleaseName = "DiscordProxyTray-$Version-win64"
$Stage = Join-Path $Root "release\$ReleaseName"
$DistApp = Join-Path $Root "dist\DiscordProxyTray"

Write-Step "Version $Version"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Step "Creating venv"
    python -m venv .venv
}

Write-Step "Installing dependencies"
& .\.venv\Scripts\python.exe -m pip install -q -U pip
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt -r requirements-build.txt

Write-Step "App icon (app.ico)"
& .\.venv\Scripts\python.exe scripts\make_app_icon.py

Write-Step "Running PyInstaller"
& .\.venv\Scripts\pyinstaller.exe DiscordProxyTray.spec --noconfirm --clean
if (-not (Test-Path "$DistApp\DiscordProxyTray.exe")) {
    throw "Build failed: $DistApp\DiscordProxyTray.exe not found"
}

Write-Step "Staging release -> release\$ReleaseName"
if (Test-Path $Stage) {
    Remove-Item $Stage -Recurse -Force
}
New-Item -ItemType Directory -Path $Stage -Force | Out-Null

Copy-Item -Path "$DistApp\*" -Destination $Stage -Recurse -Force
Copy-Item -Path "presets" -Destination "$Stage\presets" -Recurse -Force
Copy-Item -Path "vendor" -Destination "$Stage\vendor" -Recurse -Force
Copy-Item -Path "licenses" -Destination "$Stage\licenses" -Recurse -Force
Copy-Item -Path "LICENSE", "VERSION" -Destination $Stage -Force

@(
    "$Stage\data",
    "$Stage\data\logs",
    "$Stage\data\presets\local",
    "$Stage\data\presets\remote"
) | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}

Write-Step "Desktop-style shortcut (.lnk)"
$lnkPath = Join-Path $Stage "Discord Proxy Tray.lnk"
$exePath = Join-Path $Stage "DiscordProxyTray.exe"
$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($lnkPath)
$Sc.TargetPath = $exePath
$Sc.Arguments = "--open-panel"
$Sc.WorkingDirectory = $Stage
$Sc.IconLocation = "$exePath,0"
$Sc.Description = "Discord Proxy Tray"
$Sc.Save()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($Wsh) | Out-Null

Write-Step "Release ready: $Stage"

if ($Zip) {
    $ZipPath = Join-Path $Root "release\$ReleaseName.zip"
    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    Write-Step "Creating $ZipPath"
    Compress-Archive -Path $Stage -DestinationPath $ZipPath -CompressionLevel Optimal
    Write-Host "Zip: $ZipPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Run:" -ForegroundColor Green
Write-Host "  $Stage\DiscordProxyTray.exe" -ForegroundColor Yellow
