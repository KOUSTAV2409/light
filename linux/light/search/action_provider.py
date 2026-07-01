"""Action search — ported from Snap/ActionSearch.swift + ActionDecoder.swift."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from ..configuration.configuration import CONFIG_DIR, DATA_DIR
from .search_item import SearchItem

BUNDLED_ACTIONS = Path(__file__).resolve().parent.parent / "actions" / "default_actions.json"
USER_ACTIONS = CONFIG_DIR / "actions.json"


@dataclass
class ActionDefinition:
    title: str
    command: str
    keywords: list[str]
    icon_name: str = "system-run"
    accepts_arguments: bool = False


def _run_command(command: str) -> None:
    subprocess.Popen(command, shell=True, start_new_session=True)


def _load_actions() -> list[ActionDefinition]:
    actions: list[ActionDefinition] = []
    for path in (BUNDLED_ACTIONS, USER_ACTIONS):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
        for entry in raw:
            actions.append(
                ActionDefinition(
                    title=entry["title"],
                    command=entry["command"],
                    keywords=entry.get("keywords", [entry["title"]]),
                    icon_name=entry.get("icon_name", "system-run"),
                    accepts_arguments=entry.get("accepts_arguments", False),
                )
            )
    return actions


def _keyword_matches(keyword: str, query: str) -> bool:
    return fnmatch(keyword.lower(), f"{query.lower()}*")


class ActionSearch:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._actions = _load_actions()

    def search(self, query: str, arguments: str = "") -> list[SearchItem]:
        if not query.strip():
            return []

        token = query.split()[0]
        items: list[SearchItem] = []
        for action in self._actions:
            if not any(_keyword_matches(kw, token) for kw in action.keywords):
                continue

            command = action.command
            if action.accepts_arguments and arguments:
                command = f"{command} {shlex.quote(arguments)}"

            items.append(
                SearchItem(
                    title=action.title,
                    subtitle=command,
                    icon_name=action.icon_name,
                    keywords=action.keywords,
                    accepts_arguments=action.accepts_arguments,
                    action=lambda cmd=command: _run_command(cmd),
                )
            )
        return items
