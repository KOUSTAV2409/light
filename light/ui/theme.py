"""Built-in launcher themes inspired by Raycast and macOS Spotlight."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    id: str
    label: str
    background: str
    surface: str
    surface_elevated: str
    border: str
    text: str
    text_muted: str
    placeholder: str
    selection: str
    selection_text: str
    answer_surface: str
    answer_selection: str
    accent: str
    separator: str
    shadow: str
    radius: int
    entry_font_size: int
    title_font_size: int
    subtitle_font_size: int
    width: int
    search_height: int
    result_height: int


THEMES: dict[str, ThemeTokens] = {
    "raycast": ThemeTokens(
        id="raycast",
        label="Raycast Dark",
        background="rgba(0,0,0,0)",
        surface="#1C1C1E",
        surface_elevated="#2C2C2E",
        border="rgba(255,255,255,0.09)",
        text="#F5F5F7",
        text_muted="rgba(245,245,247,0.55)",
        placeholder="rgba(245,245,247,0.36)",
        selection="#FF6363",
        selection_text="#FFFFFF",
        answer_surface="#252528",
        answer_selection="#3A3A3C",
        accent="#FF6363",
        separator="rgba(255,255,255,0.08)",
        shadow="rgba(0,0,0,0.55)",
        radius=16,
        entry_font_size=20,
        title_font_size=15,
        subtitle_font_size=12,
        width=680,
        search_height=56,
        result_height=50,
    ),
    "spotlight": ThemeTokens(
        id="spotlight",
        label="Spotlight Light",
        background="rgba(0,0,0,0)",
        surface="#F5F5F7",
        surface_elevated="#FFFFFF",
        border="rgba(0,0,0,0.08)",
        text="#1D1D1F",
        text_muted="rgba(29,29,31,0.52)",
        placeholder="rgba(29,29,31,0.34)",
        selection="#007AFF",
        selection_text="#FFFFFF",
        answer_surface="#FFFFFF",
        answer_selection="#E8F1FF",
        accent="#007AFF",
        separator="rgba(0,0,0,0.08)",
        shadow="rgba(0,0,0,0.22)",
        radius=14,
        entry_font_size=20,
        title_font_size=15,
        subtitle_font_size=12,
        width=680,
        search_height=56,
        result_height=50,
    ),
    "dracula": ThemeTokens(
        id="dracula",
        label="Dracula",
        background="rgba(0,0,0,0)",
        surface="#282A36",
        surface_elevated="#343746",
        border="rgba(248,248,242,0.12)",
        text="#F8F8F2",
        text_muted="rgba(248,248,242,0.62)",
        placeholder="rgba(248,248,242,0.4)",
        selection="#BD93F9",
        selection_text="#282A36",
        answer_surface="#343746",
        answer_selection="#44475A",
        accent="#FF79C6",
        separator="rgba(248,248,242,0.12)",
        shadow="rgba(0,0,0,0.45)",
        radius=14,
        entry_font_size=18,
        title_font_size=15,
        subtitle_font_size=12,
        width=680,
        search_height=56,
        result_height=50,
    ),
}


def resolve_theme(theme_id: str) -> ThemeTokens:
    return THEMES.get(theme_id, THEMES["raycast"])


def apply_theme_to_config(config, theme: ThemeTokens) -> None:
    """Sync layout + legacy color fields from a theme preset."""
    config.background_color = theme.surface
    config.text_color = theme.text
    config.selected_item_background_color = theme.selection
    config.answer_background_color = theme.answer_surface
    config.answer_selected_background_color = theme.answer_selection
    config.maximum_width = theme.width
    config.search_bar_height = theme.search_height
    config.result_item_height = theme.result_height


def build_launcher_css(theme: ThemeTokens) -> str:
    radius = theme.radius
    return f"""
    window.light-launcher {{
        background-color: {theme.background};
    }}
    .launcher-frame {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {radius}px;
        box-shadow: 0 22px 60px {theme.shadow}, 0 2px 8px rgba(0,0,0,0.12);
    }}
    .search-header {{
        background-color: {theme.surface};
        border-top-left-radius: {radius}px;
        border-top-right-radius: {radius}px;
        min-height: {theme.search_height}px;
        padding: 2px 4px 2px 4px;
    }}
    .search-header.collapsed {{
        border-radius: {radius}px;
    }}
    entry.search-entry {{
        background-color: transparent;
        background-image: none;
        color: {theme.text};
        border: none;
        box-shadow: none;
        outline: none;
        padding: 12px 10px 12px 4px;
        font-size: {theme.entry_font_size}px;
        font-weight: 500;
        caret-color: {theme.accent};
        min-height: {theme.search_height - 8}px;
    }}
    entry.search-entry:focus {{
        background-color: transparent;
        border: none;
        box-shadow: none;
        outline: none;
    }}
    entry.search-entry selection {{
        background-color: {theme.accent};
        color: {theme.selection_text};
    }}
    entry.search-entry placeholder {{
        color: {theme.placeholder};
        font-weight: 400;
    }}
    .search-icon {{
        color: {theme.text_muted};
        margin-left: 14px;
        margin-right: 4px;
    }}
    .results-panel {{
        background-color: {theme.surface};
        border-bottom-left-radius: {radius}px;
        border-bottom-right-radius: {radius}px;
        padding: 2px 6px 6px 6px;
    }}
    .results-separator {{
        background-color: {theme.separator};
        min-height: 1px;
        margin: 0 12px 6px 12px;
    }}
    .result-row {{
        background-color: transparent;
        border-radius: 10px;
        padding: 0;
        margin: 1px 4px;
    }}
    .result-row:hover {{
        background-color: {theme.surface_elevated};
    }}
    .result-row.selected {{
        background-color: {theme.selection};
    }}
    .result-row.selected:hover {{
        background-color: {theme.selection};
    }}
    .result-row.selected .result-title,
    .result-row.selected .result-subtitle {{
        color: {theme.selection_text};
        opacity: 1;
    }}
    .result-row.selected .result-subtitle {{
        opacity: 0.88;
    }}
    .answer-row {{
        background-color: {theme.answer_surface};
        border: 1px solid {theme.border};
        border-radius: 12px;
        padding: 0;
        margin: 2px 4px 6px 4px;
    }}
    .answer-row:hover {{
        border-color: {theme.accent};
    }}
    .answer-row.selected {{
        background-color: {theme.answer_selection};
        border-color: {theme.accent};
    }}
    .answer-body {{
        font-size: 14px;
        color: {theme.text};
    }}
    .answer-row.selected .answer-body {{
        color: {theme.text};
    }}
    .answer-source {{
        font-size: 11px;
        color: {theme.text_muted};
        margin-top: 4px;
    }}
    .result-title {{
        font-size: {theme.title_font_size}px;
        font-weight: 600;
        color: {theme.text};
    }}
    .result-subtitle {{
        font-size: {theme.subtitle_font_size}px;
        color: {theme.text_muted};
    }}
    .result-icon {{
        margin-right: 12px;
        margin-left: 2px;
    }}
    .result-inner {{
        padding: 7px 12px;
        min-height: {theme.result_height - 2}px;
    }}
    .answer-inner {{
        padding: 10px 14px 12px 14px;
    }}
    .footer-hint {{
        font-size: 11px;
        color: {theme.text_muted};
        padding: 6px 14px 8px 14px;
    }}
    """
