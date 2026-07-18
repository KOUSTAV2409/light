"""Global hotkey support — replaces Snap/KeyboardShortcutManager.swift (MVP)."""

from __future__ import annotations

import threading
from typing import Callable


def _parse_hotkey(hotkey: str) -> tuple[set[str], str]:
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    key = parts[-1]
    modifiers = set(parts[:-1])
    return modifiers, key


def start_global_hotkey(hotkey: str, callback: Callable[[], None]) -> threading.Thread | None:
    """Register a global hotkey in a background thread.

    Uses the `keyboard` package when installed. Returns None if unavailable.
    """
    try:
        import keyboard  # type: ignore[import-untyped]
    except ImportError:
        return None

    modifiers, key = _parse_hotkey(hotkey)
    combo = "+".join(sorted(modifiers) + [key]) if modifiers else key

    def _worker() -> None:
        keyboard.add_hotkey(combo, callback, suppress=False)
        keyboard.wait()

    thread = threading.Thread(target=_worker, name="light-hotkey", daemon=True)
    thread.start()
    return thread
