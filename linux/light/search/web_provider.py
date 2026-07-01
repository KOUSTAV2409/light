"""Web search provider — ported from Snap/WebSearch.swift."""

from __future__ import annotations

import subprocess
import webbrowser
from urllib.parse import quote, urlparse

from ..configuration.configuration import Configuration
from .search_item import SearchItem

_SEARCH_URLS = {
    "google": "https://www.google.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "yahoo": "https://search.yahoo.com/search?p={query}",
    "ecosia": "https://www.ecosia.org/search?q={query}",
}


def looks_like_url(text: str) -> bool:
    if " " in text:
        return False
    if "." not in text:
        return False
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    return bool(parsed.netloc)


def search_web(query: str, config: Configuration) -> list[SearchItem]:
    if not query.strip():
        return []

    items: list[SearchItem] = []

    if looks_like_url(query):
        url = query if "://" in query else f"https://{query}"
        items.append(
            SearchItem(
                title=f"Open {query}",
                subtitle=url,
                icon_name="web-browser",
                action=lambda u=url: webbrowser.open(u),
            )
        )

    engine = config.default_search_engine.lower()
    template = _SEARCH_URLS.get(engine, _SEARCH_URLS["google"])
    search_url = template.format(query=quote(query))

    items.append(
        SearchItem(
            title=f"Search {engine.title()} for \"{query}\"",
            subtitle=search_url,
            icon_name="system-search",
            action=lambda u=search_url: webbrowser.open(u),
        )
    )
    return items
