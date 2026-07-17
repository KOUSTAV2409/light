"""Linux application search using freedesktop .desktop entries."""

from __future__ import annotations

import configparser
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .search_item import SearchItem

_FIELD_CODES = {
    "%f",
    "%F",
    "%u",
    "%U",
    "%d",
    "%D",
    "%n",
    "%N",
    "%i",
    "%c",
    "%k",
    "%v",
    "%m",
}


def _application_dirs() -> list[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    roots = [data_home, *(Path(item) for item in data_dirs.split(":") if item)]
    return [root / "applications" for root in roots]


def _current_desktops() -> set[str]:
    raw = os.environ.get("XDG_CURRENT_DESKTOP", "")
    return {item.strip().lower() for item in raw.replace(";", ":").split(":") if item.strip()}


def _desktop_list(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(";") if item.strip()}


def _visible_in_current_desktop(section: configparser.SectionProxy) -> bool:
    current = _current_desktops()
    only_show_in = _desktop_list(section.get("OnlyShowIn", ""))
    not_show_in = _desktop_list(section.get("NotShowIn", ""))

    if only_show_in and current and only_show_in.isdisjoint(current):
        return False
    if not_show_in and current and not not_show_in.isdisjoint(current):
        return False
    return True


def _launch_arguments(exec_line: str) -> list[str]:
    try:
        tokens = shlex.split(exec_line)
    except ValueError:
        return []

    result: list[str] = []
    for token in tokens:
        if token == "%%":
            result.append("%")
            continue
        if token in _FIELD_CODES:
            continue

        cleaned = token
        for code in _FIELD_CODES:
            cleaned = cleaned.replace(code, "")
        cleaned = cleaned.replace("%%", "%")
        if cleaned:
            result.append(cleaned)
    return result


def _launch_application(exec_line: str, terminal: bool) -> None:
    command = _launch_arguments(exec_line)
    if not command:
        return

    if terminal:
        terminal_binary = os.environ.get("TERMINAL", "x-terminal-emulator")
        command = [terminal_binary, "-e", *command]

    try:
        subprocess.Popen(
            command,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


@dataclass(frozen=True)
class ApplicationDefinition:
    desktop_id: str
    name: str
    exec_line: str
    icon_name: str
    keywords: tuple[str, ...]
    comment: str = ""
    terminal: bool = False

    def matches(self, query: str) -> bool:
        words = [word for word in query.casefold().split() if word]
        if not words:
            return False
        haystack = " ".join((self.name, self.comment, *self.keywords)).casefold()
        return all(word in haystack for word in words)

    def score(self, query: str) -> tuple[int, int, str]:
        normalized = query.casefold().strip()
        name = self.name.casefold()
        if name == normalized:
            rank = 0
        elif name.startswith(normalized):
            rank = 1
        elif any(keyword.casefold().startswith(normalized) for keyword in self.keywords):
            rank = 2
        else:
            rank = 3
        return rank, len(self.name), self.name.casefold()

    def to_search_item(self) -> SearchItem:
        return SearchItem(
            title=self.name,
            subtitle=self.comment or "Application",
            icon_name=self.icon_name or "application-x-executable",
            keywords=list(self.keywords),
            action=lambda: _launch_application(self.exec_line, self.terminal),
        )


def _read_desktop_entry(path: Path) -> ApplicationDefinition | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        return None

    if not parser.has_section("Desktop Entry"):
        return None
    section = parser["Desktop Entry"]
    if section.get("Type", "Application") != "Application":
        return None

    try:
        if section.getboolean("Hidden", fallback=False):
            return None
        if section.getboolean("NoDisplay", fallback=False):
            return None
        terminal = section.getboolean("Terminal", fallback=False)
    except ValueError:
        return None

    if not _visible_in_current_desktop(section):
        return None

    name = section.get("Name", "").strip()
    exec_line = section.get("Exec", "").strip()
    if not name or not exec_line:
        return None

    keywords = tuple(
        keyword.strip()
        for keyword in section.get("Keywords", "").split(";")
        if keyword.strip()
    )
    return ApplicationDefinition(
        desktop_id=path.name,
        name=name,
        exec_line=exec_line,
        icon_name=section.get("Icon", "application-x-executable").strip(),
        keywords=keywords,
        comment=section.get("Comment", "").strip(),
        terminal=terminal,
    )


def load_applications() -> list[ApplicationDefinition]:
    """Load visible applications, respecting XDG directory precedence."""
    applications: list[ApplicationDefinition] = []
    seen_ids: set[str] = set()

    for directory in _application_dirs():
        if not directory.is_dir():
            continue
        try:
            entries = sorted(directory.glob("*.desktop"))
        except OSError:
            continue
        for path in entries:
            if path.name in seen_ids:
                continue
            seen_ids.add(path.name)
            application = _read_desktop_entry(path)
            if application:
                applications.append(application)

    return applications


class ApplicationSearch:
    def __init__(self) -> None:
        self._applications = load_applications()

    def reload(self) -> None:
        self._applications = load_applications()

    def search(self, query: str, limit: int) -> list[SearchItem]:
        matches = [app for app in self._applications if app.matches(query)]
        matches.sort(key=lambda app: app.score(query))
        return [app.to_search_item() for app in matches[:limit]]
