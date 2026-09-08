"""Bring Qt top-level windows to the foreground on Windows."""

from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

SW_RESTORE = 9
SW_SHOWNA = 8


def bring_window_to_foreground(hwnd: int) -> None:
    if sys.platform != "win32" or not hwnd:
        return
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        if not user32.IsWindow(hwnd):
            log.warning("bring_window_to_foreground: invalid hwnd=%s", hwnd)
            return
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOWNA)
        user32.BringWindowToTop(hwnd)
        fg = user32.GetForegroundWindow()
        if fg and fg != hwnd:
            fg_tid = user32.GetWindowThreadProcessId(fg, None)
            tid = kernel32.GetCurrentThreadId()
            attached = False
            if fg_tid != tid:
                attached = bool(user32.AttachThreadInput(fg_tid, tid, True))
            user32.SetForegroundWindow(hwnd)
            if attached:
                user32.AttachThreadInput(fg_tid, tid, False)
        else:
            user32.SetForegroundWindow(hwnd)
    except (OSError, AttributeError, ValueError) as e:
        log.debug("bring_window_to_foreground failed hwnd=%s: %s", hwnd, e)
