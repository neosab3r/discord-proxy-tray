"""Qt Fusion dark theme + QSS from design tokens."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from . import theme as T
from .fonts import mono_family, ui_family


def apply_application_theme(app: QApplication) -> None:
    from .fonts import ensure_fonts_loaded

    ensure_fonts_loaded()
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(T.BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(T.TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(T.INSET))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(T.SURFACE))
    palette.setColor(QPalette.ColorRole.Text, QColor(T.TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(T.SURFACE_2))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(T.TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(T.SURFACE))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(T.TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(T.MUTED))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(T.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(T.ACCENT_INK))
    palette.setColor(QPalette.ColorRole.Link, QColor(T.TCP))

    app.setPalette(palette)
    app.setStyleSheet(application_stylesheet())


def application_stylesheet() -> str:
    ui = ui_family()
    mono = mono_family()
    return f"""
* {{
    outline: none;
}}
QWidget {{
    color: {T.TEXT};
    font-family: "{ui}";
    font-size: 12px;
    background-color: {T.BG};
}}
QMainWindow {{
    background-color: {T.BG};
}}
QWidget#panelRoot {{
    background-color: {T.SURFACE};
    border: 1px solid {T.LINE};
}}
QWidget#panelBody,
QWidget#tabOuter {{
    background-color: {T.SURFACE};
}}
QWidget#panelRoot > QWidget,
QWidget#panelRoot QStackedWidget,
QWidget#panelRoot QScrollArea,
QWidget#panelRoot QScrollArea > QWidget > QWidget {{
    background-color: {T.SURFACE};
}}
QWidget#panelRoot QScrollArea > QWidget > QWidget > QWidget {{
    background-color: transparent;
}}
QWidget#panelRoot QLabel {{
    background: transparent;
}}
QStackedWidget {{
    background-color: {T.SURFACE};
    border: none;
}}
QFrame#tabStrip {{
    background-color: {T.SURFACE_2};
    border-radius: 8px;
}}
QPushButton[tabButton="true"] {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {T.MUTED};
    min-height: 28px;
    padding: 0 8px;
    font-weight: 500;
}}
QPushButton[tabButton="true"]:hover:!checked {{
    color: {T.TEXT};
}}
QPushButton[tabButton="true"]:checked {{
    background-color: {T.SURFACE};
    color: {T.TEXT};
}}
QScrollArea {{
    border: none;
    background-color: {T.SURFACE};
}}
QScrollArea > QWidget > QWidget {{
    background-color: {T.SURFACE};
}}
QAbstractScrollArea::viewport {{
    background-color: {T.SURFACE};
}}
QFrame#footer {{
    background-color: {T.SURFACE};
    border-top: 1px solid {T.LINE};
    border-radius: 0;
    min-height: {T.FOOTER_H}px;
    max-height: {T.FOOTER_H}px;
}}
QFrame#footer QLabel {{
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}}
QPushButton#footerLink {{
    background: transparent;
    border: none;
    border-radius: 4px;
    color: {T.MUTED};
    min-height: 24px;
    padding: 2px 6px;
}}
QPushButton#footerLink:hover {{
    color: {T.TEXT};
    background: rgba(42, 49, 64, 0.35);
}}
QLabel#infoIcon {{
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}}
QScrollBar:vertical {{
    width: 8px;
    margin: 2px 0;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    background: {T.LINE};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T.HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    height: 8px;
    margin: 0 2px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: {T.LINE};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QFrame#card {{
    background-color: {T.SURFACE_2};
    border: 1px solid {T.LINE};
    border-radius: 8px;
}}
QFrame#titleBar {{
    background-color: {T.SURFACE};
    border: none;
    border-bottom: 1px solid {T.LINE};
    min-height: {T.TITLE_BAR_H}px;
    max-height: {T.TITLE_BAR_H}px;
}}
QFrame#titleBar QLabel {{
    background: transparent;
    border: none;
}}
QPushButton[winBtn="min"] {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 0;
    min-width: 36px;
    min-height: 28px;
}}
QPushButton[winBtn="min"]:hover {{
    background-color: {T.HOVER};
}}
QPushButton[winBtn="close"] {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 0;
    min-width: 36px;
    min-height: 28px;
}}
QPushButton[winBtn="close"]:hover {{
    background-color: #e81123;
}}
QFrame#statusCard {{
    background-color: rgba(34, 38, 47, 0.5);
    border: 1px solid {T.LINE};
    border-radius: 8px;
}}
QPlainTextEdit#rawStatus {{
    background-color: {T.INSET};
    border: 1px solid {T.LINE};
    border-radius: 6px;
    color: {T.MUTED};
    font-family: "{mono}";
    font-size: 10.5px;
    padding: 10px;
    line-height: 1.65;
}}
QTextEdit#logView {{
    background-color: {T.INSET};
    border: 1px solid {T.LINE};
    border-radius: 6px;
    color: {T.MUTED};
    font-family: "{mono}";
    font-size: 10.5px;
    padding: 10px;
}}
QPushButton[toolbarBtn="true"] {{
    min-height: 28px;
    padding: 4px 12px;
    font-size: 12px;
}}
QPushButton[localeBtn="true"] {{
    min-height: 28px;
    min-width: 44px;
    padding: 0 12px;
    font-size: 11px;
    background-color: {T.SURFACE_2};
    border: 1px solid {T.LINE};
    color: {T.MUTED};
    text-decoration: none;
}}
QPushButton[localeBtn="true"]:checked {{
    background-color: {T.ACCENT};
    color: {T.ACCENT_INK};
    border: 1px solid {T.ACCENT};
}}
QWidget#panelRoot QLabel[role="stackChip"] {{
    background-color: {T.SURFACE_2};
    color: {T.MUTED};
    border: 1px solid {T.LINE};
    border-radius: 5px;
    padding: 4px 8px;
    font-family: "{mono}";
    font-size: 10.5px;
    text-decoration: none;
}}
QPushButton[linkBtn="true"] {{
    background: transparent;
    border: none;
    color: {T.TCP};
    text-align: left;
    padding: 0;
    min-height: 20px;
    text-decoration: none;
}}
QPushButton[linkBtn="true"]:hover {{
    text-decoration: underline;
}}
QFrame#presetActions {{
    background-color: {T.SURFACE};
    border-top: 1px solid {T.LINE};
    border-radius: 0;
    margin: 0;
    padding: 0;
}}
QWidget#presetListRow {{
    background-color: transparent;
    border-radius: 6px;
}}
QWidget#presetListRow QLabel {{
    background: transparent;
    border: none;
}}
QPushButton[presetAction="true"] {{
    min-height: 28px;
    max-height: 28px;
    padding: 0 12px;
    font-size: 12px;
}}
QPushButton[presetAction="true"][danger="true"] {{
    background-color: transparent;
    border: 1px solid rgba(232, 93, 93, 0.6);
    color: {T.DANGER};
}}
QPushButton[presetAction="true"][danger="true"]:hover:enabled {{
    background-color: rgba(232, 93, 93, 0.1);
}}
QFrame#groupBlock {{
    background-color: rgba(26, 29, 38, 0.4);
    border: 1px solid {T.LINE_SOFT};
    border-radius: 7px;
}}
QFrame#groupDivider {{
    background-color: {T.LINE_SOFT};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QFrame#presetNameChip {{
    background-color: {T.SURFACE_2};
    border: 1px solid {T.LINE};
    border-radius: 6px;
}}
QFrame#presetNameChip QLabel {{
    background: transparent;
    border: none;
}}
QLabel[role="section"] {{
    color: {T.FAINT};
    letter-spacing: 1.6px;
    background: transparent;
    border: none;
}}
QLabel[role="setting"] {{
    color: {T.TEXT};
    background: transparent;
    border: none;
    text-decoration: none;
}}
QLabel[role="label"] {{
    color: {T.TEXT};
    background: transparent;
    border: none;
    text-decoration: none;
}}
QLabel[role="muted"] {{
    color: {T.MUTED};
    background: transparent;
    border: none;
    text-decoration: none;
}}
QLabel[role="faint"] {{
    color: {T.FAINT};
    background: transparent;
    border: none;
    text-decoration: none;
}}
QLabel[role="faint-sm"] {{
    color: {T.FAINT};
    background: transparent;
    border: none;
    text-decoration: none;
    padding: 0;
    margin: 0;
}}
QLabel[role="mono"] {{
    font-family: "{mono}";
    font-size: 11px;
    background: transparent;
}}
QLabel[role="chip"] {{
    background-color: {T.SURFACE_2};
    color: {T.ACCENT};
    padding: 4px 8px;
    border-radius: 6px;
    font-family: "{mono}";
    font-size: 10.5px;
}}
QLabel[role="hint-warn"] {{
    color: {T.STREAM};
    font-size: 10px;
    background: transparent;
}}
QLabel[role="row-label"] {{
    color: {T.FAINT};
    font-family: "{mono}";
    font-size: 10px;
    min-width: 64px;
    background: transparent;
}}
QLineEdit {{
    background-color: {T.INSET};
    border: 1px solid {T.LINE};
    border-radius: 6px;
    padding: 4px 8px;
    color: {T.TEXT};
    font-family: "{mono}";
    font-size: 11.5px;
}}
QPushButton {{
    background-color: {T.SURFACE_2};
    border: 1px solid {T.LINE};
    border-radius: 6px;
    padding: 4px 12px;
    color: {T.TEXT};
    min-height: 28px;
}}
QPushButton:hover:enabled {{
    background-color: {T.HOVER};
}}
QPushButton:disabled {{
    color: {T.FAINT};
}}
QPushButton[primary="true"] {{
    background-color: {T.ACCENT};
    color: {T.ACCENT_INK};
    border: none;
}}
QPushButton[primary="true"]:hover:enabled {{
    background-color: #5fd4ba;
}}
QPushButton[primary="true"]:disabled {{
    background-color: {T.SURFACE_2};
    color: {T.FAINT};
    border: 1px solid {T.LINE};
}}
QPushButton[presetAction="true"][primary="true"]:disabled {{
    background-color: {T.SURFACE_2};
    color: {T.FAINT};
    border: 1px solid {T.LINE};
}}
QPushButton[filter="true"] {{
    min-height: 24px;
    padding: 2px 8px;
    font-size: 11px;
}}
QPushButton[filter="true"]:checked {{
    background-color: rgba(76, 194, 168, 0.12);
    border-color: rgba(76, 194, 168, 0.6);
    color: {T.ACCENT};
}}
QPushButton[groupHeader="true"] {{
    text-align: left;
    border: none;
    border-radius: 0;
    background: transparent;
    min-height: 32px;
    padding: 0;
}}
QPushButton[groupHeader="true"]:hover {{
    background-color: rgba(34, 38, 51, 0.5);
}}
QPushButton[presetRow="true"] {{
    text-align: left;
    border: none;
    background: transparent;
    min-height: 36px;
    padding: 4px 8px;
    font-family: Consolas;
}}
QPushButton[presetRow="true"]:checked {{
    background-color: {T.SURFACE_2};
}}
QTextEdit, QPlainTextEdit {{
    background-color: {T.INSET};
    border: 1px solid {T.LINE};
    border-radius: 8px;
    color: {T.MUTED};
    font-family: "{mono}";
    font-size: 10px;
    padding: 8px;
}}
QRadioButton {{
    spacing: 6px;
    background: transparent;
}}
"""
