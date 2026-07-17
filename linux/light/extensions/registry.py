"""Minimal process-isolated extension registry."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..configuration.configuration import DATA_DIR
from ..search.search_item import SearchItem

EXTENSIONS_DIR = DATA_DIR / "extensions"


@dataclass(frozen=True)
class ExtensionManifest:
    extension_id: str
    name: str
    prefix: str
    command: tuple[str, ...]
    description: str = ""
    icon_name: str = "application-x-addon"

    @classmethod
    def from_file(cls, path: Path) -> ExtensionManifest | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            return None

        command = raw.get("command")
        if not isinstance(command, list) or not all(
            isinstance(part, str) and part for part in command
        ):
            return None

        extension_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "")).strip()
        prefix = str(raw.get("prefix", "")).strip().casefold()
        if not extension_id or not name or not prefix:
            return None

        return cls(
            extension_id=extension_id,
            name=name,
            prefix=prefix,
            command=tuple(command),
            description=str(raw.get("description", "")).strip(),
            icon_name=str(raw.get("icon", "application-x-addon")).strip(),
        )

    def matches(self, query: str) -> bool:
        token = query.casefold().strip().split(" ", 1)[0]
        return token == self.prefix

    def arguments(self, query: str) -> str:
        parts = query.strip().split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    def launch(self, query: str) -> None:
        arguments = self.arguments(query)
        environment = os.environ.copy()
        environment.update(
            {
                "LIGHT_EXTENSION_ID": self.extension_id,
                "LIGHT_QUERY": arguments,
            }
        )
        try:
            subprocess.Popen(
                [*self.command, arguments] if arguments else list(self.command),
                env=environment,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return

    def to_search_item(self, query: str) -> SearchItem:
        arguments = self.arguments(query)
        title = self.name if not arguments else f"{self.name}: {arguments}"
        return SearchItem(
            title=title,
            subtitle=self.description or f"Extension · {self.prefix}",
            icon_name=self.icon_name,
            keywords=[self.prefix, self.name],
            action=lambda: self.launch(query),
        )


class ExtensionRegistry:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or EXTENSIONS_DIR
        self._extensions: list[ExtensionManifest] = []
        self.reload()

    def reload(self) -> None:
        self._extensions = []
        if not self.directory.is_dir():
            return
        for manifest_path in sorted(self.directory.glob("*/manifest.json")):
            manifest = ExtensionManifest.from_file(manifest_path)
            if manifest:
                self._extensions.append(manifest)

    def search(self, query: str, limit: int) -> list[SearchItem]:
        matches = [
            extension.to_search_item(query)
            for extension in self._extensions
            if extension.matches(query)
        ]
        return matches[:limit]
