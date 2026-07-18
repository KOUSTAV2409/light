"""Raycast-style currency conversion using Frankfurter (no API key)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Event

from .calculator_provider import _copy_to_clipboard
from .openai_answer_provider import RequestCancelled
from .search_item import SearchItem

_TIMEOUT = 4
_API = "https://api.frankfurter.dev/v1/latest"

# Common aliases → ISO codes Frankfurter understands.
_CURRENCY_ALIASES: dict[str, str] = {
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "usdollar": "USD",
    "usdollars": "USD",
    "buck": "USD",
    "bucks": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "sterling": "GBP",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "rs": "INR",
    "jpy": "JPY",
    "yen": "JPY",
    "cny": "CNY",
    "yuan": "CNY",
    "rmb": "CNY",
    "aud": "AUD",
    "cad": "CAD",
    "chf": "CHF",
    "sgd": "SGD",
    "hkd": "HKD",
    "nzd": "NZD",
    "krw": "KRW",
    "won": "KRW",
    "aed": "AED",
    "dirham": "AED",
    "dirhams": "AED",
    "sar": "SAR",
    "riyals": "SAR",
    "riyal": "SAR",
}

_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<amount>\d+(?:[.,]\d+)?)
    \s*
    (?P<from>[a-zA-Z.]+)
    \s+
    (?:to|in|into|=)
    \s+
    (?P<to>[a-zA-Z.]+)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_PATTERN_SWAPPED = re.compile(
    r"""
    ^\s*
    (?P<from>[a-zA-Z.]+)
    \s+
    (?:to|in|into)
    \s+
    (?P<to>[a-zA-Z.]+)
    \s*
    (?P<amount>\d+(?:[.,]\d+)?)?
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass(frozen=True)
class CurrencyQuery:
    amount: float
    from_code: str
    to_code: str


def _normalize_currency(token: str) -> str | None:
    cleaned = token.strip().lower().replace(".", "").replace(" ", "")
    if not cleaned:
        return None
    if cleaned in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[cleaned]
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return None


def parse_currency_query(query: str) -> CurrencyQuery | None:
    stripped = query.strip()
    if not stripped:
        return None

    match = _PATTERN.match(stripped) or _PATTERN_SWAPPED.match(stripped)
    if not match:
        return None

    amount_raw = match.group("amount") or "1"
    amount_raw = amount_raw.replace(",", "")
    try:
        amount = float(amount_raw)
    except ValueError:
        return None
    if amount <= 0:
        return None

    from_code = _normalize_currency(match.group("from"))
    to_code = _normalize_currency(match.group("to"))
    if not from_code or not to_code or from_code == to_code:
        return None
    return CurrencyQuery(amount=amount, from_code=from_code, to_code=to_code)


def looks_like_currency_query(query: str) -> bool:
    return parse_currency_query(query) is not None


def _format_amount(value: float) -> str:
    if abs(value) >= 100:
        text = f"{value:,.2f}"
    elif abs(value) >= 1:
        text = f"{value:,.4f}".rstrip("0").rstrip(".")
    else:
        text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text


def convert_currency(
    query: CurrencyQuery,
    cancel_event: Event | None = None,
) -> tuple[str, str, str] | None:
    """Return (title, answer_text, copy_value)."""
    if cancel_event is not None and cancel_event.is_set():
        raise RequestCancelled()

    url = f"{_API}?base={query.from_code}&symbols={query.to_code}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LightLauncher/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    if cancel_event is not None and cancel_event.is_set():
        raise RequestCancelled()

    rates = payload.get("rates") if isinstance(payload, dict) else None
    if not isinstance(rates, dict):
        return None
    rate = rates.get(query.to_code)
    if not isinstance(rate, (int, float)):
        return None

    converted = float(rate) * query.amount
    amount_text = _format_amount(query.amount)
    result_text = _format_amount(converted)
    rate_text = _format_amount(float(rate))
    date = str(payload.get("date", "")).strip()

    title = f"{amount_text} {query.from_code} = {result_text} {query.to_code}"
    answer = (
        f"1 {query.from_code} = {rate_text} {query.to_code}"
        + (f" · rates as of {date}" if date else "")
        + ". Press Enter to copy the converted amount."
    )
    return title, answer, result_text


def currency_answer_item(
    query: str,
    cancel_event: Event | None = None,
) -> SearchItem | None:
    parsed = parse_currency_query(query)
    if parsed is None:
        return None

    result = convert_currency(parsed, cancel_event=cancel_event)
    if result is None:
        return None

    title, answer, copy_value = result
    return SearchItem(
        title=title,
        subtitle=answer,
        answer_text=answer,
        is_instant_answer=True,
        icon_name="accessories-calculator",
        action=lambda value=copy_value: _copy_to_clipboard(value),
    )
