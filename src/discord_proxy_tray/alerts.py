"""User-facing alerts with severity (toast policy + Status)."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"  # missing DLLs, winws gone, cannot run mode
    WARN = "warn"  # autostart needs admin, SOCKS down, soft failures
    INFO = "info"  # restored, preset saved


@dataclass(frozen=True)
class Alert:
    severity: Severity
    code: str
    message: str
    ts: float


class AlertBus:
    """Keep recent alerts for Status; toast by severity."""

    def __init__(self, maxlen: int = 20) -> None:
        self._items: deque[Alert] = deque(maxlen=maxlen)
        self._toast: Callable[[str, str], None] | None = None
        self._last_toast_key: str | None = None
        self._last_toast_at = 0.0

    def set_toast(self, fn: Callable[[str, str], None] | None) -> None:
        self._toast = fn

    @property
    def items(self) -> list[Alert]:
        return list(self._items)

    def latest(self, severity: Severity | None = None) -> Alert | None:
        for a in reversed(self._items):
            if severity is None or a.severity == severity:
                return a
        return None

    def emit(
        self,
        severity: Severity,
        code: str,
        message: str,
        *,
        toast: bool | None = None,
    ) -> Alert:
        alert = Alert(severity=severity, code=code, message=message, ts=time.time())
        self._items.append(alert)
        level = {
            Severity.CRITICAL: logging.ERROR,
            Severity.WARN: logging.WARNING,
            Severity.INFO: logging.INFO,
        }[severity]
        log.log(level, "[%s] %s: %s", severity.value, code, message)

        do_toast = toast
        if do_toast is None:
            do_toast = severity in (Severity.CRITICAL, Severity.WARN)
        if do_toast and self._toast:
            key = f"{severity.value}:{code}"
            now = time.monotonic()
            # debounce identical toasts
            if not (key == self._last_toast_key and now - self._last_toast_at < 45):
                self._last_toast_key = key
                self._last_toast_at = now
                title = {
                    Severity.CRITICAL: "DiscordProxyTray — error",
                    Severity.WARN: "DiscordProxyTray — notice",
                    Severity.INFO: "DiscordProxyTray",
                }[severity]
                self._toast(title, message)
        return alert
