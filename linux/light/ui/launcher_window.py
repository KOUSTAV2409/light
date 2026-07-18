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
from .theme import build_launcher_css, resolve_theme


def _title_duplicates_answer(title: str, answer: str) -> bool:
    """True when title is just the start of the answer (causes ghosted text)."""
    if not title or not answer:
        return False
    norm_title = title.rstrip(".…").strip().casefold()
    norm_answer = answer.strip().casefold()
    if not norm_title:
        return False
    if norm_answer.startswith(norm_title):
        return True
    # First sentence of answer used as title
    first = norm_answer.split(".", 1)[0].strip()
    return bool(first) and (norm_title == first or first.startswith(norm_title))


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
        self._theme = resolve_theme(config.theme)
        self._results: list[SearchItem] = []
        self._result_rows: list[Gtk.EventBox] = []
        self._selected_index = 0
        self._search_generation = 0
        self._search_timeout_id = 0
        self._pending_query = ""
        self._active_cancel_event: threading.Event | None = None
        self._css_provider = Gtk.CssProvider()

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(self._theme.width, self._theme.search_height)
        self._window_mode = configure_launcher_window(self)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.get_style_context().add_class("light-launcher")
        self._enable_rgba()
        self._apply_theme_css()

        # Floating card frame
        self._frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._frame.get_style_context().add_class("launcher-frame")

        # Search header with icon + entry
        self._header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._header.get_style_context().add_class("search-header")
        self._header.get_style_context().add_class("collapsed")

        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        search_icon.set_pixel_size(20)
        search_icon.get_style_context().add_class("search-icon")
        self._header.pack_start(search_icon, False, False, 0)

        self._entry = Gtk.Entry()
        self._entry.get_style_context().add_class("search-entry")
        self._entry.set_placeholder_text("Search apps, files, commands, or ask…")
        self._entry.set_has_frame(False)
        self._entry.connect("changed", self._on_text_changed)
        self._entry.connect("activate", self._on_activate)
        self._header.pack_start(self._entry, True, True, 0)

        self._results_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._results_panel.get_style_context().add_class("results-panel")
        self._results_panel.hide()

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("results-separator")
        self._results_panel.pack_start(separator, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.NONE)
        scrolled.set_propagate_natural_height(True)
        self._results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.add(self._results_box)
        self._results_panel.pack_start(scrolled, False, False, 0)

        self._footer = Gtk.Label(
            label="↑↓ navigate   ⏎ open   esc hide",
            xalign=0,
        )
        self._footer.get_style_context().add_class("footer-hint")
        if config.show_keyboard_hints:
            self._results_panel.pack_start(self._footer, False, False, 0)

        self._frame.pack_start(self._header, False, False, 0)
        self._frame.pack_start(self._results_panel, False, False, 0)

        # Outer transparent padding so the rounded card can cast a visual gap
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.pack_start(self._frame, True, True, 0)
        self.add(outer)

        self.connect("key-press-event", self._on_key_pressed)

    def _enable_rgba(self) -> None:
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)

    def _apply_theme_css(self) -> None:
        css = build_launcher_css(self._theme)
        self._css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def apply_config(self, config: Configuration) -> None:
        """Refresh theme/layout tokens after Preferences save."""
        self._config = config
        self._theme = resolve_theme(config.theme)
        self._apply_theme_css()
        self.set_default_size(self._theme.width, self._theme.search_height)
        if config.show_keyboard_hints:
            self._footer.show()
        else:
            self._footer.hide()
        self._resize_window()
        self._render_results()

    def center_on_screen(self) -> None:
        self._resize_window()
        layer_center_on_screen(self, self._theme.width + 16)

    def _window_height(self) -> int:
        chrome = 16  # outer margins
        search_h = self._theme.search_height
        if not self._results:
            return search_h + chrome
        results_height = sum(self._row_height(item) for item in self._results[:12])
        footer = 26 if self._config.show_keyboard_hints else 0
        separator = 8
        panel = min(
            self._config.maximum_height - search_h,
            results_height + footer + separator,
        )
        return search_h + panel + chrome

    def _row_height(self, item: SearchItem) -> int:
        if item.is_instant_answer:
            text = (item.answer_text or item.subtitle or "").strip()
            # Title is only a short label now; size mainly from wrapped body.
            approx_chars = max(1, self._theme.width // 9)
            lines = min(5, max(1, (len(text) + approx_chars - 1) // approx_chars))
            return 52 + lines * 17
        return self._theme.result_height

    def _resize_window(self) -> None:
        width = self._theme.width
        height = self._window_height()
        # Clear prior minimum so shrinking after fewer results works.
        self.set_size_request(-1, -1)
        self.resize(width, height)
        self.set_size_request(width, height)

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
            from ..search.currency_provider import looks_like_currency_query

            if looks_like_currency_query(query):
                loading_subtitle = "Fetching live exchange rate…"
            elif self._engine.uses_openai_answers:
                loading_subtitle = "Searching the web with OpenAI…"
            else:
                loading_subtitle = "Fetching from Wikipedia…"
            answer_item = SearchItem(
                title="Looking up answer…",
                subtitle=loading_subtitle,
                is_instant_answer=True,
                is_loading=True,
                answer_text=loading_subtitle,
                icon_name="accessories-calculator"
                if looks_like_currency_query(query)
                else "dialog-information",
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
            row.destroy()
        self._result_rows = []

    def _clear_results(self) -> None:
        self._results = []
        self._selected_index = 0
        self._clear_result_rows()
        self._results_panel.hide()
        self._header.get_style_context().add_class("collapsed")
        self._resize_window()

    def _build_result_row(self, index: int, item: SearchItem) -> Gtk.EventBox:
        row = Gtk.EventBox()
        row.set_visible_window(True)

        if item.is_instant_answer:
            row.get_style_context().add_class("answer-row")
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            content.get_style_context().add_class("answer-inner")

            answer_text = (item.answer_text or item.subtitle or "").strip()
            # Avoid ghosting: OpenAI titles are often the first sentence of the body.
            title_text = (item.title or "").strip()
            show_title = bool(title_text) and not _title_duplicates_answer(
                title_text, answer_text
            )
            if show_title:
                title = Gtk.Label(label=title_text, xalign=0)
                title.get_style_context().add_class("result-title")
                title.set_ellipsize(Pango.EllipsizeMode.END)
                content.pack_start(title, False, False, 0)
            elif item.is_loading:
                title = Gtk.Label(label=title_text or "Looking up answer…", xalign=0)
                title.get_style_context().add_class("result-title")
                title.set_ellipsize(Pango.EllipsizeMode.END)
                content.pack_start(title, False, False, 0)

            if answer_text:
                answer = Gtk.Label(label=answer_text, xalign=0)
                answer.get_style_context().add_class("answer-body")
                answer.set_line_wrap(True)
                answer.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                answer.set_max_width_chars(68)
                content.pack_start(answer, False, False, 0)

            if item.is_loading:
                source_text = "Working…"
            elif item.source_urls:
                domains: list[str] = []
                for url in item.source_urls:
                    domain = urlparse(url).netloc.removeprefix("www.")
                    if domain and domain not in domains:
                        domains.append(domain)
                source_text = (
                    f"Sources · {' · '.join(domains[:3])} · ⏎ open"
                    if domains
                    else "⏎ open source"
                )
            else:
                source_text = "⏎ copy / open"
            source = Gtk.Label(label=source_text, xalign=0)
            source.get_style_context().add_class("answer-source")
            source.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(source, False, False, 0)
            row.add(content)
        else:
            row.get_style_context().add_class("result-row")
            row.set_size_request(-1, self._theme.result_height)
            layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            layout.get_style_context().add_class("result-inner")
            layout.set_valign(Gtk.Align.CENTER)

            if self._config.show_icons:
                icon = Gtk.Image.new_from_icon_name(item.icon_name, Gtk.IconSize.DND)
                icon.set_pixel_size(24)
                icon.set_valign(Gtk.Align.CENTER)
                icon.get_style_context().add_class("result-icon")
                layout.pack_start(icon, False, False, 0)

            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text.set_valign(Gtk.Align.CENTER)

            title = Gtk.Label(label=item.title, xalign=0)
            title.get_style_context().add_class("result-title")
            title.set_ellipsize(Pango.EllipsizeMode.END)
            text.pack_start(title, False, False, 0)

            subtitle_text = item.subtitle or item.path
            if subtitle_text:
                subtitle = Gtk.Label(label=subtitle_text, xalign=0)
                subtitle.get_style_context().add_class("result-subtitle")
                subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                text.pack_start(subtitle, False, False, 0)

            layout.pack_start(text, True, True, 0)
            row.add(layout)

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
            self._header.get_style_context().add_class("collapsed")
            self._resize_window()
            return

        self._header.get_style_context().remove_class("collapsed")
        for index, item in enumerate(self._results):
            row = self._build_result_row(index, item)
            self._results_box.pack_start(row, False, False, 0)
            self._result_rows.append(row)

        self._results_panel.show()
        self._results_box.show_all()
        if self._config.show_keyboard_hints:
            self._footer.show()
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
