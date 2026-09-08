"""Typography scale from design mock (panel.tsx + brief §3)."""

from __future__ import annotations

from PySide6.QtGui import QFont

from .fonts import mono_font, ui_font

# section overlines — mono caps
SECTION_PT = 9.5
SECTION_WEIGHT = QFont.Weight.Medium
SECTION_TRACKING = "1.6px"  # tracking-[0.16em] ≈ 1.6px at 9.5–10px

# Inter variable @ panel px — wght 900 renders ~semi vs browser; used as mock semi
SEMI_WEIGHT = QFont.Weight.Black

# primary setting labels (TCP proxy, Stream desync, …)
SETTING_PT = 13
SETTING_WEIGHT = SEMI_WEIGHT

# secondary labels (autostart — mock is 13 regular)
LABEL_PT = 13

# muted body / info lines
BODY_PT = 11

# faint meta (footer, preset bar hint)
FAINT_PT = 10
FAINT_SM_PT = 9.5

# tabs, buttons, status values
UI_PT = 12
UI_SM_PT = 10.5

# mono fields & preset names
MONO_PT = 11
MONO_LG_PT = 11.5
MONO_SM_PT = 10
MONO_XS_PT = 9


def section_font() -> QFont:
    return mono_font(SECTION_PT, weight=SECTION_WEIGHT)


def setting_font() -> QFont:
    return ui_font(SETTING_PT, weight=SETTING_WEIGHT)


def label_font() -> QFont:
    return ui_font(LABEL_PT)


def body_font() -> QFont:
    return ui_font(BODY_PT)


def button_font() -> QFont:
    return ui_font(UI_PT, weight=SEMI_WEIGHT)


def faint_font(*, mono: bool = False) -> QFont:
    if mono:
        return mono_font(FAINT_PT)
    return ui_font(FAINT_PT)


def faint_sm_font(
    *,
    mono: bool = False,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    if mono:
        return mono_font(FAINT_SM_PT, weight=weight)
    return ui_font(FAINT_SM_PT, weight=weight)


def ui_sm_font(*, weight: QFont.Weight = QFont.Weight.Medium) -> QFont:
    return ui_font(UI_SM_PT, weight=weight)


def mono_lg_font(*, weight: QFont.Weight = SEMI_WEIGHT) -> QFont:
    return mono_font(MONO_LG_PT, weight=weight)


def mono_md_font(*, weight: QFont.Weight = SEMI_WEIGHT) -> QFont:
    return mono_font(MONO_PT, weight=weight)


def mono_sm_font(*, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return mono_font(MONO_SM_PT, weight=weight)


# preset list row names
MONO_ROW_PT = 12


def mono_row_font(*, weight: QFont.Weight = SEMI_WEIGHT) -> QFont:
    return mono_font(MONO_ROW_PT, weight=weight)


def mono_xs_font(*, weight: QFont.Weight = QFont.Weight.Medium) -> QFont:
    return mono_font(MONO_XS_PT, weight=weight)
