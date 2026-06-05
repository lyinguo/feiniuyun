"""Per-user, per-thread memory persistence."""

from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
    return cleaned[:80] or "unknown"


def new_memory(user_id: str, thread_id: str, short_term_window: int) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "thread_id": thread_id,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "short_term": {
            "window_chapters": short_term_window,
            "recent_chapters": [],
        },
        "long_term": {
            "logline": "",
            "canon_facts": [],
            "characters": {},
            "locations": {},
            "unresolved_threads": [],
        },
    }


class MemoryStore:
    """JSON-backed memory store.

    The key point for this project is isolation: user_id and thread_id are part
    of the storage path so different authors and adaptation sessions never
    share memory by accident.
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or settings.memory_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def load(self, user_id: str, thread_id: str, short_term_window: int) -> Dict[str, Any]:
        path = self._path_for(user_id, thread_id)
        with self._lock:
            if not path.exists():
                return new_memory(user_id, thread_id, short_term_window)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                backup = path.with_suffix(".corrupt.json")
                path.replace(backup)
                return new_memory(user_id, thread_id, short_term_window)

        data.setdefault("short_term", {}).setdefault("recent_chapters", [])
        data.setdefault("short_term", {})["window_chapters"] = short_term_window
        data.setdefault("long_term", {}).setdefault("canon_facts", [])
        data.setdefault("long_term", {}).setdefault("characters", {})
        data.setdefault("long_term", {}).setdefault("locations", {})
        data.setdefault("long_term", {}).setdefault("unresolved_threads", [])
        return data

    def save(self, user_id: str, thread_id: str, memory: Dict[str, Any]) -> None:
        path = self._path_for(user_id, thread_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = deepcopy(memory)
        payload["updated_at"] = utc_now_iso()
        temp_path = path.with_suffix(".tmp")
        with self._lock:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, path)

    def clear(self, user_id: str, thread_id: str) -> bool:
        path = self._path_for(user_id, thread_id)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
        return False

    def snapshot(self, user_id: str, thread_id: str, short_term_window: int) -> Dict[str, Any]:
        return deepcopy(self.load(user_id, thread_id, short_term_window))

    def _path_for(self, user_id: str, thread_id: str) -> Path:
        user_part = safe_component(user_id)
        thread_part = safe_component(thread_id)
        return self.base_dir / user_part / f"{thread_part}.json"


memory_store = MemoryStore()
