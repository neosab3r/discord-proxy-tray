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
        # Tooltip shows CRITICAL until user acks (Status → Dismiss).
        self._critical_ack_ts = 0.0
        # WARN toast at most once per code per process lifetime (unless toast=True forced).
        self._warn_toasted: set[str] = set()

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

    def pending_critical(self) -> Alert | None:
        """Latest CRITICAL that has not been dismissed."""
        a = self.latest(Severity.CRITICAL)
        if a is not None and a.ts > self._critical_ack_ts:
            return a
        return None

    def ack_critical(self) -> bool:
        """Dismiss sticky CRITICAL from tray tooltip. Returns True if something was pending."""
        a = self.pending_critical()
        if a is None:
            return False
        self._critical_ack_ts = time.time()
        return True

    def clear_code(self, code: str) -> int:
        """Remove alerts with this code (e.g. resolved socks_down). Returns count removed."""
        before = len(self._items)
        kept = [a for a in self._items if a.code != code]
        self._items.clear()
        self._items.extend(kept)
        return before - len(self._items)

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
            if severity == Severity.CRITICAL:
                do_toast = True
            elif severity == Severity.WARN:
                if code in self._warn_toasted:
                    do_toast = False
                else:
                    self._warn_toasted.add(code)
                    do_toast = True
            else:
                do_toast = False
        elif severity == Severity.WARN and do_toast:
            self._warn_toasted.add(code)

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
