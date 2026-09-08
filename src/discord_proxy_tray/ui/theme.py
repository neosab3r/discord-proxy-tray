"""Design tokens (shared by QSS and widgets)."""

from __future__ import annotations

# §08 Spec — Color tokens (index.css dark theme)
BG = "#12141A"
SURFACE = "#1A1D26"
SURFACE_2 = "#22262F"
TEXT = "#E8EAED"
MUTED = "#9AA0A6"
FAINT = "#6B7280"
LINE = "#2A2E38"
LINE_SOFT = "#23262F"
HOVER = "#2A2F3B"
INSET = "#0D0F13"
ACCENT = "#4CC2A8"
ACCENT_INK = "#0B0E0C"
DANGER = "#E85D5D"
OK = "#43B675"
TCP = "#4D8FEA"
STREAM = "#E0A63E"

FONT_UI = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 11)
FONT_SECTION = ("Segoe UI", 10, "bold")

# Panel layout (mock §08 — h-9 title/footer, 640×520 shell)
WINDOW_W = 640
TITLE_BAR_H = 36
FOOTER_H = 36
SHELL_H = 520  # mock inner shell height (title + tabs + content + footer)
# Frameless: title bar is inside client — add TITLE_BAR_H so content area matches pre-migration
WINDOW_H = SHELL_H + TITLE_BAR_H
