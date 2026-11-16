import json
import struct
import time
from pathlib import Path

from fastapi.testclient import TestClient

from vibesight.api.app import create_app
from vibesight.config import Settings, redact


def test_mock_engine_end_to_end(tmp_path: Path) -> None:
    settings = Settings(source="mock", db_path=tmp_path / "t.db", history_interval_s=0.2)
    with TestClient(create_app(settings)) as client:
        time.sleep(1.0)
        assert client.get("/api/health").json()["ok"]
        assert client.get("/api/status").json()["mode"] == "mock"
        assert len(client.get("/api/meta").json()["labels"]) == 8
        snap = client.get("/api/snapshot").json()
        assert snap["count"] > 0
        assert client.get("/api/history", params={"minutes": 1}).json()
        assert client.patch("/api/settings", json={"privacy_blur": True}).json()["privacy_blur"] is True

        with client.websocket_connect("/ws/live") as ws:
            msg = ws.receive_bytes()
            n = struct.unpack(">I", msg[:4])[0]
            meta = json.loads(msg[4 : 4 + n])
            assert meta["type"] == "tick"
            if "frame" in meta:
                assert msg[4 + n : 4 + n + 2] == b"\xff\xd8"  # JPEG başlangıcı


def test_tapo_url_is_built_and_redacted() -> None:
    s = Settings(source="tapo", tapo_host="10.0.0.5", tapo_user="eren", tapo_password="p@ss:1")
    url = s.resolved_source()
    assert url == "rtsp://eren:p%40ss%3A1@10.0.0.5:554/stream1"
    assert redact(url) == "rtsp://***:***@10.0.0.5:554/stream1"


def test_mock_people_never_share_a_seat(tmp_path: Path) -> None:
    from vibesight.engine import MockEngine

    engine = MockEngine(Settings(source="mock", db_path=tmp_path / "t.db"))
    for k in range(3000):  # ~8 dakikalık simülasyon: kişiler girip çıkar
        engine._step(1_000.0 + k / 6)
        slots = [a["slot"] for a in engine._agents]
        assert len(slots) == len(set(slots))


def test_history_migrates_old_database(tmp_path: Path) -> None:
    """Eski sürümle oluşturulmuş (katılım sütunu olmayan) veritabanı sorunsuz yükseltilir."""
    import sqlite3

    from vibesight.storage.history import History

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE room_metrics (t REAL PRIMARY KEY, count INTEGER NOT NULL, faces INTEGER NOT NULL, "
        "energy REAL, attention REAL, valence REAL, arousal REAL, perclos REAL, activity REAL, "
        "atmosphere TEXT, emotions TEXT)"
    )
    con.execute("INSERT INTO room_metrics VALUES (1, 3, 2, 50, 0.5, 0, 0, 0.1, 10, 'calm', NULL)")
    con.commit()
    con.close()
    h = History(db)
    snap = {
        "t": 2.0,
        "count": 4,
        "faces_analyzed": 4,
        "energy": 60.0,
        "attention": 0.7,
        "valence": 0.1,
        "arousal": 0.2,
        "perclos": 0.05,
        "activity": 20.0,
        "atmosphere": {"key": "focused"},
        "emotions": None,
        "engagement": 0.8,
    }
    h.add(snap)
    rows = h.since(10, now=5)
    assert [r["count"] for r in rows] == [3, 4]
    assert rows[0]["engagement"] is None and rows[1]["engagement"] == 0.8
