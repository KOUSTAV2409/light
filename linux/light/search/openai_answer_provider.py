"""OpenAI Answers API with web search — Google-like current answers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ..configuration.configuration import Configuration

_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_TIMEOUT = 25

_SYSTEM_PROMPT = """You are Light, a fast launcher assistant.
Answer the user's question directly in 2-3 short sentences.
Lead with the key fact or person/name when relevant.
Prefer current public web information for people, companies, news, and roles that change over time.
If sources disagree or you are unsure, say so briefly.
Do not use markdown headings or bullet lists.
Plain text only."""


@dataclass
class OpenAIAnswer:
    title: str
    answer: str
    source_url: str


def resolve_openai_api_key(config: Configuration) -> str:
    """Prefer env, then secrets file, then configuration.json."""
    placeholders = {"", "PASTE_YOUR_OPENAI_API_KEY_HERE"}

    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key not in placeholders:
        return env_key

    secrets_path = config.secrets_path()
    if secrets_path.exists():
        try:
            data = json.loads(secrets_path.read_text(encoding="utf-8"))
            key = str(data.get("openai_api_key", "")).strip()
            if key not in placeholders:
                return key
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    config_key = (config.openai_api_key or "").strip()
    return "" if config_key in placeholders else config_key


def _extract_output_text(payload: dict) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") in ("output_text", "text") and part.get("text"):
                chunks.append(str(part["text"]))
    return "\n".join(chunks).strip()


def _extract_source_url(payload: dict) -> str:
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            if isinstance(action, dict):
                for source in action.get("sources", []) or []:
                    if isinstance(source, dict) and source.get("url"):
                        return str(source["url"])
        if item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if not isinstance(part, dict):
                continue
            for annotation in part.get("annotations", []) or []:
                if not isinstance(annotation, dict):
                    continue
                url = annotation.get("url") or annotation.get("href")
                if url:
                    return str(url)
    return ""


def _title_from_answer(query: str, answer: str) -> str:
    first_line = answer.split("\n", 1)[0].strip()
    if "." in first_line:
        head = first_line.split(".", 1)[0].strip()
        if 3 <= len(head) <= 80:
            return head
    if len(first_line) <= 80:
        return first_line or query
    return first_line[:77].rstrip() + "…"


def fetch_openai_answer(query: str, config: Configuration) -> OpenAIAnswer | None:
    api_key = resolve_openai_api_key(config)
    if not api_key or not config.openai_enabled:
        return None

    tools: list[dict] = []
    tool_choice: str | dict = "auto"
    if config.openai_web_search:
        tools.append({"type": "web_search"})
        tool_choice = "required"

    body: dict = {
        "model": config.openai_model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": _SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": query.strip()}],
            },
        ],
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice

    request = urllib.request.Request(
        _OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LightLauncher/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail[:300]}") from exc
    except Exception as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    answer = _extract_output_text(payload)
    if not answer:
        return None

    source_url = _extract_source_url(payload)
    if not source_url:
        source_url = "https://www.google.com/search?q=" + urllib.parse.quote(query)

    return OpenAIAnswer(
        title=_title_from_answer(query, answer),
        answer=answer,
        source_url=source_url,
    )
