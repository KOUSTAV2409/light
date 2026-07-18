from __future__ import annotations

import unittest
from unittest.mock import patch

from light.search.currency_provider import (
    convert_currency,
    looks_like_currency_query,
    parse_currency_query,
)
from light.search.search import SearchEngine
from light.configuration.configuration import Configuration


class CurrencyProviderTests(unittest.TestCase):
    def test_parses_common_phrases(self) -> None:
        cases = {
            "1 usd to inr": (1.0, "USD", "INR"),
            "1 usd to rupees": (1.0, "USD", "INR"),
            "100 euros in usd": (100.0, "EUR", "USD"),
            "usd to inr": (1.0, "USD", "INR"),
            "2,500 gbp to eur": (2500.0, "GBP", "EUR"),
        }
        for query, expected in cases.items():
            parsed = parse_currency_query(query)
            self.assertIsNotNone(parsed, query)
            assert parsed is not None
            self.assertEqual(
                (parsed.amount, parsed.from_code, parsed.to_code),
                expected,
                query,
            )

    def test_rejects_non_currency_queries(self) -> None:
        self.assertFalse(looks_like_currency_query("budget report"))
        self.assertFalse(looks_like_currency_query("ceo of google"))
        self.assertFalse(looks_like_currency_query("1 + 2"))

    def test_engine_triggers_currency_not_files(self) -> None:
        engine = SearchEngine(Configuration())
        self.assertTrue(engine.should_fetch_instant_answer("1 usd to inr"))
        self.assertFalse(engine.should_search_files("1 usd to rupees"))

    def test_convert_uses_rate(self) -> None:
        query = parse_currency_query("10 usd to inr")
        assert query is not None
        with patch(
            "light.search.currency_provider.urllib.request.urlopen"
        ) as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = (
                b'{"date":"2026-07-17","rates":{"INR":83.5}}'
            )
            result = convert_currency(query)
        self.assertIsNotNone(result)
        assert result is not None
        title, answer, copy_value = result
        self.assertIn("835", title)
        self.assertIn("INR", title)
        self.assertEqual(copy_value, "835.00")
        self.assertIn("2026-07-17", answer)


if __name__ == "__main__":
    unittest.main()
