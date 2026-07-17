"""Configuration — ported from Snap/Configuration.swift."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


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
    background_color: str = "#282A36"
    text_color: str = "#F8F8F2"
    selected_item_background_color: str = "#FF79C6"
    maximum_width: int = 775
    maximum_height: int = 600
    search_bar_height: int = 50
    result_item_height: int = 48
    result_item_limit: int = 25
    search_paths: list[str] = field(default_factory=lambda: ["~"])
    blocked_paths: list[str] = field(default_factory=list)
    activation_hotkey: str = "alt+space"
    default_search_engine: str = "google"
    show_icons: bool = True

    # OpenAI instant answers (web-grounded)
    openai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_web_search: bool = True

    @classmethod
    def load(cls) -> Configuration:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if not CONFIG_PATH.exists():
            shutil.copy(BUNDLED_DEFAULT, CONFIG_PATH)

        with CONFIG_PATH.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        defaults = {item.name: getattr(cls(), item.name) for item in fields(cls)}
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return cls(**defaults)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def secrets_path(self) -> Path:
        return SECRETS_PATH

    def expanded_search_paths(self) -> list[Path]:
        paths: list[Path] = []
        for raw in self.search_paths:
            paths.append(Path(os.path.expanduser(raw)).resolve())
        return paths
