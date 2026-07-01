"""GTK launcher window — ported from Snap/SearchView.swift + SearchBarView."""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from ..configuration.configuration import Configuration
from ..search.search import SearchEngine
from ..search.search_item import SearchItem


class LauncherWindow(Gtk.Window):
    DEBOUNCE_MS = 120

    def __init__(self, app: Gtk.Application, config: Configuration, engine: SearchEngine) -> None:
        super().__init__(application=app, title="Light", type=Gtk.WindowType.TOPLEVEL)
        self._config = config
        self._engine = engine
        self._results: list[SearchItem] = []
        self._selected_index = 0
        self._search_generation = 0
        self._search_timeout_id = 0
        self._pending_query = ""

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(config.maximum_width, config.search_bar_height)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        css = f"""
        window {{
            background-color: {config.background_color};
        }}
        entry {{
            background-color: {config.background_color};
            color: {config.text_color};
            border: none;
            padding: 12px 16px;
            font-size: 18px;
        }}
        listbox {{
            background-color: {config.background_color};
            color: {config.text_color};
        }}
        listbox row {{
            padding: 8px 12px;
            border: none;
        }}
        listbox row:selected {{
            background-color: {config.selected_item_background_color};
            color: {config.text_color};
        }}
        .result-title {{
            font-size: 15px;
            font-weight: 600;
        }}
        .result-subtitle {{
            font-size: 12px;
            opacity: 0.75;
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._entry = Gtk.Entry()
        self._entry.set_placeholder_text("Search files, apps, and commands…")
        self._entry.connect("changed", self._on_text_changed)
        self._entry.connect("activate", self._on_activate)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_no_show_all(True)
        scrolled.hide()
        self._scrolled = scrolled

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        scrolled.add(self._listbox)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.pack_start(self._entry, False, False, 0)
        box.pack_start(scrolled, True, True, 0)
        self.add(box)

        self.connect("key-press-event", self._on_key_pressed)

    def center_on_screen(self) -> None:
        self.resize(self._config.maximum_width, self._config.search_bar_height)
        display = Gdk.Display.get_default()
        if display is None:
            return
        monitor = display.get_primary_monitor()
        if monitor is None:
            return
        geometry = monitor.get_geometry()
        width, height = self.get_size()
        x = geometry.x + max(0, (geometry.width - width) // 2)
        y = geometry.y + max(0, (geometry.height - height) // 4)
        self.move(x, y)

    def focus_search(self) -> None:
        self._entry.grab_focus()
        self._entry.select_region(0, -1)

    def reset(self) -> None:
        self._entry.set_text("")
        self._clear_results()

    def _on_text_changed(self, entry: Gtk.Entry) -> None:
        query = entry.get_text()
        self._pending_query = query

        if self._search_timeout_id:
            GLib.source_remove(self._search_timeout_id)

        if not query.strip():
            self._search_generation += 1
            self._clear_results()
            return

        self._search_timeout_id = GLib.timeout_add(
            self.DEBOUNCE_MS,
            self._run_debounced_search,
        )

    def _run_debounced_search(self) -> bool:
        self._search_timeout_id = 0
        query = self._pending_query
        if not query.strip():
            return False

        self._search_generation += 1
        generation = self._search_generation

        fast_results = self._engine.search_fast(query)
        if generation != self._search_generation:
            return False

        self._results = fast_results
        self._selected_index = 0
        self._render_results()

        if not self._engine.should_search_files(query):
            return False

        def search_in_background() -> None:
            file_results = self._engine.search_files_only(query)
            GLib.idle_add(
                self._apply_file_results,
                generation,
                query,
                file_results,
            )

        threading.Thread(target=search_in_background, daemon=True).start()
        return False

    def _apply_file_results(
        self,
        generation: int,
        query: str,
        file_results: list[SearchItem],
    ) -> bool:
        if generation != self._search_generation:
            return False
        if query != self._pending_query:
            return False

        fast_results = self._engine.search_fast(query)
        self._results = self._engine.merge_results(fast_results, file_results)
        self._selected_index = min(self._selected_index, max(0, len(self._results) - 1))
        self._render_results()
        return False

    def _clear_listbox(self) -> None:
        for row in self._listbox.get_children():
            self._listbox.remove(row)
        self._scrolled.hide()
        self.resize(self._config.maximum_width, self._config.search_bar_height)

    def _clear_results(self) -> None:
        self._results = []
        self._selected_index = 0
        self._clear_listbox()

    def _render_results(self) -> None:
        self._clear_listbox()
        if not self._results:
            return

        for index, item in enumerate(self._results):
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row_box.set_margin_top(4)
            row_box.set_margin_bottom(4)

            title = Gtk.Label(label=item.title, xalign=0)
            title.get_style_context().add_class("result-title")
            title.set_ellipsize(Pango.EllipsizeMode.END)
            row_box.pack_start(title, False, False, 0)

            subtitle_text = item.subtitle or item.path
            if subtitle_text:
                subtitle = Gtk.Label(label=subtitle_text, xalign=0)
                subtitle.get_style_context().add_class("result-subtitle")
                subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                row_box.pack_start(subtitle, False, False, 0)

            row.add(row_box)
            row.set_name(str(index))
            self._listbox.add(row)

        self._listbox.show_all()
        height = min(
            self._config.maximum_height,
            self._config.search_bar_height + len(self._results) * self._config.result_item_height,
        )
        self.resize(self._config.maximum_width, height)
        self._scrolled.show()
        self._select_row(self._selected_index)

    def _select_row(self, index: int) -> None:
        if not self._results:
            return
        index = max(0, min(index, len(self._results) - 1))
        self._selected_index = index
        row = self._listbox.get_row_at_index(index)
        if row:
            self._listbox.select_row(row)

    def _activate_selected(self) -> None:
        if not self._results:
            return
        item = self._results[self._selected_index]
        item.action()
        self.get_application().hide_launcher()  # type: ignore[attr-defined]

    def _on_activate(self, *_args) -> None:
        self._activate_selected()

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        index = row.get_index()
        if 0 <= index < len(self._results):
            self._selected_index = index
            self._activate_selected()

    def _on_key_pressed(self, _widget, event: Gdk.EventKey) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Escape:
            self.get_application().hide_launcher()  # type: ignore[attr-defined]
            return True
        if keyval == Gdk.KEY_Down:
            self._select_row(self._selected_index + 1)
            return True
        if keyval == Gdk.KEY_Up:
            self._select_row(self._selected_index - 1)
            return True
        if keyval == Gdk.KEY_Tab and not (event.state & Gdk.ModifierType.SHIFT_MASK):
            if self._results:
                self._entry.set_text(self._results[self._selected_index].title)
            return True
        return False
