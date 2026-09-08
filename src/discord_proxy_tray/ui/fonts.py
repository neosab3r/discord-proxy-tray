"""Load bundled Inter + JetBrains Mono (fallback: Segoe UI / Consolas)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

_FONTS_ROOT = Path(__file__).resolve().parent / "assets" / "fonts"

UI_FONT_FILE = _FONTS_ROOT / "Inter" / "Inter-VariableFont_opsz,wght.ttf"
MONO_FONT_FILE = _FONTS_ROOT / "JetBrains_Mono" / "JetBrainsMono-VariableFont_wght.ttf"

_UI_FAMILY = "Segoe UI"
_MONO_FAMILY = "Consolas"
_loaded = False


def _load_family(path: Path, family_hint: str) -> str:
    if not path.is_file():
        return family_hint
    fid = QFontDatabase.addApplicationFont(str(path))
    if fid < 0:
        return family_hint
    families = QFontDatabase.applicationFontFamilies(fid)
    return families[0] if families else family_hint


def _tune_font(f: QFont) -> QFont:
    f.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return f


def ensure_fonts_loaded() -> None:
    global _loaded, _UI_FAMILY, _MONO_FAMILY
    if _loaded:
        return
    _UI_FAMILY = _load_family(UI_FONT_FILE, "Segoe UI")
    _MONO_FAMILY = _load_family(MONO_FONT_FILE, "Consolas")
    _loaded = True


def missing_font_files() -> list[str]:
    missing: list[str] = []
    if not UI_FONT_FILE.is_file():
        missing.append(str(UI_FONT_FILE.relative_to(_FONTS_ROOT)))
    if not MONO_FONT_FILE.is_file():
        missing.append(str(MONO_FONT_FILE.relative_to(_FONTS_ROOT)))
    return missing


def ui_family() -> str:
    ensure_fonts_loaded()
    return _UI_FAMILY


def mono_family() -> str:
    ensure_fonts_loaded()
    return _MONO_FAMILY


def ui_font(
    size: float,
    *,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    """Inter variable — weight axis at panel pixel size."""
    ensure_fonts_loaded()
    px = max(1, round(size))
    f = QFont(_UI_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    return _tune_font(f)


def mono_font(
    size: float,
    *,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    ensure_fonts_loaded()
    f = QFont(_MONO_FAMILY)
    f.setPixelSize(max(1, round(size)))
    f.setWeight(weight)
    return _tune_font(f)
