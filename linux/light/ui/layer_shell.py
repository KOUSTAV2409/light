"""Optional Wayland overlay support via gtk-layer-shell."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

_LAYER_SHELL_AVAILABLE = False

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell

    _LAYER_SHELL_AVAILABLE = True
except (ValueError, ImportError):
    GtkLayerShell = None  # type: ignore[assignment,misc]


def layer_shell_available() -> bool:
    return _LAYER_SHELL_AVAILABLE


def is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def configure_launcher_window(window: Gtk.Window) -> str:
    """Apply layer-shell when available; otherwise keep the GTK fallback."""
    if not _LAYER_SHELL_AVAILABLE or not is_wayland() or GtkLayerShell is None:
        window.set_keep_above(True)
        return "gtk-fallback"

    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.LEFT, True)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, True)
    GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.ON_DEMAND)
    GtkLayerShell.set_namespace(window, "light-launcher")
    return "layer-shell"


def center_on_screen(window: Gtk.Window, width: int, top_ratio: float = 0.22) -> None:
    """Place the launcher with its top (search bar) at a fixed screen fraction.

    Results grow downward. Do not re-center using the full window height — that
    pulls the search bar upward as the result list expands.
    """
    display = Gdk.Display.get_default()
    if display is None:
        return
    monitor = display.get_primary_monitor()
    if monitor is None:
        return
    geometry = monitor.get_geometry()
    x = geometry.x + max(0, (geometry.width - width) // 2)
    y = geometry.y + max(48, int(geometry.height * top_ratio))
    window.move(x, y)
    if _LAYER_SHELL_AVAILABLE and is_wayland() and GtkLayerShell is not None:
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, y - geometry.y)
