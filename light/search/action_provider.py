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
    argv: list[str]
    keywords: list[str]
    icon_name: str = "system-run"
    accepts_arguments: bool = False


def _run_argv(argv: list[str]) -> None:
    if not argv:
        return
    try:
        subprocess.Popen(
            argv,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


def _parse_argv(entry: dict) -> list[str] | None:
    argv = entry.get("argv")
    if isinstance(argv, list) and all(isinstance(part, str) and part for part in argv):
        return list(argv)

    command = entry.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    try:
        parsed = shlex.split(command)
    except ValueError:
        return None
    return parsed or None


def _load_actions() -> list[ActionDefinition]:
    actions: list[ActionDefinition] = []
    for path in (BUNDLED_ACTIONS, USER_ACTIONS):
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, list):
            continue
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            argv = _parse_argv(entry)
            if not isinstance(title, str) or not title.strip() or not argv:
                continue
            keywords = entry.get("keywords", [title])
            if not isinstance(keywords, list) or not all(
                isinstance(keyword, str) for keyword in keywords
            ):
                keywords = [title]
            actions.append(
                ActionDefinition(
                    title=title,
                    argv=argv,
                    keywords=keywords,
                    icon_name=str(entry.get("icon_name", "system-run")),
                    accepts_arguments=bool(entry.get("accepts_arguments", False)),
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

            argv = list(action.argv)
            if action.accepts_arguments and arguments:
                argv.append(arguments)

            items.append(
                SearchItem(
                    title=action.title,
                    subtitle=shlex.join(argv),
                    icon_name=action.icon_name,
                    keywords=action.keywords,
                    accepts_arguments=action.accepts_arguments,
                    action=lambda cmd=argv: _run_argv(cmd),
                )
            )
        return items
