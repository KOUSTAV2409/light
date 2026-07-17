"""File search provider — replaces Snap SpotlightSearchItem + NSMetadataQuery."""

from __future__ import annotations

import os
import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from ..configuration.configuration import Configuration
from .search_item import SearchItem

# Raycast/Spotlight-style: search common folders first, skip heavy cache trees.
_FAST_HOME_DIRS = (
    "Desktop",
    "Documents",
    "Downloads",
    "Projects",
    "Pictures",
    "Music",
    "Videos",
)
_FD_EXCLUDES = (
    ".git",
    "node_modules",
    ".cache",
    ".npm",
    ".nvm",
    ".zoom",
    ".codex",
    "__pycache__",
    ".venv",
    "venv",
    ".cargo",
    ".rustup",
    ".local/share/Trash",
)


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


def _locate_binary() -> str | None:
    for name in ("plocate", "locate"):
        if shutil.which(name):
            return name
    return None


def _query_tokens(query: str) -> list[str]:
    return [token for token in query.casefold().split() if token]


def _path_matches_tokens(path: str, tokens: list[str]) -> bool:
    haystack = path.casefold()
    return all(token in haystack for token in tokens)


def _primary_token(tokens: list[str]) -> str:
    return max(tokens, key=len)


def _search_tiers(config: Configuration) -> list[list[Path]]:
    """Fast tier (Documents, Downloads, …) then full configured roots."""
    home = Path.home().resolve()
    fast: list[Path] = []
    slow: list[Path] = []

    for raw in config.expanded_search_paths():
        if raw == home:
            for name in _FAST_HOME_DIRS:
                candidate = home / name
                if candidate.is_dir():
                    fast.append(candidate)
            slow.append(home)
        elif raw.is_dir():
            slow.append(raw)

    if fast:
        return [fast, slow]
    return [slow] if slow else [[home]]


def _run_subprocess(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return None


def _search_with_locate(tokens: list[str], limit: int) -> list[str]:
    locate_bin = _locate_binary()
    if not locate_bin or not tokens:
        return []

    cmd = [locate_bin, "-i", "-l", str(max(limit * 4, 40)), _primary_token(tokens)]
    result = _run_subprocess(cmd, timeout=1.0)
    if result is None or result.returncode not in (0, 1):
        return []

    matches: list[str] = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if path and _path_matches_tokens(path, tokens):
            matches.append(path)
        if len(matches) >= limit:
            break
    return matches


def _search_with_fd(
    query: str,
    paths: list[Path],
    limit: int,
    fd_bin: str,
    timeout: float,
) -> list[str]:
    tokens = _query_tokens(query)
    if not tokens or not paths:
        return []

    pattern = _primary_token(tokens)
    cmd = [
        fd_bin,
        "-i",
        "-t",
        "f",
        "-H",
        "--max-results",
        str(max(limit * 8, 40)),
    ]
    for exclude in _FD_EXCLUDES:
        cmd.extend(["--exclude", exclude])
    cmd.extend(["--", pattern, *map(str, paths)])

    result = _run_subprocess(cmd, timeout=timeout)
    if result is None or result.returncode not in (0, 1):
        return []

    matches = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and _path_matches_tokens(line.strip(), tokens)
    ]
    return matches[:limit]


def _search_with_find(query: str, paths: list[Path], limit: int, timeout: float) -> list[str]:
    tokens = _query_tokens(query)
    if not tokens:
        return []

    pattern = f"*{_primary_token(tokens)}*"
    found: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        cmd = [
            "find",
            str(base),
            "-iname",
            pattern,
            "-type",
            "f",
            "-not",
            "-path",
            "*/.*",
        ]
        result = _run_subprocess(cmd, timeout=timeout)
        if result is None or result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            path = line.strip()
            if path and _path_matches_tokens(path, tokens):
                found.append(path)
            if len(found) >= limit:
                return found
    return found[:limit]


def _search_with_python(query: str, paths: list[Path], limit: int) -> list[str]:
    tokens = _query_tokens(query)
    if not tokens:
        return []

    pattern = f"*{_primary_token(tokens)}*"
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
                path = str(Path(root) / name)
                if fnmatch(name.lower(), pattern) and _path_matches_tokens(path, tokens):
                    found.append(path)
                    if len(found) >= limit:
                        return found
    return found


def _collect_raw_paths(query: str, config: Configuration, limit: int) -> list[str]:
    tokens = _query_tokens(query)
    if not tokens:
        return []

    seen: set[str] = set()
    collected: list[str] = []

    def add(paths: list[str]) -> None:
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            if _is_blocked(path, config.blocked_paths):
                continue
            collected.append(path)
            if len(collected) >= limit:
                return

    add(_search_with_locate(tokens, limit))

    fd_bin = _fd_binary()
    tiers = _search_tiers(config)
    for index, tier in enumerate(tiers):
        if len(collected) >= limit:
            break
        remaining = limit - len(collected)
        timeout = 2.0 if index == 0 else 5.0
        if fd_bin:
            add(_search_with_fd(query, tier, remaining, fd_bin, timeout=timeout))
        elif shutil.which("find"):
            add(_search_with_find(query, tier, remaining, timeout=timeout))
        else:
            add(_search_with_python(query, tier, remaining))

    return collected[:limit]


def search_files(query: str, config: Configuration) -> list[SearchItem]:
    if not query.strip():
        return []

    limit = config.result_item_limit
    raw_paths = _collect_raw_paths(query, config, limit * 2)

    items: list[SearchItem] = []
    for path in raw_paths[:limit]:
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
    return items


def file_search_loading_item() -> SearchItem:
    return SearchItem(
        title="Searching files…",
        subtitle="Desktop, Documents, Downloads, then home",
        icon_name="folder",
        is_loading=True,
        action=lambda: None,
    )
