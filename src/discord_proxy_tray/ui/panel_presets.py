"""Presets tab — grouped list + sticky action bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..presets import PRESET_SOURCES, PresetSource, list_presets_by_source, resolve_preset_source
from .i18n import I18n
from .preset_widgets import PresetGroupBlock, PresetListRow, PresetNameChip
from .scroll import style_scroll_area
from .svg_icons import icon_pixmap, star_pixmap
from .widgets import InfoLine, make_section_header
from . import theme as T
from . import typography as TY

_PAD = 20
_VPAD = 14

if TYPE_CHECKING:
    from ..app import TrayApp


def _action_button(text: str = "", *, primary: bool = False, danger: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("presetAction", True)
    btn.setFont(TY.button_font())
    if primary:
        btn.setProperty("primary", True)
    if danger:
        btn.setProperty("danger", True)
    return btn


class PresetsTab(QWidget):
    _sync_finished = Signal()

    def __init__(self, app: TrayApp, i18n: I18n) -> None:
        super().__init__()
        self.app = app
        self.i18n = i18n
        self._sync_finished.connect(self._on_sync_finished)
        self._pick: tuple[str, PresetSource] | None = None
        self._last_groups_signature: tuple[tuple[str, ...], ...] | None = None
        self._group_open: dict[PresetSource, bool] = {
            "local": True,
            "remote": True,
            "shipped": False,
        }
        self._group_blocks: dict[PresetSource, PresetGroupBlock] = {}
        self._preset_rows: list[PresetListRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        style_scroll_area(self._scroll)
        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self._scroll.setWidget(scroll_content)
        self._scroll_lay = QVBoxLayout(scroll_content)
        self._scroll_lay.setContentsMargins(0, 0, 0, 0)
        self._scroll_lay.setSpacing(0)

        current_block = QWidget()
        current_lay = QVBoxLayout(current_block)
        current_lay.setContentsMargins(_PAD, _VPAD, _PAD, _VPAD)
        current_lay.setSpacing(8)
        self._current_hdr = make_section_header(self.i18n.t("sec.current"))
        current_lay.addWidget(self._current_hdr)
        current_wrap = QWidget()
        self._current_row = QHBoxLayout(current_wrap)
        self._current_row.setContentsMargins(0, 0, 0, 0)
        self._current_row.setSpacing(8)
        self._active_chip = PresetNameChip()
        self._active_tag = QLabel()
        self._active_tag.setProperty("role", "muted")
        self._active_admin_hint = InfoLine(
            self.i18n.t("preset.selectNeedAdmin"), wrap=False
        )
        self._active_admin_hint.hide()
        self._current_star = QLabel()
        self._current_star.setFixedSize(13, 13)
        self._current_star.setScaledContents(True)
        self._current_star.hide()
        self._current_fav_tag = QLabel()
        self._current_fav_tag.setProperty("role", "muted")
        self._current_fav_tag.hide()
        self._current_row.addWidget(self._active_chip)
        self._current_row.addWidget(self._active_tag)
        self._current_row.addWidget(self._active_admin_hint)
        self._current_row.addWidget(self._current_star)
        self._current_row.addWidget(self._current_fav_tag)
        self._current_row.addStretch(1)
        current_lay.addWidget(current_wrap)
        self._scroll_lay.addWidget(current_block)

        section_divider = QFrame()
        section_divider.setFrameShape(QFrame.Shape.NoFrame)
        section_divider.setFixedHeight(1)
        section_divider.setStyleSheet(
            f"background-color: {T.LINE_SOFT}; border: none;"
        )
        self._scroll_lay.addWidget(section_divider)

        all_block = QWidget()
        all_lay = QVBoxLayout(all_block)
        all_lay.setContentsMargins(_PAD, _VPAD, _PAD, _VPAD)
        all_lay.setSpacing(8)
        self._all_hdr = make_section_header(self.i18n.t("sec.all"))
        all_lay.addWidget(self._all_hdr)
        self._groups_host = QVBoxLayout()
        self._groups_host.setSpacing(6)
        all_lay.addLayout(self._groups_host)
        self._scroll_lay.addWidget(all_block)

        self._note = QLabel()
        self._note.setProperty("role", "muted")
        self._note.setWordWrap(True)
        note_wrap = QWidget()
        note_lay = QHBoxLayout(note_wrap)
        note_lay.setContentsMargins(_PAD, 8, _PAD, 8)
        note_lay.addWidget(self._note)
        self._scroll_lay.addWidget(note_wrap)
        self._scroll_lay.addStretch(1)

        root.addWidget(self._scroll, stretch=1)

        actions = QFrame()
        actions.setObjectName("presetActions")
        actions_lay = QVBoxLayout(actions)
        actions_lay.setContentsMargins(_PAD, 10, _PAD, 10)
        actions_lay.setSpacing(8)

        row_main = QHBoxLayout()
        row_main.setSpacing(8)
        self._btn_use = _action_button(primary=True)
        self._btn_use.clicked.connect(self._use_preset)
        self._btn_save = _action_button()
        self._btn_save.clicked.connect(self._save_local)
        self._btn_last = _action_button()
        self._btn_last.clicked.connect(self._set_last)
        self._btn_delete = _action_button(danger=True)
        self._btn_delete.clicked.connect(self._delete_local)
        self._btn_delete.hide()
        for btn in (self._btn_use, self._btn_save, self._btn_last, self._btn_delete):
            row_main.addWidget(btn)
        row_main.addStretch(1)

        row_sync = QHBoxLayout()
        row_sync.setSpacing(8)
        self._btn_sync = _action_button()
        self._btn_sync.clicked.connect(self._check_updates)
        self._btn_hint = _action_button()
        self._btn_hint.clicked.connect(self.app.suggest_from_discord_logs)
        row_sync.addWidget(self._btn_sync)
        row_sync.addWidget(self._btn_hint)
        row_sync.addStretch(1)

        actions_lay.addLayout(row_main)
        actions_lay.addLayout(row_sync)
        root.addWidget(actions)

        from .svg_icons import icon_button

        icon_button(self._btn_use, "circle-dot", 12, color=T.ACCENT_INK)
        icon_button(self._btn_save, "save", 12, color=T.MUTED)
        icon_button(self._btn_last, "star", 12, color=T.STREAM)
        icon_button(self._btn_delete, "trash-2", 12, color=T.DANGER)
        icon_button(self._btn_sync, "loader-2", 12, color=T.MUTED)
        icon_button(self._btn_hint, "triangle-alert", 12, color=T.MUTED)

        self._apply_static_labels()

    def _apply_static_labels(self) -> None:
        self._current_hdr.setText(self.i18n.t("sec.current").upper())
        self._all_hdr.setText(self.i18n.t("sec.all").upper())
        self._active_tag.setText(self.i18n.t("preset.active"))
        self._active_admin_hint.setText(self.i18n.t("preset.selectNeedAdmin"))
        self._note.setText(self.i18n.t("preset.note"))
        self._btn_use.setText(self.i18n.t("preset.use"))
        self._btn_save.setText(self.i18n.t("preset.saveLocal"))
        self._btn_last.setText(self.i18n.t("preset.setLast"))
        self._btn_delete.setText(self.i18n.t("preset.deleteLocal"))
        self._btn_sync.setText(self.i18n.t("preset.checkUpdates"))
        self._btn_hint.setText(self.i18n.t("preset.strategyHint"))

    @staticmethod
    def _compute_groups_signature() -> tuple[tuple[str, ...], ...]:
        by_source = list_presets_by_source()
        return tuple(tuple(by_source.get(src, [])) for src in PRESET_SOURCES)

    def refresh(self, *, force_rebuild: bool = False) -> None:
        signature = self._compute_groups_signature()
        if force_rebuild or signature != self._last_groups_signature:
            self._rebuild_groups()
            self._last_groups_signature = signature
        self._update_current()
        self._sync_row_states()
        self._update_buttons()
        self._apply_static_labels()

    def refresh_light(self) -> None:
        self._update_current()
        self._sync_row_states()
        self._update_buttons()

    def _sync_row_states(self) -> None:
        from ..elevation import is_admin

        cfg = self.app.config
        pick = self._pick
        active_label = self.i18n.t("preset.active")
        live = is_admin() and self.app.zapret.is_running()
        for row in self._preset_rows:
            selected = pick == (row.preset_name, row.preset_src) if pick else False
            row.configure(
                selected=selected,
                is_active=live and row.preset_name == cfg.preset,
                is_favorite=row.preset_name == cfg.last_working_preset,
                active_label=active_label,
            )

    def _rebuild_groups(self) -> None:
        self.setUpdatesEnabled(False)
        try:
            while self._groups_host.count():
                item = self._groups_host.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self._group_blocks.clear()
            self._preset_rows.clear()

            by_source = list_presets_by_source()
            cfg = self.app.config

            if self._pick is None:
                src = resolve_preset_source(cfg.preset) or "shipped"
                self._pick = (cfg.preset, src)

            for src in PRESET_SOURCES:
                names = by_source.get(src, [])
                block = PresetGroupBlock(
                    src,
                    title=self.i18n.t(f"preset.group.{src}"),
                    hint=self.i18n.t(f"preset.group.{src}Hint"),
                    count=len(names),
                    open=self._group_open[src],
                )
                block.toggled.connect(lambda s=src: self._on_group_toggled(s))
                self._group_blocks[src] = block

                if not names:
                    empty = QLabel("—")
                    empty.setProperty("role", "faint")
                    block.body_layout.addWidget(empty)
                for name in names:
                    row = PresetListRow(
                        name,
                        src,
                        delete_tooltip=self.i18n.t("preset.deleteLocal"),
                        favorite_tooltip=self.i18n.t("preset.setLast"),
                    )
                    row.activated.connect(lambda r=row: self._on_row_activated(r))
                    row.star_clicked.connect(lambda r=row: self._on_row_star(r))
                    row.delete_clicked.connect(lambda r=row: self._on_row_delete(r))
                    block.body_layout.addWidget(row)
                    self._preset_rows.append(row)

                self._groups_host.addWidget(block)
        finally:
            self.setUpdatesEnabled(True)

    def _on_group_toggled(self, src: PresetSource) -> None:
        block = self._group_blocks.get(src)
        if block is None:
            return
        self._group_open[src] = block.is_open()

    def _on_row_activated(self, row: PresetListRow) -> None:
        self._pick = (row.preset_name, row.preset_src)
        self._sync_row_states()
        self._update_buttons()

    def _on_row_star(self, row: PresetListRow) -> None:
        self._pick = (row.preset_name, row.preset_src)
        if row.preset_name != self.app.config.last_working_preset:
            self.app.set_last_working_preset(row.preset_name)
        self.refresh_light()

    def _on_row_delete(self, row: PresetListRow) -> None:
        if row.preset_src != "local":
            return
        self._pick = (row.preset_name, row.preset_src)
        self.app.delete_local_preset(row.preset_name)
        self._pick = None
        self._last_groups_signature = None
        self.refresh(force_rebuild=True)

    def _update_current(self) -> None:
        from ..elevation import is_admin

        cfg = self.app.config
        if self.app.tun_blocks_ui():
            self._active_chip.setText(self.i18n.t("preset.notSelected"))
            self._active_tag.hide()
            self._active_admin_hint.setText(self.i18n.t("tun.presetsLocked"))
            self._active_admin_hint.show()
            self._current_star.hide()
            self._current_fav_tag.hide()
            return

        if cfg.is_full_proxy:
            self._active_chip.setText(self.i18n.t("preset.notSelected"))
            self._active_tag.hide()
            self._active_admin_hint.setText(self.i18n.t("strategy.fullHint"))
            self._active_admin_hint.show()
            self._current_star.hide()
            self._current_fav_tag.hide()
            return

        if not is_admin():
            self._active_chip.setText(self.i18n.t("preset.notSelected"))
            self._active_tag.hide()
            self._active_admin_hint.setText(self.i18n.t("preset.selectNeedAdmin"))
            self._active_admin_hint.show()
            self._current_star.hide()
            self._current_fav_tag.hide()
            return

        self._active_admin_hint.hide()
        live = self.app.zapret.is_running()
        self._active_chip.setText(cfg.preset)
        self._active_tag.setVisible(live)
        is_fav = cfg.last_working_preset == cfg.preset
        if is_fav and live:
            pix = star_pixmap(13, filled=True, color=T.STREAM)
            if not pix.isNull():
                self._current_star.setPixmap(pix)
            self._current_star.show()
            self._current_fav_tag.setText(self.i18n.t("preset.lastWorking"))
            self._current_fav_tag.show()
        else:
            self._current_star.hide()
            self._current_fav_tag.hide()

    def _update_buttons(self) -> None:
        from ..elevation import is_admin
        from ..presets import list_presets_by_source

        cfg = self.app.config
        pick = self._pick
        usable = self.app.presets_usable()
        local_names = set(list_presets_by_source()["local"])

        if pick is None:
            self._btn_use.setEnabled(False)
            self._btn_save.setEnabled(False)
            self._btn_last.setEnabled(False)
            self._btn_delete.hide()
            return

        name, src = pick
        is_local = src == "local"
        self._btn_use.setEnabled(usable and name != cfg.preset)
        self._btn_save.setEnabled(name not in local_names)
        self._btn_last.setEnabled(usable and name != cfg.last_working_preset)
        if is_local:
            self._btn_delete.show()
            self._btn_delete.setEnabled(True)
        else:
            self._btn_delete.hide()

    def _use_preset(self) -> None:
        if self._pick:
            self.app.set_preset(self._pick[0])

    def _save_local(self) -> None:
        if not self._pick:
            return
        from ..presets import save_preset_as_local

        try:
            save_preset_as_local(self._pick[0])
        except FileNotFoundError:
            pass
        self._last_groups_signature = None
        self.refresh(force_rebuild=True)

    def _set_last(self) -> None:
        if self._pick:
            self.app.set_last_working_preset(self._pick[0])

    def _delete_local(self) -> None:
        if self._pick and self._pick[1] == "local":
            self.app.delete_local_preset(self._pick[0])
            self._pick = None
            self._last_groups_signature = None
            self.refresh(force_rebuild=True)

    def _check_updates(self) -> None:
        self._btn_sync.setText(self.i18n.t("preset.checking"))
        self._btn_sync.setEnabled(False)

        def _run() -> None:
            try:
                self.app.sync_remote_presets(force=False, quiet=False)
            finally:
                self._sync_finished.emit()

        import threading

        threading.Thread(target=_run, name="preset-sync-ui", daemon=True).start()

    def _on_sync_finished(self) -> None:
        self._btn_sync.setText(self.i18n.t("preset.checkUpdates"))
        self._btn_sync.setEnabled(True)
        self._last_groups_signature = None
        self.refresh(force_rebuild=True)
