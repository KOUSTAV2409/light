"""Configuration — ported from Snap/Configuration.swift."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


CONFIG_DIR = _xdg_config_home() / "light"
DATA_DIR = _xdg_data_home() / "light"
CONFIG_PATH = CONFIG_DIR / "configuration.json"
SECRETS_PATH = CONFIG_DIR / "secrets.json"
BUNDLED_DEFAULT = Path(__file__).with_name("default_configuration.json")


@dataclass
class Configuration:
    theme: str = "raycast"
    background_color: str = "#1C1C1E"
    text_color: str = "#F5F5F7"
    selected_item_background_color: str = "#FF6363"
    answer_background_color: str = "#252528"
    answer_selected_background_color: str = "#3A3A3C"
    maximum_width: int = 680
    maximum_height: int = 560
    search_bar_height: int = 58
    result_item_height: int = 52
    result_item_limit: int = 25
    search_paths: list[str] = field(default_factory=lambda: ["~"])
    blocked_paths: list[str] = field(default_factory=list)
    activation_hotkey: str = "alt+space"
    default_search_engine: str = "google"
    show_icons: bool = True
    show_keyboard_hints: bool = True

    # OpenAI instant answers (web-grounded)
    openai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_web_search: bool = True

    # Local productivity features
    clipboard_history_enabled: bool = False
    clipboard_history_limit: int = 50
    extensions_enabled: bool = True
    usage_metrics_enabled: bool = False

    @classmethod
    def load(cls) -> Configuration:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_DIR.chmod(0o700)
        except OSError:
            pass

        if not CONFIG_PATH.exists():
            try:
                shutil.copy(BUNDLED_DEFAULT, CONFIG_PATH)
            except OSError:
                return cls()

        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            broken = CONFIG_PATH.with_suffix(".json.broken")
            try:
                CONFIG_PATH.replace(broken)
            except OSError:
                pass
            return cls()

        if not isinstance(data, dict):
            return cls()

        defaults = {item.name: getattr(cls(), item.name) for item in fields(cls)}
        for key, value in data.items():
            if key not in defaults:
                continue
            expected = type(defaults[key])
            if expected is type(None) or isinstance(value, expected):
                defaults[key] = value
        # API keys belong in secrets/env, never in the persisted config object.
        defaults["openai_api_key"] = ""
        return cls(**defaults)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload.pop("openai_api_key", None)
        temporary = CONFIG_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(CONFIG_PATH)

    def secrets_path(self) -> Path:
        return SECRETS_PATH

    def expanded_search_paths(self) -> list[Path]:
        paths: list[Path] = []
        for raw in self.search_paths:
            paths.append(Path(os.path.expanduser(raw)).resolve())
        return paths
