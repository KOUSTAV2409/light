"""Search and restore locally stored clipboard entries."""

from __future__ import annotations

from ..clipboard.history import ClipboardHistory
from .search_item import SearchItem


class ClipboardSearch:
    def __init__(self, history: ClipboardHistory, copy_text) -> None:
        self._history = history
        self._copy_text = copy_text

    def search(self, query: str, limit: int) -> list[SearchItem]:
        stripped = query.strip()
        lowered = stripped.casefold()
        if not (
            "clipboard".startswith(lowered)
            or lowered.startswith("clipboard ")
            or "clip".startswith(lowered)
        ):
            return []

        filter_text = ""
        if " " in stripped:
            filter_text = stripped.split(" ", 1)[1].casefold().strip()

        results: list[SearchItem] = []
        for entry in self._history.load():
            if filter_text and filter_text not in entry.text.casefold():
                continue
            preview = " ".join(entry.text.split())
            if len(preview) > 90:
                preview = preview[:87] + "…"
            results.append(
                SearchItem(
                    title=preview,
                    subtitle=f"Clipboard · {entry.copied_at}",
                    icon_name="edit-paste",
                    action=lambda text=entry.text: self._copy_text(text),
                )
            )
            if len(results) >= limit:
                break
        return results
