"""Linux filename index detection and setup guidance."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileIndexStatus:
    backend: str
    available: bool
    database_exists: bool
    hint: str


def _database_exists() -> bool:
    candidates = (
        Path("/var/lib/plocate/plocate.db"),
        Path("/var/lib/mlocate/mlocate.db"),
    )
    return any(path.exists() for path in candidates)


def file_index_status() -> FileIndexStatus:
    if shutil.which("plocate"):
        db_exists = _database_exists()
        if db_exists:
            return FileIndexStatus(
                backend="plocate",
                available=True,
                database_exists=True,
                hint="Using system plocate index for fast file search.",
            )
        return FileIndexStatus(
            backend="plocate",
            available=True,
            database_exists=False,
            hint="plocate is installed but the index is missing. Run: sudo updatedb",
        )
    if shutil.which("locate"):
        db_exists = _database_exists()
        return FileIndexStatus(
            backend="locate",
            available=True,
            database_exists=db_exists,
            hint=(
                "Using locate index."
                if db_exists
                else "locate is installed but the index is missing. Run: sudo updatedb"
            ),
        )
    return FileIndexStatus(
        backend="none",
        available=False,
        database_exists=False,
        hint=(
            "Optional: install plocate for Raycast-like speed — "
            "sudo apt install plocate && sudo updatedb"
        ),
    )


def refresh_file_index() -> tuple[bool, str]:
    status = file_index_status()
    if not status.available:
        return False, status.hint
    if not shutil.which("updatedb"):
        return False, "updatedb is not available on this system."
    try:
        subprocess.run(["updatedb"], check=True, timeout=120)
    except subprocess.CalledProcessError:
        return False, "updatedb failed. Try: sudo updatedb"
    except (OSError, subprocess.TimeoutExpired):
        return False, "Could not refresh the file index."
    return True, "File index refreshed."
