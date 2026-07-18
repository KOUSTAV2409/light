"""Optional Wayland overlay support via gtk-layer-shell."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
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
    # Keep the top edge fixed when height changes so results grow downward.
    window.set_gravity(Gdk.Gravity.NORTH)

    if not _LAYER_SHELL_AVAILABLE or not is_wayland() or GtkLayerShell is None:
        window.set_keep_above(True)
        return "gtk-fallback"

    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
    # Do not stretch full width — keep a floating centered card.
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.LEFT, False)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, False)
    GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.ON_DEMAND)
    GtkLayerShell.set_namespace(window, "light-launcher")
    return "layer-shell"


def collapsed_center_position(
    width: int,
    collapsed_height: int,
) -> tuple[int, int, int] | None:
    """Position so the collapsed search bar sits in the vertical middle.

    That Y is reused when results expand, so the search bar never jumps.
    """
    display = Gdk.Display.get_default()
    if display is None:
        return None
    monitor = display.get_primary_monitor()
    if monitor is None:
        return None
    geometry = monitor.get_geometry()
    x = geometry.x + max(0, (geometry.width - width) // 2)
    y = geometry.y + max(48, (geometry.height - collapsed_height) // 2)
    return x, y, y - geometry.y


def place_launcher(
    window: Gtk.Window,
    width: int,
    height: int,
    *,
    pin_x: int | None = None,
    pin_y: int | None = None,
    collapsed_height: int | None = None,
) -> tuple[int, int] | None:
    """Set size and position atomically. Returns the (x, y) pin used."""
    if pin_x is not None and pin_y is not None:
        x, y = pin_x, pin_y
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display is not None else None
        top_margin = y - monitor.get_geometry().y if monitor is not None else y
    else:
        pos = collapsed_center_position(
            width,
            collapsed_height if collapsed_height is not None else height,
        )
        if pos is None:
            window.set_size_request(-1, -1)
            window.resize(width, height)
            window.set_size_request(width, height)
            return None
        x, y, top_margin = pos

    window.set_size_request(-1, -1)
    gdk_window = window.get_window()
    if gdk_window is not None:
        gdk_window.move_resize(x, y, width, height)
    else:
        # Not realized yet — remember intent; caller should place again after show.
        window.move(x, y)
        window.resize(width, height)
    window.set_size_request(width, height)

    if _LAYER_SHELL_AVAILABLE and is_wayland() and GtkLayerShell is not None:
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, top_margin)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display is not None else None
        if monitor is not None:
            geometry = monitor.get_geometry()
            GtkLayerShell.set_margin(
                window,
                GtkLayerShell.Edge.LEFT,
                max(0, x - geometry.x),
            )

    return x, y
