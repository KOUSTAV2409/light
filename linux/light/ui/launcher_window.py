"""GTK launcher window — ported from Snap/SearchView.swift + SearchBarView."""

from __future__ import annotations

import threading
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from ..configuration.configuration import Configuration
from ..metrics import UsageMetrics
from ..search.file_provider import file_search_loading_item
from ..search.openai_answer_provider import RequestCancelled
from ..search.search import SearchEngine
from ..search.search_item import SearchItem
from .layer_shell import center_on_screen as layer_center_on_screen, configure_launcher_window


class LauncherWindow(Gtk.Window):
    DEBOUNCE_MS = 250

    def __init__(
        self,
        app: Gtk.Application,
        config: Configuration,
        engine: SearchEngine,
        metrics: UsageMetrics | None = None,
    ) -> None:
        super().__init__(application=app, title="Light", type=Gtk.WindowType.TOPLEVEL)
        self._config = config
        self._engine = engine
        self._metrics = metrics or UsageMetrics(enabled=False)
        self._results: list[SearchItem] = []
        self._result_rows: list[Gtk.EventBox] = []
        self._selected_index = 0
        self._search_generation = 0
        self._search_timeout_id = 0
        self._pending_query = ""
        self._active_cancel_event: threading.Event | None = None

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(config.maximum_width, config.search_bar_height)
        self._window_mode = configure_launcher_window(self)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        css = f"""
        window {{
            background-color: {config.background_color};
        }}
        .search-shell {{
            background-color: {config.background_color};
        }}
        entry {{
            background-color: {config.background_color};
            color: {config.text_color};
            border: none;
            padding: 12px 16px;
            font-size: 18px;
        }}
        .results-panel {{
            background-color: {config.background_color};
        }}
        .results-separator {{
            background-color: rgba(248, 248, 242, 0.15);
            min-height: 1px;
        }}
        .result-row {{
            background-color: {config.background_color};
            padding: 8px 12px;
        }}
        .result-row.selected {{
            background-color: {config.selected_item_background_color};
        }}
        .answer-row {{
            background-color: {config.answer_background_color};
            padding: 12px 14px;
        }}
        .answer-row.selected {{
            background-color: {config.answer_selected_background_color};
        }}
        .answer-body {{
            font-size: 14px;
            color: {config.text_color};
        }}
        .answer-source {{
            font-size: 11px;
            color: {config.text_color};
            opacity: 0.6;
        }}
        .result-title {{
            font-size: 15px;
            font-weight: 600;
            color: {config.text_color};
        }}
        .result-subtitle {{
            font-size: 12px;
            color: {config.text_color};
            opacity: 0.75;
        }}
        .result-icon {{
            margin-right: 10px;
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

        self._results_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._results_panel.get_style_context().add_class("results-panel")
        self._results_panel.hide()

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("results-separator")
        self._results_panel.pack_start(separator, False, False, 0)

        self._results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._results_panel.pack_start(self._results_box, False, False, 0)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        shell.get_style_context().add_class("search-shell")
        shell.pack_start(self._entry, False, False, 0)
        shell.pack_start(self._results_panel, False, False, 0)
        self.add(shell)

        self.connect("key-press-event", self._on_key_pressed)

    def center_on_screen(self) -> None:
        self._resize_window()
        layer_center_on_screen(self, self._config.maximum_width)

    def _window_height(self) -> int:
        if not self._results:
            return self._config.search_bar_height
        results_height = sum(self._row_height(item) for item in self._results)
        results_height = min(
            self._config.maximum_height - self._config.search_bar_height,
            results_height,
        )
        return self._config.search_bar_height + results_height

    def _row_height(self, item: SearchItem) -> int:
        if item.is_instant_answer:
            text = item.answer_text or item.subtitle
            lines = min(5, max(2, len(text) // 75 + 1))
            return self._config.result_item_height + (lines - 1) * 22
        return self._config.result_item_height

    def _resize_window(self) -> None:
        width = self._config.maximum_width
        height = self._window_height()
        self.set_size_request(width, height)
        self.resize(width, height)

    def focus_search(self) -> None:
        self._entry.grab_focus()
        self._entry.select_region(0, -1)

    def reset(self) -> None:
        self._cancel_active_search()
        self._entry.set_text("")
        self._clear_results()

    def _cancel_active_search(self) -> None:
        if self._active_cancel_event is not None:
            self._active_cancel_event.set()
            self._active_cancel_event = None

    def _cancel_debounce(self) -> None:
        source_id = self._search_timeout_id
        self._search_timeout_id = 0
        if not source_id:
            return
        context = GLib.MainContext.default()
        if context.find_source_by_id(source_id) is not None:
            GLib.source_remove(source_id)

    def _on_text_changed(self, entry: Gtk.Entry) -> None:
        query = entry.get_text()
        self._pending_query = query
        self._cancel_debounce()
        self._cancel_active_search()

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
        query = self._pending_query.strip()
        if not query:
            return False

        self._metrics.record("search")
        self._search_generation += 1
        generation = self._search_generation
        cancel_event = threading.Event()
        self._active_cancel_event = cancel_event

        fast_results = self._engine.search_fast(query)
        if generation != self._search_generation:
            return False

        answer_item: SearchItem | None = None
        file_items: list[SearchItem] = []

        if self._engine.should_fetch_instant_answer(query):
            answer_item = SearchItem(
                title="Looking up answer…",
                subtitle="Searching the web with OpenAI…"
                if self._engine.uses_openai_answers
                else "Fetching from Wikipedia",
                is_instant_answer=True,
                is_loading=True,
                answer_text=(
                    "Searching the web with OpenAI…"
                    if self._engine.uses_openai_answers
                    else "Fetching from Wikipedia…"
                ),
                icon_name="dialog-information",
                action=lambda: None,
            )

        if self._engine.should_search_files(query):
            file_items = [file_search_loading_item()]

        self._results = self._engine.merge_results(
            fast_results, file_items, answer_item, query
        )
        self._selected_index = 0
        self._render_results()

        if answer_item is not None:
            threading.Thread(
                target=self._fetch_instant_answer_background,
                args=(generation, query, cancel_event),
                daemon=True,
            ).start()

        if file_items:
            threading.Thread(
                target=self._fetch_files_background,
                args=(generation, query, cancel_event),
                daemon=True,
            ).start()

        return False

    def _fetch_instant_answer_background(
        self,
        generation: int,
        query: str,
        cancel_event: threading.Event,
    ) -> None:
        answer_item: SearchItem | None = None

        def on_delta(text: str) -> None:
            if not cancel_event.is_set():
                GLib.idle_add(self._apply_stream_delta, generation, query, text)

        try:
            answer_item = self._engine.fetch_instant_answer_item(
                query,
                on_delta=on_delta if self._engine.uses_openai_answers else None,
                cancel_event=cancel_event,
            )
        except RequestCancelled:
            return
        except Exception as exc:
            print(f"Instant answer failed: {exc}", file=__import__("sys").stderr, flush=True)

        def apply() -> bool:
            return self._apply_instant_answer(generation, query, answer_item)

        GLib.idle_add(apply)

    def _apply_stream_delta(
        self,
        generation: int,
        query: str,
        answer_text: str,
    ) -> bool:
        if generation != self._search_generation or not self._same_query(query):
            return False

        streaming_item = SearchItem(
            title="OpenAI web answer",
            subtitle=answer_text,
            answer_text=answer_text,
            is_instant_answer=True,
            icon_name="dialog-information",
            action=lambda: None,
        )
        fast_results = self._engine.search_fast(query)
        file_items = self._current_file_items()
        self._results = self._engine.merge_results(
            fast_results,
            file_items,
            streaming_item,
            query,
        )
        self._selected_index = 0
        self._render_results()
        return False

    def _fetch_files_background(
        self,
        generation: int,
        query: str,
        cancel_event: threading.Event,
    ) -> None:
        try:
            file_results = self._engine.search_files_only(
                query,
                cancel_event=cancel_event,
            )
        except Exception:
            file_results = []
        if cancel_event.is_set():
            return

        def apply() -> bool:
            return self._apply_file_results(generation, query, file_results)

        GLib.idle_add(apply)

    def _current_answer_item(self) -> SearchItem | None:
        for item in self._results:
            if item.is_instant_answer:
                return item
        return None

    def _current_file_items(self) -> list[SearchItem]:
        """Keep completed file hits and the in-progress file-search row."""
        files = [item for item in self._results if item.path]
        if files:
            return files
        return [
            item
            for item in self._results
            if item.is_loading and not item.is_instant_answer
        ]

    def _same_query(self, query: str) -> bool:
        return query.strip() == self._pending_query.strip()

    def _apply_instant_answer(
        self,
        generation: int,
        query: str,
        answer_item: SearchItem | None,
    ) -> bool:
        if generation != self._search_generation:
            return False
        if not self._same_query(query):
            return False

        fast_results = self._engine.search_fast(query)
        file_items = self._current_file_items()
        if answer_item is None:
            existing = self._current_answer_item()
            # Keep a streamed partial/final answer if the final fetch returned empty.
            if (
                existing is not None
                and not existing.is_loading
                and (existing.answer_text or existing.subtitle)
            ):
                answer_item = existing
        self._results = self._engine.merge_results(
            fast_results, file_items, answer_item, query
        )
        self._selected_index = 0
        self._render_results()
        return False

    def _apply_file_results(
        self,
        generation: int,
        query: str,
        file_results: list[SearchItem],
    ) -> bool:
        if generation != self._search_generation:
            return False
        if not self._same_query(query):
            return False

        fast_results = self._engine.search_fast(query)
        # Preserve in-progress or completed AI row — do not drop "Looking up answer…".
        answer_item = self._current_answer_item()
        self._results = self._engine.merge_results(
            fast_results, file_results, answer_item, query
        )
        self._selected_index = min(self._selected_index, max(0, len(self._results) - 1))
        self._render_results()
        return False

    def _clear_result_rows(self) -> None:
        for row in self._result_rows:
            self._results_box.remove(row)
        self._result_rows = []

    def _clear_results(self) -> None:
        self._results = []
        self._selected_index = 0
        self._clear_result_rows()
        self._results_panel.hide()
        self._resize_window()

    def _build_result_row(self, index: int, item: SearchItem) -> Gtk.EventBox:
        row = Gtk.EventBox()
        row.set_visible_window(True)
        row.set_size_request(-1, self._row_height(item))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_top(4)
        content.set_margin_bottom(4)

        if item.is_instant_answer:
            row.get_style_context().add_class("answer-row")

            title = Gtk.Label(label=item.title, xalign=0)
            title.get_style_context().add_class("result-title")
            title.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(title, False, False, 0)

            answer = Gtk.Label(label=item.answer_text or item.subtitle, xalign=0)
            answer.get_style_context().add_class("answer-body")
            answer.set_line_wrap(True)
            answer.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            answer.set_max_width_chars(88)
            content.pack_start(answer, False, False, 0)

            domains: list[str] = []
            for url in item.source_urls:
                domain = urlparse(url).netloc.removeprefix("www.")
                if domain and domain not in domains:
                    domains.append(domain)
            source_text = " · ".join(domains[:3])
            if source_text:
                source_text = f"Sources: {source_text}  ·  Enter to open"
            else:
                source_text = "Press Enter to open source"
            source = Gtk.Label(label=source_text, xalign=0)
            source.get_style_context().add_class("answer-source")
            source.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(source, False, False, 0)
        else:
            row.get_style_context().add_class("result-row")

            title = Gtk.Label(label=item.title, xalign=0)
            title.get_style_context().add_class("result-title")
            title.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(title, False, False, 0)

            subtitle_text = item.subtitle or item.path
            if subtitle_text:
                subtitle = Gtk.Label(label=subtitle_text, xalign=0)
                subtitle.get_style_context().add_class("result-subtitle")
                subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                content.pack_start(subtitle, False, False, 0)

        if self._config.show_icons and not item.is_instant_answer:
            layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            icon = Gtk.Image.new_from_icon_name(item.icon_name, Gtk.IconSize.DIALOG)
            icon.set_pixel_size(28)
            icon.get_style_context().add_class("result-icon")
            layout.pack_start(icon, False, False, 0)
            layout.pack_start(content, True, True, 0)
            row.add(layout)
        else:
            row.add(content)
        row.connect("button-press-event", self._on_row_pressed, index)
        return row

    def _on_row_pressed(self, _widget: Gtk.EventBox, _event, index: int) -> bool:
        self._select_row(index)
        self._activate_selected()
        return True

    def _render_results(self) -> None:
        self._clear_result_rows()
        if not self._results:
            self._results_panel.hide()
            self._resize_window()
            return

        for index, item in enumerate(self._results):
            row = self._build_result_row(index, item)
            self._results_box.pack_start(row, False, False, 0)
            self._result_rows.append(row)

        self._results_panel.show()
        self._results_box.show_all()
        self._resize_window()
        self._select_row(self._selected_index)

    def _select_row(self, index: int) -> None:
        if not self._results:
            return
        index = max(0, min(index, len(self._results) - 1))
        self._selected_index = index
        for i, row in enumerate(self._result_rows):
            style = row.get_style_context()
            if i == index:
                style.add_class("selected")
            else:
                style.remove_class("selected")

    def _activate_selected(self) -> None:
        if not self._results:
            return
        item = self._results[self._selected_index]
        if item.is_loading:
            return
        self._metrics.record("activate_result")
        item.action()
        self.get_application().hide_launcher()  # type: ignore[attr-defined]

    def _on_activate(self, *_args) -> None:
        if not self._results and self._pending_query.strip():
            self._run_debounced_search()
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
