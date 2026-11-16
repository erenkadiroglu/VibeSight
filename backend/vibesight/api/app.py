"""FastAPI uygulaması: REST uç noktaları + canlı WebSocket.

WebSocket ikili mesaj biçimi (görüntü ve metrikler birebir senkron):
    [4 bayt big-endian uint32: JSON uzunluğu][UTF-8 JSON][JPEG baytları (opsiyonel)]
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vibesight import __version__
from vibesight.analytics.affect import CIRCUMPLEX, LABELS_TR
from vibesight.config import Settings, get_settings
from vibesight.engine import BaseEngine, create_engine
from vibesight.storage.history import History
from vibesight.vision.emotion import FERPLUS_LABELS

log = logging.getLogger(__name__)


def _label_order(key: str) -> int:
    return FERPLUS_LABELS.index(key) if key in FERPLUS_LABELS else len(FERPLUS_LABELS)


FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


class SettingsPatch(BaseModel):
    privacy_blur: bool | None = None


def pack(meta: dict[str, Any], jpeg: bytes | None) -> bytes:
    body = json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body + (jpeg or b"")


def create_app(settings: Settings | None = None, engine: BaseEngine | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        history = History(settings.db_path, settings.history_retention_days)
        eng = engine or create_engine(settings, history)
        eng.history = eng.history or history
        eng.start()
        app.state.engine = eng
        app.state.history = history
        log.info("VibeSight %s hazır — mod: %s", __version__, eng.mode)
        try:
            yield
        finally:
            eng.stop()
            history.close()

    app = FastAPI(title="VibeSight API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )

    def eng() -> BaseEngine:
        return app.state.engine

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return eng().status()

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        labels = eng().labels
        return {
            "version": __version__,
            "labels": [  # arayüzde her modelde aynı sırada görünsün
                {
                    "key": k,
                    "label": LABELS_TR.get(k, k),
                    "valence": CIRCUMPLEX.get(k, (0, 0))[0],
                    "arousal": CIRCUMPLEX.get(k, (0, 0))[1],
                }
                for k in sorted(labels, key=_label_order)
            ],
            "analysis_hz": settings.analysis_hz,
            "history_interval_s": settings.history_interval_s,
        }

    @app.get("/api/snapshot")
    def snapshot() -> dict[str, Any] | None:
        return eng().snapshot()

    @app.get("/api/history")
    def history(minutes: float = Query(10, gt=0, le=60 * 24 * 7)) -> list[dict[str, Any]]:
        return app.state.history.since(minutes * 60)

    @app.patch("/api/settings")
    def patch_settings(patch: SettingsPatch) -> dict[str, Any]:
        if patch.privacy_blur is not None:
            eng().privacy_blur = patch.privacy_blur
        return eng().status()

    @app.websocket("/ws/live")
    async def live(ws: WebSocket) -> None:
        await ws.accept()
        interval = 1.0 / settings.stream_fps
        last_frame = last_snap_t = -1.0
        status_every, tick = int(settings.stream_fps), 0
        try:
            while True:
                e = eng()
                frame, snap = e.frame(), e.snapshot()
                new_frame = frame is not None and frame.index != last_frame
                new_snap = snap is not None and snap["t"] != last_snap_t
                if new_frame or new_snap:
                    meta: dict[str, Any] = {"type": "tick"}
                    if new_snap:
                        meta["snapshot"] = snap
                        last_snap_t = snap["t"]  # type: ignore[index]
                    if new_frame:
                        meta["frame"] = {"w": frame.width, "h": frame.height, "t": frame.timestamp}  # type: ignore[union-attr]
                        last_frame = frame.index  # type: ignore[union-attr]
                    if tick % status_every == 0:
                        meta["status"] = e.status()
                    tick += 1
                    await ws.send_bytes(pack(meta, frame.jpeg if new_frame else None))  # type: ignore[union-attr]
                await asyncio.sleep(interval)
        except (WebSocketDisconnect, RuntimeError):
            return

    if FRONTEND_DIST.exists():  # üretim: derlenmiş arayüzü aynı porttan sun
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            target = FRONTEND_DIST / path
            return FileResponse(target if path and target.is_file() else FRONTEND_DIST / "index.html")

    return app
