"""Persistent, local-only clipboard history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..configuration.configuration import DATA_DIR


@dataclass
class ClipboardEntry:
    text: str
    copied_at: str


class ClipboardHistory:
    def __init__(self, limit: int, path: Path | None = None) -> None:
        self.limit = max(1, limit)
        self.path = path or DATA_DIR / "clipboard_history.json"

    def load(self) -> list[ClipboardEntry]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        entries: list[ClipboardEntry] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            copied_at = item.get("copied_at")
            if isinstance(text, str) and isinstance(copied_at, str):
                entries.append(ClipboardEntry(text=text, copied_at=copied_at))
        return entries[: self.limit]

    def add(self, text: str) -> None:
        normalized = text.strip()
        if not normalized or len(normalized) > 100_000:
            return

        entries = [entry for entry in self.load() if entry.text != normalized]
        entries.insert(
            0,
            ClipboardEntry(
                text=normalized,
                copied_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._write(entries[: self.limit])

    def clear(self) -> None:
        self._write([])

    def _write(self, entries: list[ClipboardEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(entry) for entry in entries], indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)
