"""Simple GTK preferences dialog."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..configuration.configuration import Configuration
from ..platform.file_index import file_index_status, refresh_file_index


class PreferencesWindow(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, config: Configuration) -> None:
        super().__init__(
            title="Light Preferences",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_size(520, 420)
        self.set_border_width(12)

        content = self.get_content_area()
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        content.pack_start(grid, True, True, 0)

        row = 0
        self._openai_enabled = Gtk.CheckButton(label="Enable OpenAI live answers")
        self._openai_enabled.set_active(config.openai_enabled)
        grid.attach(self._openai_enabled, 0, row, 2, 1)
        row += 1

        self._openai_web_search = Gtk.CheckButton(label="Use web search for current answers")
        self._openai_web_search.set_active(config.openai_web_search)
        grid.attach(self._openai_web_search, 0, row, 2, 1)
        row += 1

        self._clipboard_enabled = Gtk.CheckButton(label="Enable local clipboard history")
        self._clipboard_enabled.set_active(config.clipboard_history_enabled)
        grid.attach(self._clipboard_enabled, 0, row, 2, 1)
        row += 1

        self._metrics_enabled = Gtk.CheckButton(label="Enable privacy-safe local usage metrics")
        self._metrics_enabled.set_active(config.usage_metrics_enabled)
        grid.attach(self._metrics_enabled, 0, row, 2, 1)
        row += 1

        grid.attach(Gtk.Label(label="OpenAI model", xalign=0), 0, row, 1, 1)
        self._openai_model = Gtk.Entry()
        self._openai_model.set_text(config.openai_model)
        grid.attach(self._openai_model, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Search paths (comma-separated)", xalign=0), 0, row, 1, 1)
        self._search_paths = Gtk.Entry()
        self._search_paths.set_text(", ".join(config.search_paths))
        grid.attach(self._search_paths, 1, row, 1, 1)
        row += 1

        status = file_index_status()
        index_label = Gtk.Label(
            label=f"File index: {status.backend} — {status.hint}",
            xalign=0,
            wrap=True,
        )
        grid.attach(index_label, 0, row, 2, 1)
        row += 1

        refresh_button = Gtk.Button(label="Refresh file index (may need sudo)")
        refresh_button.connect("clicked", self._on_refresh_index)
        grid.attach(refresh_button, 0, row, 2, 1)
        row += 1

        secrets_label = Gtk.Label(
            label="OpenAI API key stays in ~/.config/light/secrets.json (never saved here).",
            xalign=0,
            wrap=True,
        )
        grid.attach(secrets_label, 0, row, 2, 1)

        self.show_all()

    def _on_refresh_index(self, _button: Gtk.Button) -> None:
        ok, message = refresh_file_index()
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO if ok else Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def apply(self) -> Configuration:
        paths = [
            part.strip()
            for part in self._search_paths.get_text().split(",")
            if part.strip()
        ]
        self._config.openai_enabled = self._openai_enabled.get_active()
        self._config.openai_web_search = self._openai_web_search.get_active()
        self._config.clipboard_history_enabled = self._clipboard_enabled.get_active()
        self._config.usage_metrics_enabled = self._metrics_enabled.get_active()
        self._config.openai_model = self._openai_model.get_text().strip() or "gpt-4o"
        self._config.search_paths = paths or ["~"]
        self._config.save()
        return self._config
