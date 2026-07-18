from __future__ import annotations

import unittest
from threading import Event

from light.search.openai_answer_provider import RequestCancelled, _read_stream
from light.search.ranking import merge_ranked_results
from light.search.search_item import SearchItem


class RankingTests(unittest.TestCase):
    def test_answer_stays_on_top_and_files_rank_before_web(self) -> None:
        answer = SearchItem(
            title="AI",
            subtitle="answer",
            is_instant_answer=True,
            answer_text="answer",
            action=lambda: None,
        )
        app = SearchItem(
            title="Firefox",
            subtitle="Application",
            icon_name="application-x-executable",
            action=lambda: None,
        )
        file_a = SearchItem(
            title="ceo_of_google.png",
            subtitle="/home/me/ceo_of_google.png",
            path="/home/me/ceo_of_google.png",
            action=lambda: None,
        )
        web = SearchItem(
            title='Search Google for "ceo of google"',
            subtitle="https://google.com",
            icon_name="system-search",
            action=lambda: None,
        )
        merged = merge_ranked_results(
            [app, web],
            [file_a],
            answer,
            "ceo of google",
            10,
        )
        self.assertEqual([item.title for item in merged[:3]], ["AI", "Firefox", "ceo_of_google.png"])
        self.assertEqual(merged[-1].title, 'Search Google for "ceo of google"')

    def test_duplicate_paths_are_deduped(self) -> None:
        duplicate = SearchItem(
            title="readme.md",
            subtitle="/home/me/readme.md",
            path="/home/me/readme.md",
            action=lambda: None,
        )
        merged = merge_ranked_results([], [duplicate, duplicate], None, "readme", 10)
        self.assertEqual(len(merged), 1)


class CancellationTests(unittest.TestCase):
    def test_stream_stops_when_cancelled(self) -> None:
        cancel = Event()
        cancel.set()
        response = [
            b'data: {"type":"response.output_text.delta","delta":"Partial answer"}\n',
        ]

        with self.assertRaises(RequestCancelled):
            _read_stream(response, lambda _text: None, cancel)


if __name__ == "__main__":
    unittest.main()
