from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from light.clipboard.history import ClipboardHistory
from light.extensions.registry import ExtensionManifest, ExtensionRegistry
from light.metrics import UsageMetrics
from light.search.clipboard_provider import ClipboardSearch


class ProductFeatureTests(unittest.TestCase):
    def test_clipboard_history_deduplicates_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            history = ClipboardHistory(2, Path(directory) / "history.json")
            history.add("first")
            history.add("second")
            history.add("first")
            history.add("third")
            self.assertEqual(
                [entry.text for entry in history.load()],
                ["third", "first"],
            )

    def test_clipboard_search_does_not_match_normal_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            history = ClipboardHistory(10, Path(directory) / "history.json")
            history.add("release notes")
            provider = ClipboardSearch(history, lambda _text: None)
            self.assertEqual(provider.search("release", 10), [])
            self.assertEqual(
                [item.title for item in provider.search("clipboard release", 10)],
                ["release notes"],
            )

    def test_extension_manifest_requires_command_array(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "id": "unsafe",
                        "name": "Unsafe",
                        "prefix": "u",
                        "command": "echo unsafe",
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(ExtensionManifest.from_file(path))

    def test_extension_registry_loads_valid_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension_dir = root / "example"
            extension_dir.mkdir()
            (extension_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "example",
                        "name": "Example Extension",
                        "prefix": "ex",
                        "command": ["/bin/echo"],
                    }
                ),
                encoding="utf-8",
            )
            registry = ExtensionRegistry(root)
            items = registry.search("ex hello", 10)
            self.assertEqual(items[0].title, "Example Extension: hello")

    def test_metrics_never_store_query_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            metrics = UsageMetrics(True, path)
            metrics.record("search")
            stored = path.read_text(encoding="utf-8")
            self.assertIn('"search": 1', stored)
            self.assertNotIn("private query", stored)

    def test_disabled_metrics_do_not_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            UsageMetrics(False, path).record("launch")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
