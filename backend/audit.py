"""Append-only audit trail: output/audit_trail.json.

The file is a JSON array. Every agent-loop step adds one AuditEntry to the end; earlier
entries are never removed or rewritten, so the trail survives across runs. Writes go to a
temp file first and then replace the original, so a crash can't leave half-written JSON.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from models import AuditEntry

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_FIELD_CHARS = 2000  # long tool outputs are cut so the trail stays readable

_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def clip(text: str | None, limit: int = MAX_FIELD_CHARS) -> str | None:
    if text is None or len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated {len(text) - limit} chars]"


def append(entry: AuditEntry, path: Path = AUDIT_PATH) -> None:
    """Add one entry to the end of the trail (never wipes existing entries)."""
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if path.exists() and path.stat().st_size:
            entries = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                raise ValueError(f"{path} is not a JSON array; refusing to overwrite it.")
        entries.append(entry.model_dump(mode="json", exclude_none=True))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=1, ensure_ascii=False), encoding="utf-8")
        _replace(tmp, path)


def _replace(tmp: Path, path: Path) -> None:
    """os.replace, retried briefly: OneDrive or an editor can hold the file for a moment."""
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    path.write_bytes(tmp.read_bytes())  # last resort: overwrite in place (content is the full array)
    tmp.unlink(missing_ok=True)
