"""Search orchestrator — ported from Snap/Search.swift."""

from __future__ import annotations

from ..configuration.configuration import Configuration
from .action_provider import ActionSearch
from .calculator_provider import maybe_calculator_item
from .file_provider import search_files
from .instant_answer_provider import fetch_instant_answer, instant_answer_item
from .search_item import SearchItem
from .web_provider import looks_like_url, search_web


class SearchEngine:
    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._action_search = ActionSearch()

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
        results.extend(search_web(query, self._config))

        return results[: self._config.result_item_limit]

    def should_search_files(self, query: str) -> bool:
        query = query.strip()
        if len(query) < 3:
            return False
        if looks_like_url(query):
            return False

        parts = query.split()
        token = parts[0].lower()

        # Skip common English stopwords while the user is still typing a question.
        if token in {
            "who", "what", "when", "where", "why", "how", "is", "are",
            "the", "a", "an", "of", "for", "to", "in", "on",
        }:
            return False

        action_results = self._action_search.search(query, " ".join(parts[1:]) if len(parts) > 1 else "")
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

        # Multi-word queries are usually web searches, not file lookups.
        if len(parts) > 1:
            return False

        return True

    def should_fetch_instant_answer(self, query: str) -> bool:
        if len(query.strip()) < 3:
            return False
        if looks_like_url(query.strip()):
            return False

        parts = query.split(maxsplit=1)
        if len(parts) < 2:
            return False

        calc = maybe_calculator_item(query)
        if calc is not None and all(ch in "0123456789+-*/(). " for ch in query):
            return False

        return True

    def fetch_instant_answer_item(self, query: str) -> SearchItem | None:
        result = fetch_instant_answer(query, self._config)
        if not result:
            return None
        title, answer, source_url = result
        return instant_answer_item(query, title, answer, source_url)

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
