"""Yalnızca **oda düzeyindeki toplu** metriklerin SQLite zaman serisi. Görüntü veya kişi verisi saklanmaz."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS room_metrics (
    t           REAL PRIMARY KEY,
    count       INTEGER NOT NULL,
    faces       INTEGER NOT NULL,
    energy      REAL,
    attention   REAL,
    valence     REAL,
    arousal     REAL,
    perclos     REAL,
    activity    REAL,
    atmosphere  TEXT,
    emotions    TEXT
);
"""

FIELDS = (
    "t",
    "count",
    "faces",
    "energy",
    "attention",
    "valence",
    "arousal",
    "perclos",
    "activity",
    "atmosphere",
    "emotions",
)


class History:
    def __init__(self, path: Path, retention_days: int = 30) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()
        self.retention_s = retention_days * 86400
        self._last_prune = 0.0

    def add(self, snap: dict[str, Any]) -> None:
        row = (
            snap["t"],
            snap["count"],
            snap["faces_analyzed"],
            snap["energy"],
            snap["attention"],
            snap["valence"],
            snap["arousal"],
            snap["perclos"],
            snap["activity"],
            snap["atmosphere"]["key"],
            json.dumps(snap["emotions"]) if snap["emotions"] else None,
        )
        with self._lock:
            self._db.execute(
                f"INSERT OR REPLACE INTO room_metrics VALUES ({','.join('?' * len(FIELDS))})", row
            )
            if snap["t"] - self._last_prune > 3600:
                self._db.execute("DELETE FROM room_metrics WHERE t < ?", (snap["t"] - self.retention_s,))
                self._last_prune = snap["t"]
            self._db.commit()

    def since(self, seconds: float, now: float | None = None) -> list[dict[str, Any]]:
        start = (now or time.time()) - seconds
        with self._lock:
            rows = self._db.execute("SELECT * FROM room_metrics WHERE t >= ? ORDER BY t", (start,)).fetchall()
        out = []
        for r in rows:
            item = dict(zip(FIELDS, r, strict=True))
            item["emotions"] = json.loads(item["emotions"]) if item["emotions"] else None
            out.append(item)
        return out

    def close(self) -> None:
        with self._lock:
            self._db.close()
