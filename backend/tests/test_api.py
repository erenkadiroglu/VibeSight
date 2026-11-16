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
