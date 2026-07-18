from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from light.search.application_provider import (
    ApplicationDefinition,
    ApplicationSearch,
    _launch_arguments,
    _read_desktop_entry,
)


class ApplicationProviderTests(unittest.TestCase):
    def test_exec_field_codes_are_removed(self) -> None:
        self.assertEqual(
            _launch_arguments("code --new-window %F"),
            ["code", "--new-window"],
        )

    def test_embedded_field_code_is_removed(self) -> None:
        self.assertEqual(
            _launch_arguments("browser --url=%u"),
            ["browser", "--url="],
        )

    def test_visible_desktop_entry_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.desktop"
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Example Browser\n"
                "Comment=Browse the web\n"
                "Exec=example-browser %U\n"
                "Icon=example-browser\n"
                "Keywords=web;internet;\n",
                encoding="utf-8",
            )

            result = _read_desktop_entry(path)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "Example Browser")
        self.assertEqual(result.keywords, ("web", "internet"))

    def test_malformed_boolean_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.desktop"
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Broken\n"
                "Exec=broken\n"
                "Hidden=maybe\n",
                encoding="utf-8",
            )
            self.assertIsNone(_read_desktop_entry(path))

    def test_exact_application_name_ranks_first(self) -> None:
        browser = ApplicationDefinition(
            desktop_id="browser.desktop",
            name="Browser",
            exec_line="browser",
            icon_name="browser",
            keywords=("web",),
        )
        browser_beta = ApplicationDefinition(
            desktop_id="browser-beta.desktop",
            name="Browser Beta",
            exec_line="browser-beta",
            icon_name="browser",
            keywords=("web",),
        )
        with patch(
            "light.search.application_provider.load_applications",
            return_value=[browser_beta, browser],
        ):
            provider = ApplicationSearch()

        results = provider.search("Browser", limit=10)
        self.assertEqual([item.title for item in results], ["Browser", "Browser Beta"])

    def test_only_show_in_respects_current_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gnome.desktop"
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=GNOME Tool\n"
                "Exec=gnome-tool\n"
                "OnlyShowIn=GNOME;\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}):
                self.assertIsNone(_read_desktop_entry(path))


if __name__ == "__main__":
    unittest.main()
