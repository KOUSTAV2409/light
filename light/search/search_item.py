"""SearchItem protocol — mirrors Snap/Search/SearchItem.swift."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID, uuid4


@dataclass
class SearchItem:
    title: str
    action: Callable[[], None]
    subtitle: str = ""
    icon_name: str = "text-x-generic"
    keywords: list[str] = field(default_factory=list)
    accepts_arguments: bool = False
    path: str = ""
    is_instant_answer: bool = False
    answer_text: str = ""
    source_urls: list[str] = field(default_factory=list)
    is_loading: bool = False
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.keywords:
            self.keywords = [self.title]
