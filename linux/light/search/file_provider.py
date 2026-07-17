"""File search provider — replaces Snap SpotlightSearchItem + NSMetadataQuery."""

from __future__ import annotations

import os
import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from ..configuration.configuration import Configuration
from .search_item import SearchItem


def _open_path(path: str) -> None:
    subprocess.Popen(["xdg-open", path], start_new_session=True)


def _is_blocked(path: str, blocked_paths: list[str]) -> bool:
    for blocked in blocked_paths:
        normalized = os.path.expanduser(blocked.rstrip("/"))
        if path == normalized or path.startswith(normalized + os.sep):
            return True
    return False


def _fd_binary() -> str | None:
    for name in ("fd", "fdfind"):
        if shutil.which(name):
            return name
    return None


def _search_with_fd(query: str, paths: list[Path], limit: int, fd_bin: str) -> list[str]:
    cmd = [
        fd_bin,
        "-i",
        "-t", "f",
        "-H",
        query,
        "--max-results", str(limit),
        *map(str, paths),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
    except subprocess.TimeoutExpired:
        return []
    if result.returncode not in (0, 1):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _search_with_find(query: str, paths: list[Path], limit: int) -> list[str]:
    pattern = f"*{query}*"
    found: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        cmd = [
            "find", str(base),
            "-iname", pattern,
            "-type", "f",
            "-not", "-path", "*/.*",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
        except subprocess.TimeoutExpired:
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            if line.strip():
                found.append(line.strip())
            if len(found) >= limit:
                return found
    return found[:limit]


def _search_with_python(query: str, paths: list[Path], limit: int) -> list[str]:
    """Fallback when fd/find are unavailable — shallow walk only."""
    pattern = f"*{query.lower()}*"
    found: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            depth = root[len(str(base)) :].count(os.sep)
            if depth > 3:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if fnmatch(name.lower(), pattern):
                    found.append(str(Path(root) / name))
                    if len(found) >= limit:
                        return found
    return found


def search_files(query: str, config: Configuration) -> list[SearchItem]:
    if not query.strip():
        return []

    paths = config.expanded_search_paths()
    limit = config.result_item_limit

    fd_bin = _fd_binary()
    if fd_bin:
        raw_paths = _search_with_fd(query, paths, limit * 2, fd_bin)
    elif shutil.which("find"):
        raw_paths = _search_with_find(query, paths, limit * 2)
    else:
        raw_paths = _search_with_python(query, paths, limit * 2)

    items: list[SearchItem] = []
    seen: set[str] = set()
    for path in raw_paths:
        if path in seen:
            continue
        seen.add(path)
        if _is_blocked(path, config.blocked_paths):
            continue
        name = Path(path).name
        items.append(
            SearchItem(
                title=name,
                subtitle=path,
                path=path,
                icon_name="text-x-generic",
                action=lambda p=path: _open_path(p),
            )
        )
        if len(items) >= limit:
            break
    return items
