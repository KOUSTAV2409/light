"""Privacy-safe, local-only product usage counters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .configuration.configuration import DATA_DIR


class UsageMetrics:
    """Count events without storing queries, clipboard text, paths, or answers."""

    def __init__(self, enabled: bool, path: Path | None = None) -> None:
        self.enabled = enabled
        self.path = path or DATA_DIR / "usage_metrics.json"

    def record(self, event: str) -> None:
        if not self.enabled:
            return
        data = self.load()
        today = datetime.now(timezone.utc).date().isoformat()
        data["events"][event] = int(data["events"].get(event, 0)) + 1
        data["active_days"][today] = int(data["active_days"].get(today, 0)) + 1
        self._write(data)

    def load(self) -> dict:
        base = {"schema_version": 1, "events": {}, "active_days": {}}
        if not self.path.exists():
            return base
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return base
        if not isinstance(raw, dict):
            return base
        events = raw.get("events", {})
        active_days = raw.get("active_days", {})
        base["events"] = events if isinstance(events, dict) else {}
        base["active_days"] = active_days if isinstance(active_days, dict) else {}
        return base

    def summary(self) -> str:
        data = self.load()
        events = data["events"]
        lines = [
            "Light local usage summary",
            f"Active days: {len(data['active_days'])}",
            f"Launches: {int(events.get('launch', 0))}",
            f"Searches: {int(events.get('search', 0))}",
            f"Activated results: {int(events.get('activate_result', 0))}",
        ]
        return "\n".join(lines)

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)


def main() -> None:
    print(UsageMetrics(enabled=False).summary())


if __name__ == "__main__":
    main()
