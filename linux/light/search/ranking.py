"""Unified result ordering and deduplication."""

from __future__ import annotations

from .search_item import SearchItem


def _item_key(item: SearchItem) -> tuple[str, ...]:
    if item.path:
        return ("path", item.path.casefold())
    if item.is_instant_answer:
        return ("answer", item.title.casefold())
    if item.is_loading:
        return ("loading", item.title.casefold())
    return ("item", item.title.casefold(), item.subtitle.casefold())


def _is_web_item(item: SearchItem) -> bool:
    return item.icon_name in ("web-browser", "system-search") and not item.path


def _is_app_item(item: SearchItem) -> bool:
    return item.icon_name == "application-x-executable"


def _file_rank(item: SearchItem, query: str) -> tuple[int, int, str]:
    tokens = [token for token in query.casefold().split() if token]
    name = item.title.casefold()
    path = item.path.casefold()
    if tokens and all(token in name for token in tokens):
        rank = 0
    elif tokens and all(token in path for token in tokens):
        rank = 1
    else:
        rank = 2
    return rank, len(name), name


def _head_rank(item: SearchItem, query: str) -> tuple[int, int, str]:
    if item.is_loading:
        return (9, 0, item.title.casefold())
    if _is_app_item(item):
        name = item.title.casefold()
        normalized = query.casefold().strip()
        if name == normalized:
            return (0, len(name), name)
        if name.startswith(normalized):
            return (1, len(name), name)
        return (2, len(name), name)
    return (3, len(item.title), item.title.casefold())


def merge_ranked_results(
    fast: list[SearchItem],
    files: list[SearchItem],
    answer: SearchItem | None,
    query: str,
    limit: int,
) -> list[SearchItem]:
    web_items = [item for item in fast if _is_web_item(item)]
    head = [item for item in fast if item not in web_items]

    ranked_files = sorted(files, key=lambda item: _file_rank(item, query))
    ranked_head = sorted(head, key=lambda item: _head_rank(item, query))

    merged: list[SearchItem] = []
    seen: set[tuple[str, ...]] = set()

    def add(item: SearchItem) -> None:
        key = _item_key(item)
        if key in seen:
            return
        seen.add(key)
        merged.append(item)

    if answer:
        add(answer)
    for item in ranked_head:
        add(item)
    for item in ranked_files:
        add(item)
    for item in web_items:
        add(item)

    return merged[:limit]
