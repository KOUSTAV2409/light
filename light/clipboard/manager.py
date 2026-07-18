"""GTK clipboard listener with local persistence."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from .history import ClipboardHistory


class ClipboardManager:
    def __init__(self, history: ClipboardHistory) -> None:
        self.history = history
        self._clipboard: Gtk.Clipboard | None = None
        self._handler_id: int | None = None

    def start(self) -> bool:
        display = Gdk.Display.get_default()
        if display is None:
            return False
        self._clipboard = Gtk.Clipboard.get_default(display)
        self._handler_id = self._clipboard.connect("owner-change", self._on_owner_change)
        return True

    def stop(self) -> None:
        if self._clipboard is not None and self._handler_id is not None:
            self._clipboard.disconnect(self._handler_id)
        self._handler_id = None
        self._clipboard = None

    def copy(self, text: str) -> None:
        if self._clipboard is None:
            display = Gdk.Display.get_default()
            if display is None:
                return
            self._clipboard = Gtk.Clipboard.get_default(display)
        self._clipboard.set_text(text, -1)
        self._clipboard.store()

    def _on_owner_change(self, clipboard: Gtk.Clipboard, _event) -> None:
        clipboard.request_text(self._on_text_received)

    def _on_text_received(self, _clipboard: Gtk.Clipboard, text: str | None) -> None:
        if text:
            self.history.add(text)
