"""
Thread-safe JSON file storage for the Finalytics backend.

The MVP persists data to JSON files. A process-wide lock serializes
read-modify-write cycles so concurrent requests cannot corrupt files
(a defect flagged in the code audit).
"""
import json
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.RLock()


def _path(name: str) -> Path:
    return DATA_DIR / name


def read_json(name: str, default: Any):
    """Read a JSON file, returning ``default`` if it does not exist."""
    with _lock:
        path = _path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default


def write_json(name: str, data: Any) -> None:
    """Atomically write a JSON file (write to temp, then replace)."""
    with _lock:
        path = _path(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp.replace(path)


def update_json(name: str, default: Any, mutator) -> Any:
    """
    Read-modify-write under a single lock.

    ``mutator`` receives the current data and must return the new data
    to persist. Returns the persisted data.
    """
    with _lock:
        data = read_json(name, default)
        new_data = mutator(data)
        write_json(name, new_data)
        return new_data
