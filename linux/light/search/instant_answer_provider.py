"""Instant answer provider — OpenAI web search first, Wikipedia fallback."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import webbrowser

from ..configuration.configuration import Configuration
from .openai_answer_provider import fetch_openai_answer, resolve_openai_api_key
from .search_item import SearchItem

_USER_AGENT = "LightLauncher/0.1 (Linux; MVP)"
_TIMEOUT = 4


def _fetch_url(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _rewrite_queries(query: str) -> list[str]:
    cleaned = query.strip()
    lowered = cleaned.lower()
    rewrites = [cleaned]

    patterns = [
        (r"^who is the ceo of (.+)$", r"\1 CEO"),
        (r"^who is ceo of (.+)$", r"\1 CEO"),
        (r"^ceo of (.+)$", r"\1 CEO"),
        (r"^who is the president of (.+)$", r"\1 president"),
        (r"^president of (.+)$", r"\1 president"),
        (r"^what is the capital of (.+)$", r"capital of \1"),
        (r"^capital of (.+)$", r"capital of \1"),
        (r"^who (?:founded|is the founder of) (.+)$", r"\1 founder"),
        (r"^founder of (.+)$", r"\1 founder"),
        (r"^what is (.+)$", r"\1"),
        (r"^who is (.+)$", r"\1"),
    ]
    for pattern, replacement in patterns:
        if re.match(pattern, lowered):
            rewritten = re.sub(pattern, replacement, lowered).strip()
            if rewritten and rewritten not in rewrites:
                rewrites.insert(0, rewritten)
            break

    return rewrites


def _score_extract(query: str, title: str, extract: str) -> int:
    score = 0
    query_lower = query.lower()
    haystack = f"{title} {extract}".lower()

    query_words = {word for word in re.findall(r"[a-z0-9]+", query_lower) if len(word) > 2}
    for word in query_words:
        if word in haystack:
            score += 2

    if "ceo" in query_lower:
        if "ceo of google" in haystack or "ceo of alphabet" in haystack:
            score += 25
        if "has been the ceo" in haystack or "is the ceo" in haystack:
            score += 15
        if "was the ceo" in haystack or "former" in haystack:
            score -= 12

    if "capital" in query_lower and "capital" in haystack:
        score += 10
    if "president" in query_lower and "president" in haystack:
        score += 10
    if "founder" in query_lower and "founder" in haystack:
        score += 10

    if len(extract) >= 60:
        score += 1
    return score


def _fetch_wikipedia_answer(query: str) -> tuple[str, str, str] | None:
    best: tuple[str, str, str] | None = None
    best_score = 0

    for search_query in _rewrite_queries(query):
        encoded = urllib.parse.quote(search_query)
        body = _fetch_url(
            "https://en.wikipedia.org/w/api.php?"
            f"action=query&generator=search&gsrsearch={encoded}"
            "&prop=extracts&exintro=1&explaintext=1&exsentences=4"
            "&gsrlimit=5&format=json"
        )
        if not body:
            continue

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", query)
            extract = page.get("extract", "").strip()
            if len(extract) < 30:
                continue

            score = _score_extract(query, title, extract)
            if score > best_score:
                best_score = score
                url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                best = (title, extract, url)

    if best_score < 3:
        return None
    return best


def fetch_instant_answer(
    query: str,
    config: Configuration | None = None,
) -> tuple[str, str, str] | None:
    """Return (title, answer_text, source_url).

    Prefer OpenAI + web search when configured; fall back to Wikipedia.
    """
    if config is not None and config.openai_enabled and resolve_openai_api_key(config):
        try:
            openai_result = fetch_openai_answer(query, config)
        except Exception as exc:
            print(f"OpenAI answer failed, falling back to Wikipedia: {exc}", flush=True)
            openai_result = None
        if openai_result:
            return openai_result.title, openai_result.answer, openai_result.source_url

    return _fetch_wikipedia_answer(query)


def instant_answer_item(query: str, title: str, answer: str, source_url: str) -> SearchItem:
    def open_source() -> None:
        if source_url:
            webbrowser.open(source_url)
        else:
            webbrowser.open(
                "https://www.google.com/search?q=" + urllib.parse.quote(query)
            )

    return SearchItem(
        title=title,
        subtitle=answer,
        answer_text=answer,
        is_instant_answer=True,
        icon_name="dialog-information",
        action=open_source,
    )
