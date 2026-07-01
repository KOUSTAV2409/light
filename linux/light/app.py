"""Application controller — ported from Snap/Snap.swift + AppDelegate.swift."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import GLib, Gtk

from .configuration.configuration import Configuration
from .keyboard.hotkey import start_global_hotkey
from .search.search import SearchEngine
from .ui.launcher_window import LauncherWindow


class LightApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.koustav.light")
        self._config = Configuration.load()
        self._engine = SearchEngine(self._config)
        self._window: LauncherWindow | None = None
        self._indicator: AppIndicator.Indicator | None = None
        self._started = False

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
        self.show_launcher()

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._window = LauncherWindow(self, self._config, self._engine)
        self._window.connect("delete-event", self._on_delete_event)
        self._setup_tray()
        self._setup_hotkey()
        self._started = True

    def _on_delete_event(self, *_args) -> bool:
        self.hide_launcher()
        return True

    def show_launcher(self) -> None:
        if not self._started or self._window is None:
            return
        self._window.center_on_screen()
        self._window.show_all()
        self._window.present()
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

    def _setup_tray(self) -> None:
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
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: self.quit())
        menu.append(show_item)
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
    # Second instance (e.g. ./run.sh toggle) activates the running app via D-Bus.
    argv = [arg for arg in sys.argv if arg != "--toggle"]
    app = LightApplication()
    return app.run(argv)
