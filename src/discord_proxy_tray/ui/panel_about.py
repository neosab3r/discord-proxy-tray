"""About tab — product info, locale, stack, links."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .i18n import I18n, Locale
from .icons import make_tray_icon
from .scroll import style_scroll_area
from .widgets import Section
from . import theme as T
from . import typography as TY

if TYPE_CHECKING:
    from ..app import TrayApp

_GITHUB = "https://github.com/neosab3r/discord-proxy-tray"
_STACK = ("PySide6", "force-proxy", "winws · zapret")

_PLAIN_LABEL = (
    "background: transparent; border: none; padding: 0; margin: 0; "
    "text-decoration: none;"
)


def _chip_style() -> str:
    return (
        f"background-color: {T.SURFACE_2}; color: {T.MUTED}; "
        f"border: 1px solid {T.LINE}; border-radius: 5px; "
        f"padding: 4px 8px; text-decoration: none;"
    )


def _locale_style(*, active: bool) -> str:
    if active:
        return (
            f"background-color: {T.ACCENT}; color: {T.ACCENT_INK}; "
            f"border: 1px solid {T.ACCENT}; border-radius: 6px; "
            f"padding: 0 12px; min-height: 28px; min-width: 44px; "
            f"text-decoration: none;"
        )
    return (
        f"background-color: {T.SURFACE_2}; color: {T.MUTED}; "
        f"border: 1px solid {T.LINE}; border-radius: 6px; "
        f"padding: 0 12px; min-height: 28px; min-width: 44px; "
        f"text-decoration: none;"
    )


class AboutTab(QWidget):
    def __init__(self, app: TrayApp, i18n: I18n) -> None:
        super().__init__()
        self.app = app
        self.i18n = i18n

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        style_scroll_area(scroll)
        content = QWidget()
        scroll.setWidget(content)
        self._lay = QVBoxLayout(content)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        outer.addWidget(scroll)

        self._sec_product = Section("Discord Proxy Tray")
        product_row = QHBoxLayout()
        product_row.setSpacing(12)
        self._tray_icon = QLabel()
        self._tray_icon.setFixedSize(34, 34)
        self._tray_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tray_icon.setStyleSheet(_PLAIN_LABEL)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._version = QLabel()
        self._version.setFont(TY.setting_font())
        self._version.setStyleSheet(f"color: {T.TEXT}; {_PLAIN_LABEL}")
        self._packs = QLabel()
        self._packs.setWordWrap(True)
        self._packs.setFont(TY.body_font())
        self._packs.setStyleSheet(f"color: {T.MUTED}; {_PLAIN_LABEL}")
        self._blurb = QLabel()
        self._blurb.setWordWrap(True)
        self._blurb.setFont(TY.body_font())
        self._blurb.setStyleSheet(f"color: {T.MUTED}; {_PLAIN_LABEL}")
        text_col.addWidget(self._version)
        text_col.addWidget(self._packs)
        text_col.addWidget(self._blurb)
        product_row.addWidget(self._tray_icon, alignment=Qt.AlignmentFlag.AlignTop)
        product_row.addLayout(text_col, stretch=1)
        self._sec_product.body.addLayout(product_row)
        self._lay.addWidget(self._sec_product)

        self._sec_lang = Section(self.i18n.t("about.language"))
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._locale_group = QButtonGroup(self)
        self._locale_btns: dict[Locale, QPushButton] = {}
        for code in ("en", "ru"):
            btn = QPushButton(code.upper())
            btn.setProperty("localeBtn", True)
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setFont(TY.mono_md_font(weight=TY.SEMI_WEIGHT))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _=False, c=code: self._on_locale(c))
            self._locale_group.addButton(btn)
            self._locale_btns[code] = btn
            lang_row.addWidget(btn)
        self._lang_hint = QLabel()
        self._lang_hint.setFont(TY.body_font())
        self._lang_hint.setStyleSheet(f"color: {T.MUTED}; {_PLAIN_LABEL}")
        lang_row.addWidget(self._lang_hint, stretch=1)
        self._sec_lang.body.addLayout(lang_row)
        self._lay.addWidget(self._sec_lang)

        self._sec_stack = Section(self.i18n.t("about.stack"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self._stack_labels: list[QLabel] = []
        for name in _STACK:
            chip = QLabel(name)
            chip.setFont(TY.ui_sm_font())
            chip.setStyleSheet(_chip_style())
            self._stack_labels.append(chip)
            chips.addWidget(chip)
        chips.addStretch(1)
        self._sec_stack.body.addLayout(chips)
        self._lay.addWidget(self._sec_stack)

        self._sec_links = Section(self.i18n.t("about.links"))
        links_col = QVBoxLayout()
        links_col.setSpacing(6)
        self._github = QPushButton()
        self._github.setFlat(True)
        self._github.setProperty("linkBtn", True)
        self._github.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._github.setCursor(Qt.CursorShape.PointingHandCursor)
        self._github.setStyleSheet(
            f"background: transparent; border: none; color: {T.TCP}; "
            f"text-align: left; padding: 0; text-decoration: none;"
        )
        self._github.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(_GITHUB))
        )
        self._licenses = QLabel()
        self._licenses.setWordWrap(True)
        self._licenses.setFont(TY.ui_sm_font())
        self._licenses.setStyleSheet(f"color: {T.MUTED}; {_PLAIN_LABEL}")
        links_col.addWidget(self._github, alignment=Qt.AlignmentFlag.AlignLeft)
        links_col.addWidget(self._licenses)
        self._sec_links.body.addLayout(links_col)
        self._lay.addWidget(self._sec_links)

        self._sec_tools = Section(self.i18n.t("about.tools"), last=True)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        self._remove_dll_btn = QPushButton()
        self._remove_dll_btn.setProperty("toolbarBtn", True)
        self._remove_dll_btn.setFont(TY.button_font())
        self._remove_dll_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_dll_btn.clicked.connect(self._on_remove_dll)
        tools_row.addWidget(self._remove_dll_btn)
        tools_row.addStretch(1)
        self._sec_tools.body.addLayout(tools_row)
        self._lay.addWidget(self._sec_tools)
        self._lay.addStretch(1)

        self.refresh()

    def _on_remove_dll(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            self.i18n.t("about.removeDllConfirmTitle"),
            self.i18n.t("about.removeDllConfirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._remove_dll_btn.setEnabled(False)
        try:
            self.app.uninstall_all_dlls()
        finally:
            self._remove_dll_btn.setEnabled(True)
            self.refresh()

    def _on_locale(self, code: str) -> None:
        loc: Locale = "ru" if code == "ru" else "en"
        if self.i18n.locale == loc:
            return
        self.app.set_locale(loc)

    def _style_locale_buttons(self) -> None:
        for code, btn in self._locale_btns.items():
            active = self.i18n.locale == code
            btn.setStyleSheet(_locale_style(active=active))

    def apply_locale(self) -> None:
        self._sec_lang.set_title(self.i18n.t("about.language"))
        self._sec_stack.set_title(self.i18n.t("about.stack"))
        self._sec_links.set_title(self.i18n.t("about.links"))
        self._sec_tools.set_title(self.i18n.t("about.tools"))
        self.refresh()

    def refresh(self) -> None:
        from ..presets import preset_pack_version

        stream_on = self.app.stream_toggle_display()
        pix = make_tray_icon(self.app.config.tcp_proxy, stream_on).pixmap(34, 34)
        self._tray_icon.setPixmap(pix)
        self._version.setText(f"{self.i18n.t('about.version')} {__version__}")
        pack = preset_pack_version()
        zapret = self.app.updater.local_display()
        self._packs.setText(
            f"{self.i18n.t('about.presetPack')}: {pack}\n"
            f"{self.i18n.t('about.zapretCore')}: {zapret}"
        )
        self._blurb.setText(self.i18n.t("about.blurb"))
        self._lang_hint.setText(self.i18n.t("about.languageHint"))
        for code, btn in self._locale_btns.items():
            btn.blockSignals(True)
            btn.setChecked(self.i18n.locale == code)
            btn.blockSignals(False)
        self._style_locale_buttons()
        for chip in self._stack_labels:
            chip.setStyleSheet(_chip_style())
        self._github.setText("github.com/neosab3r/discord-proxy-tray")
        self._licenses.setText(self.i18n.t("about.licenses"))
        self._remove_dll_btn.setText(self.i18n.t("about.removeDll"))
