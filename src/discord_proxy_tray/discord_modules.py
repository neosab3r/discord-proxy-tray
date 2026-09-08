"""Check whether force-proxy / DWrite are loaded inside Discord processes."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

import psutil

log = logging.getLogger(__name__)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03


@dataclass(frozen=True)
class DiscordModuleStatus:
    """loaded=True if force-proxy.dll seen in any Discord process."""

    discord_running: bool
    force_proxy_loaded: bool | None  # None = could not inspect
    dwrite_loaded: bool | None
    pids_checked: int


def _discord_pids() -> list[int]:
    pids: list[int] = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info["name"] or "").lower()
        except (psutil.Error, TypeError):
            continue
        if name in ("discord.exe", "discordptb.exe", "discordcanary.exe"):
            pids.append(int(p.info["pid"]))
    return pids


def _modules_via_psutil(pid: int) -> set[str] | None:
    try:
        proc = psutil.Process(pid)
        maps = proc.memory_maps()
    except (psutil.Error, PermissionError, OSError):
        return None
    names: set[str] = set()
    for m in maps:
        path = (m.path or "").replace("\\", "/").lower()
        base = path.rsplit("/", 1)[-1]
        if base:
            names.add(base)
    return names


def _modules_via_enum(pid: int) -> set[str] | None:
    """EnumProcessModulesEx — works better than memory_maps without full admin."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    OpenProcess = k32.OpenProcess
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    OpenProcess.restype = wintypes.HANDLE

    CloseHandle = k32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    EnumProcessModulesEx = psapi.EnumProcessModulesEx
    EnumProcessModulesEx.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HMODULE),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    EnumProcessModulesEx.restype = wintypes.BOOL

    GetModuleBaseNameW = psapi.GetModuleBaseNameW
    GetModuleBaseNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    GetModuleBaseNameW.restype = wintypes.DWORD

    handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        needed = wintypes.DWORD(0)
        # First call: size
        EnumProcessModulesEx(handle, None, 0, ctypes.byref(needed), LIST_MODULES_ALL)
        count = max(int(needed.value) // ctypes.sizeof(wintypes.HMODULE), 64)
        arr = (wintypes.HMODULE * count)()
        needed2 = wintypes.DWORD(0)
        if not EnumProcessModulesEx(
            handle,
            arr,
            ctypes.sizeof(arr),
            ctypes.byref(needed2),
            LIST_MODULES_ALL,
        ):
            return None
        n = int(needed2.value) // ctypes.sizeof(wintypes.HMODULE)
        names: set[str] = set()
        buf = ctypes.create_unicode_buffer(260)
        for i in range(min(n, count)):
            if GetModuleBaseNameW(handle, arr[i], buf, 260):
                names.add(buf.value.lower())
        return names
    finally:
        CloseHandle(handle)


def discord_module_status() -> DiscordModuleStatus:
    pids = _discord_pids()
    if not pids:
        return DiscordModuleStatus(
            discord_running=False,
            force_proxy_loaded=None,
            dwrite_loaded=None,
            pids_checked=0,
        )

    fp: bool | None = False
    dw: bool | None = False
    checked = 0
    any_ok = False
    for pid in pids:
        mods = _modules_via_enum(pid)
        if mods is None:
            mods = _modules_via_psutil(pid)
        if mods is None:
            continue
        any_ok = True
        checked += 1
        if "force-proxy.dll" in mods:
            fp = True
        if "dwrite.dll" in mods:
            # Discord may load system DWrite — only count if path-less basename
            # is enough for our hijack (same name). Treat as soft signal.
            dw = True
        if fp:
            break

    if not any_ok:
        return DiscordModuleStatus(
            discord_running=True,
            force_proxy_loaded=None,
            dwrite_loaded=None,
            pids_checked=0,
        )
    return DiscordModuleStatus(
        discord_running=True,
        force_proxy_loaded=fp,
        dwrite_loaded=dw,
        pids_checked=checked,
    )
