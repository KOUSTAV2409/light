from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from light.configuration import configuration
from light.search.openai_answer_provider import resolve_openai_api_key


class ConfigurationTests(unittest.TestCase):
    def test_old_configuration_receives_new_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "configuration.json"
            config_path.write_text(
                json.dumps({"background_color": "#000000"}),
                encoding="utf-8",
            )
            with (
                patch.object(configuration, "CONFIG_DIR", root),
                patch.object(configuration, "DATA_DIR", root / "data"),
                patch.object(configuration, "CONFIG_PATH", config_path),
                patch.object(configuration, "SECRETS_PATH", root / "secrets.json"),
            ):
                loaded = configuration.Configuration.load()

        self.assertEqual(loaded.background_color, "#000000")
        self.assertEqual(loaded.openai_model, "gpt-4o")
        self.assertTrue(loaded.openai_web_search)

    def test_unknown_keys_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "configuration.json"
            config_path.write_text(
                json.dumps({"unknown_future_key": True}),
                encoding="utf-8",
            )
            with (
                patch.object(configuration, "CONFIG_DIR", root),
                patch.object(configuration, "DATA_DIR", root / "data"),
                patch.object(configuration, "CONFIG_PATH", config_path),
                patch.object(configuration, "SECRETS_PATH", root / "secrets.json"),
            ):
                loaded = configuration.Configuration.load()

        self.assertEqual(loaded.default_search_engine, "google")

    def test_api_key_placeholder_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secrets_path = Path(directory) / "secrets.json"
            secrets_path.write_text(
                json.dumps({"openai_api_key": "PASTE_YOUR_OPENAI_API_KEY_HERE"}),
                encoding="utf-8",
            )
            config = configuration.Configuration(openai_enabled=True)
            with patch.object(config, "secrets_path", return_value=secrets_path):
                with patch.dict("os.environ", {}, clear=True):
                    self.assertEqual(resolve_openai_api_key(config), "")

    def test_save_never_writes_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "configuration.json"
            config = configuration.Configuration(openai_api_key="sk-should-not-persist")
            with (
                patch.object(configuration, "CONFIG_DIR", root),
                patch.object(configuration, "CONFIG_PATH", config_path),
            ):
                config.save()

            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("openai_api_key", saved)

    def test_invalid_json_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "configuration.json"
            config_path.write_text("{not-json", encoding="utf-8")
            with (
                patch.object(configuration, "CONFIG_DIR", root),
                patch.object(configuration, "DATA_DIR", root / "data"),
                patch.object(configuration, "CONFIG_PATH", config_path),
                patch.object(configuration, "SECRETS_PATH", root / "secrets.json"),
            ):
                loaded = configuration.Configuration.load()

        self.assertEqual(loaded.default_search_engine, "google")
        self.assertFalse(loaded.openai_enabled)


if __name__ == "__main__":
    unittest.main()
