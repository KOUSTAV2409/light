from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from light.configuration.configuration import Configuration
from light.search.file_provider import _is_blocked, _search_with_fd
from light.search.openai_answer_provider import (
    _extract_output_text,
    _extract_source_url,
    _extract_source_urls,
    _read_stream,
    _title_from_answer,
)
from light.search.search import SearchEngine
from light.search.web_provider import looks_like_url, search_web


class SearchProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Configuration(result_item_limit=10)

    def test_url_detection(self) -> None:
        self.assertTrue(looks_like_url("example.com"))
        self.assertTrue(looks_like_url("https://example.com/docs"))
        self.assertFalse(looks_like_url("search example.com"))

    def test_web_query_is_encoded(self) -> None:
        item = search_web("ceo of google", self.config)[-1]
        self.assertIn("ceo%20of%20google", item.subtitle)

    def test_ai_only_prefix_skips_file_search(self) -> None:
        engine = SearchEngine(self.config)
        self.assertFalse(engine.should_search_files("? budget tips"))
        self.assertTrue(engine.should_search_files("who is the ceo of google"))
        self.assertTrue(engine.should_search_files("ceo of google"))

    def test_multi_word_can_search_files(self) -> None:
        engine = SearchEngine(self.config)
        self.assertTrue(engine.should_search_files("budget report"))
        self.assertTrue(engine.should_search_files("python tutorial"))
        self.assertTrue(engine.should_search_files("ceo of google"))

    def test_single_word_can_search_files(self) -> None:
        engine = SearchEngine(self.config)
        self.assertTrue(engine.should_search_files("readme"))

    def test_instant_answer_for_questions_facts_and_prefix(self) -> None:
        engine = SearchEngine(self.config)
        self.assertTrue(engine.should_fetch_instant_answer("who is the ceo of google"))
        self.assertTrue(engine.should_fetch_instant_answer("ceo of google"))
        self.assertTrue(engine.should_fetch_instant_answer("? latest openai news"))
        self.assertFalse(engine.should_fetch_instant_answer("budget report"))

    def test_blocked_path_uses_path_boundary(self) -> None:
        self.assertTrue(_is_blocked("/home/user/private/file", ["/home/user/private"]))
        self.assertFalse(_is_blocked("/home/user/privately/file", ["/home/user/private"]))

    def test_multi_word_path_match(self) -> None:
        from light.search.file_provider import _path_matches_tokens

        self.assertTrue(
            _path_matches_tokens("/home/me/Documents/budget-report.pdf", ["budget", "report"])
        )
        self.assertFalse(
            _path_matches_tokens("/home/me/Documents/budget.pdf", ["budget", "report"])
        )

    def test_fd_timeout_returns_empty_results(self) -> None:
        with patch(
            "light.search.file_provider.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["fd"], 2.0),
        ):
            self.assertEqual(
                _search_with_fd("query", [], 10, "fd", timeout=2.0),
                [],
            )

    def test_openai_output_text_extraction(self) -> None:
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Current answer"}],
                }
            ]
        }
        self.assertEqual(_extract_output_text(payload), "Current answer")

    def test_openai_citation_extraction(self) -> None:
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Answer",
                            "annotations": [{"type": "url_citation", "url": "https://example.com"}],
                        }
                    ],
                }
            ]
        }
        self.assertEqual(_extract_source_url(payload), "https://example.com")

    def test_openai_multiple_citations_are_deduplicated(self) -> None:
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Answer",
                            "annotations": [
                                {"url": "https://one.example"},
                                {"url": "https://two.example"},
                                {"url": "https://one.example"},
                            ],
                        }
                    ],
                }
            ]
        }
        self.assertEqual(
            _extract_source_urls(payload),
            ["https://one.example", "https://two.example"],
        )

    def test_openai_stream_accumulates_text(self) -> None:
        response = [
            b'data: {"type":"response.output_text.delta","delta":"Current "}\n',
            b'data: {"type":"response.output_text.delta","delta":"answer."}\n',
            b'data: {"type":"response.completed","response":{"output_text":"Current answer."}}\n',
            b"data: [DONE]\n",
        ]
        updates: list[str] = []
        payload = _read_stream(response, updates.append)
        self.assertEqual(payload["output_text"], "Current answer.")
        self.assertEqual(updates[-1], "Current answer.")

    def test_answer_title_is_shortened(self) -> None:
        title = _title_from_answer(
            "question",
            "Sundar Pichai is the CEO of Google. More detail follows.",
        )
        self.assertEqual(title, "Sundar Pichai is the CEO of Google")


if __name__ == "__main__":
    unittest.main()
