"""Application controller — ported from Snap/Snap.swift + AppDelegate.swift."""

from __future__ import annotations

import sys
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    AppIndicator = None  # type: ignore[assignment]

from .clipboard.history import ClipboardHistory
from .clipboard.manager import ClipboardManager
from .configuration.configuration import Configuration
from .keyboard.hotkey import start_global_hotkey
from .metrics import UsageMetrics
from .platform.file_index import file_index_status
from .search.search import SearchEngine
from .ui.launcher_window import LauncherWindow
from .ui.preferences_window import PreferencesWindow


class LightApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="com.koustav.light",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._config = Configuration.load()
        self._clipboard_history = ClipboardHistory(
            self._config.clipboard_history_limit
        )
        self._clipboard_manager = ClipboardManager(self._clipboard_history)
        self._metrics = UsageMetrics(self._config.usage_metrics_enabled)
        self._engine = SearchEngine(
            self._config,
            clipboard_history=(
                self._clipboard_history
                if self._config.clipboard_history_enabled
                else None
            ),
            copy_text=(
                self._clipboard_manager.copy
                if self._config.clipboard_history_enabled
                else None
            ),
        )
        self._window: LauncherWindow | None = None
        self._indicator: Any | None = None
        self._started = False
        self._toggle_on_activate = False

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self._ensure_started()
        self.hold()
        print(
            "Light is running. Search bar should be visible.\n"
            "Tray: magnifying glass icon | Escape: hide | ./run.sh stop: quit",
            file=sys.stderr,
            flush=True,
        )

    def do_activate(self) -> None:
        self._ensure_started()
        if self._toggle_on_activate:
            self._toggle_on_activate = False
            self.toggle_launcher()
        else:
            self.show_launcher()

    def do_command_line(self, command_line) -> int:
        argv = list(command_line.get_arguments())
        self._toggle_on_activate = "--toggle" in argv
        self.activate()
        return 0

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._window = LauncherWindow(
            self,
            self._config,
            self._engine,
            metrics=self._metrics,
        )
        self._window.connect("delete-event", self._on_delete_event)
        self._setup_tray()
        self._setup_hotkey()
        if self._config.clipboard_history_enabled:
            self._clipboard_manager.start()
        self._metrics.record("launch")
        index_status = file_index_status()
        if not index_status.database_exists and index_status.backend != "none":
            print(f"Note: {index_status.hint}", file=sys.stderr, flush=True)
        elif index_status.backend == "none":
            print(f"Tip: {index_status.hint}", file=sys.stderr, flush=True)
        self._started = True

    def _on_delete_event(self, *_args) -> bool:
        self.hide_launcher()
        return True

    def show_launcher(self) -> None:
        if not self._started or self._window is None:
            return
        # Realize first so move/resize sticks; then pin the search bar in place.
        self._window.show_all()
        self._window.present()
        self._window.center_on_screen()
        self._window.focus_search()

    def hide_launcher(self) -> None:
        if not self._started or self._window is None:
            return
        self._window.reset()
        self._window.hide()

    def toggle_launcher(self) -> None:
        if not self._started or self._window is None:
            return
        if self._window.get_visible():
            self.hide_launcher()
        else:
            self.show_launcher()

    def show_preferences(self) -> None:
        if self._window is None:
            return
        dialog = PreferencesWindow(self._window, self._config)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._config = dialog.apply()
            self._metrics = UsageMetrics(self._config.usage_metrics_enabled)
            if self._window is not None:
                self._window.apply_config(self._config)
                self._window._metrics = self._metrics  # noqa: SLF001
            if self._config.clipboard_history_enabled:
                self._clipboard_manager.start()
            else:
                self._clipboard_manager.stop()
        dialog.destroy()

    def _setup_tray(self) -> None:
        if AppIndicator is None:
            print(
                "System tray integration is unavailable; use the global shortcut.",
                file=sys.stderr,
            )
            return
        indicator = AppIndicator.Indicator.new(
            "light-launcher",
            "system-search",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        indicator.set_title("Light")
        menu = Gtk.Menu()
        show_item = Gtk.MenuItem(label="Show Launcher")
        show_item.connect("activate", lambda *_: GLib.idle_add(self.show_launcher))
        prefs_item = Gtk.MenuItem(label="Preferences…")
        prefs_item.connect("activate", lambda *_: GLib.idle_add(self.show_preferences))
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: self.quit())
        menu.append(show_item)
        menu.append(prefs_item)
        menu.append(quit_item)
        menu.show_all()
        indicator.set_menu(menu)
        self._indicator = indicator

    def _setup_hotkey(self) -> None:
        hotkey = self._config.activation_hotkey
        thread = start_global_hotkey(hotkey, lambda: GLib.idle_add(self.toggle_launcher))
        if thread is None:
            print(
                f"Note: built-in global hotkey ({hotkey}) is unavailable.\n"
                "Use one of these instead:\n"
                "  1. Tray icon (magnifying glass in system tray)\n"
                "  2. ./run.sh toggle  (bind Alt+Space in system keyboard settings)\n"
                "  3. ./run.sh setup-hotkey  (optional pip keyboard in a venv)\n",
                file=sys.stderr,
            )


def run() -> int:
    # Second instance (e.g. ./run.sh toggle --toggle) reaches do_command_line
    # over D-Bus so the primary process can toggle visibility.
    app = LightApplication()
    return app.run(sys.argv)
