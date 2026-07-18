from __future__ import annotations

import unittest

from light.configuration.configuration import Configuration
from light.ui.theme import THEMES, apply_theme_to_config, build_launcher_css, resolve_theme


class ThemeTests(unittest.TestCase):
    def test_default_theme_is_raycast(self) -> None:
        theme = resolve_theme("missing")
        self.assertEqual(theme.id, "raycast")

    def test_css_contains_rounded_frame(self) -> None:
        for theme_id in THEMES:
            css = build_launcher_css(resolve_theme(theme_id))
            self.assertIn("launcher-frame", css)
            self.assertIn("border-radius", css)
            self.assertIn("search-entry", css)
            self.assertIn("result-row:hover", css)

    def test_apply_theme_syncs_layout(self) -> None:
        config = Configuration()
        config.maximum_width = 900
        apply_theme_to_config(config, resolve_theme("raycast"))
        self.assertEqual(config.maximum_width, 680)
        self.assertEqual(config.search_bar_height, 56)
        self.assertEqual(config.selected_item_background_color, "#FF6363")


if __name__ == "__main__":
    unittest.main()
