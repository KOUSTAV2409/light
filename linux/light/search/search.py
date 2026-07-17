"""Search orchestrator — ported from Snap/Search.swift."""

from __future__ import annotations

from typing import Callable

from ..clipboard.history import ClipboardHistory
from ..configuration.configuration import Configuration
from ..extensions.registry import ExtensionRegistry
from .action_provider import ActionSearch
from .application_provider import ApplicationSearch
from .calculator_provider import maybe_calculator_item
from .clipboard_provider import ClipboardSearch
from .file_provider import search_files
from .instant_answer_provider import fetch_instant_answer, instant_answer_item
from .search_item import SearchItem
from .web_provider import looks_like_url, search_web


_QUESTION_STARTERS = {
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "is",
    "are",
    "does",
    "do",
    "did",
    "can",
    "could",
    "should",
    "would",
}

# Phrases like "ceo of google" — Raycast-style AI + local results in parallel.
_FACT_ROLES = {
    "ceo",
    "cfo",
    "cto",
    "coo",
    "founder",
    "cofounder",
    "president",
    "owner",
    "chairman",
    "capital",
    "population",
    "age",
    "birthday",
    "headquarters",
    "hq",
}


def _looks_like_question(query: str) -> bool:
    first = query.strip().split(maxsplit=1)[0].lower() if query.strip() else ""
    return first in _QUESTION_STARTERS


def _looks_like_fact_query(query: str) -> bool:
    """Detect short entity-fact lookups that should get a live AI answer."""
    parts = [part for part in query.casefold().split() if part]
    if len(parts) < 2 or len(parts) > 8:
        return False
    if parts[0] in _FACT_ROLES and "of" in parts:
        return True
    if len(parts) >= 3 and parts[1] == "of" and parts[0] in _FACT_ROLES:
        return True
    # "sundar pichai role" style is left to explicit ? / who
    joined = " ".join(parts)
    return any(
        joined.startswith(f"{role} of ") or f" {role} of " in f" {joined}"
        for role in _FACT_ROLES
    )


class SearchEngine:
    def __init__(
        self,
        config: Configuration,
        clipboard_history: ClipboardHistory | None = None,
        copy_text: Callable[[str], None] | None = None,
    ) -> None:
        self._config = config
        self._action_search = ActionSearch()
        self._application_search = ApplicationSearch()
        self._extension_registry = (
            ExtensionRegistry() if config.extensions_enabled else None
        )
        self._clipboard_search = (
            ClipboardSearch(clipboard_history, copy_text)
            if clipboard_history is not None and copy_text is not None
            else None
        )

    def search_fast(self, query: str) -> list[SearchItem]:
        """Instant providers only — safe to run on the GTK main thread."""
        if not query.strip():
            return []

        arguments = ""
        parts = query.split(maxsplit=1)
        if len(parts) > 1:
            arguments = parts[1]

        results: list[SearchItem] = []

        calc = maybe_calculator_item(query)
        if calc:
            results.append(calc)

        results.extend(self._action_search.search(query, arguments))
        results.extend(
            self._application_search.search(query, self._config.result_item_limit)
        )
        if self._clipboard_search is not None:
            results.extend(
                self._clipboard_search.search(query, self._config.result_item_limit)
            )
        if self._extension_registry is not None:
            results.extend(
                self._extension_registry.search(query, self._config.result_item_limit)
            )
        results.extend(search_web(query, self._config))

        return results[: self._config.result_item_limit]

    def should_search_files(self, query: str) -> bool:
        """Always search files in parallel, except explicit AI-only `?` queries."""
        query = query.strip()
        if query.startswith("?"):
            return False
        if len(query) < 2:
            return False
        if looks_like_url(query):
            return False

        parts = query.split()
        token = parts[0].lower()

        action_results = self._action_search.search(
            query,
            " ".join(parts[1:]) if len(parts) > 1 else "",
        )
        exact_action = any(
            token in {kw.lower() for kw in item.keywords}
            for item in action_results
        )
        if exact_action:
            return False

        calc = maybe_calculator_item(query)
        math_only = calc is not None and all(ch in "0123456789+-*/(). " for ch in query)
        if math_only:
            return False

        return True

    def should_fetch_instant_answer(self, query: str) -> bool:
        """Live AI for ?, questions, and short fact lookups — with local results."""
        stripped = query.strip()
        if len(stripped) < 3:
            return False
        if looks_like_url(stripped):
            return False

        if stripped.startswith("?"):
            return len(stripped.lstrip("?").strip()) >= 3

        calc = maybe_calculator_item(stripped)
        if calc is not None and all(ch in "0123456789+-*/(). " for ch in stripped):
            return False

        if _looks_like_question(stripped):
            return len(stripped.split()) >= 2

        if _looks_like_fact_query(stripped):
            return True

        return False

    def fetch_instant_answer_item(
        self,
        query: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> SearchItem | None:
        cleaned = query.strip()
        if cleaned.startswith("?"):
            cleaned = cleaned.lstrip("?").strip()
        result = fetch_instant_answer(cleaned, self._config, on_delta=on_delta)
        if not result:
            return None
        title, answer, source_urls = result
        return instant_answer_item(cleaned, title, answer, source_urls)

    @property
    def uses_openai_answers(self) -> bool:
        from .openai_answer_provider import resolve_openai_api_key

        return bool(self._config.openai_enabled and resolve_openai_api_key(self._config))

    def search_files_only(self, query: str) -> list[SearchItem]:
        return search_files(query, self._config)

    def search(self, query: str) -> list[SearchItem]:
        """Full search — used by tests; UI should prefer search_fast + search_files_only."""
        results = self.search_fast(query)
        if self.should_search_files(query):
            results.extend(self.search_files_only(query))
        return results[: self._config.result_item_limit]

    def merge_results(
        self,
        fast: list[SearchItem],
        files: list[SearchItem],
        answer: SearchItem | None = None,
    ) -> list[SearchItem]:
        web_items = [item for item in fast if item.icon_name in ("web-browser", "system-search")]
        head = [item for item in fast if item not in web_items]
        merged: list[SearchItem] = []
        if answer:
            merged.append(answer)
        merged.extend(head)
        merged.extend(files)
        merged.extend(web_items)
        return merged[: self._config.result_item_limit]
