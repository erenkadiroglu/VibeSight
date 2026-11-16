"""Analiz motoru: kaynak → tespit → takip → yüz → ifade → oda metrikleri.

Üç iş parçacığı çalışır (ifade, yavaş kişi tespitini beklemez):
  * tespit döngüsü (`detect_hz`, ~6 Hz): kişi tespiti + takip (en pahalı adım)
  * analiz döngüsü (`analysis_hz`, ~15 Hz): takipçinin öngördüğü konumlarda yüz + ifade, oda anlık görüntüsü
  * yayın döngüsü (`stream_fps`): en son kareyi (gerekirse yüzleri bulanıklaştırarak) JPEG'e kodlar
WebSocket istemcileri yalnızca hazır sonuçları okur; istemci sayısı işlem yükünü artırmaz.
"""

from __future__ import annotations

import logging
import math
import os
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from vibesight.analytics.state import RoomAggregator
from vibesight.config import Settings
from vibesight.sources.capture import FrameSource, SourceStatus
from vibesight.storage.history import History
from vibesight.vision.emotion import FERPLUS_LABELS, EmotionClassifier

log = logging.getLogger(__name__)


@dataclass
class EncodedFrame:
    jpeg: bytes
    index: int
    width: int
    height: int
    timestamp: float


class RateMeter:
    def __init__(self, window: int = 30) -> None:
        self._t: deque[float] = deque(maxlen=window)

    def tick(self) -> None:
        self._t.append(time.monotonic())

    @property
    def rate(self) -> float:
        if len(self._t) < 2:
            return 0.0
        span = self._t[-1] - self._t[0]
        return (len(self._t) - 1) / span if span > 0 else 0.0


class BaseEngine:
    mode = "base"

    def __init__(self, settings: Settings, history: History | None = None) -> None:
        self.settings = settings
        self.history = history
        self.privacy_blur = settings.privacy_blur
        self.labels: list[str] = list(FERPLUS_LABELS)
        self._snapshot: dict[str, Any] | None = None
        self._frame: EncodedFrame | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.analysis_rate = RateMeter()
        self.stream_rate = RateMeter()
        self.latency_ms = 0.0
        self.timings_ms: dict[str, float] = {}  # aşama başına süre (performans teşhisi için)
        self._last_history = 0.0
        self.started_at = time.time()
        self.models: dict[str, dict[str, Any]] = {}

    # --- yaşam döngüsü -----------------------------------------------------------------------
    def start(self) -> None:
        for target, name in ((self._analysis_loop, "analysis"), (self._stream_loop, "stream")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=3)

    # --- okuma --------------------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return self._snapshot

    def frame(self) -> EncodedFrame | None:
        with self._lock:
            return self._frame

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source": {"label": "—", "kind": self.mode, "status": "live", "fps": 0.0, "resolution": None},
            "analysis_fps": round(self.analysis_rate.rate, 1),
            "stream_fps": round(self.stream_rate.rate, 1),
            "latency_ms": round(self.latency_ms, 1),
            "timings_ms": {k: round(v, 1) for k, v in self.timings_ms.items()},
            "privacy_blur": self.privacy_blur,
            "uptime_s": round(time.time() - self.started_at),
            "models": self.models,
        }

    # --- alt sınıflar --------------------------------------------------------------------------
    def _analysis_loop(self) -> None:
        raise NotImplementedError

    def _latest_image(self) -> tuple[np.ndarray, int, float] | None:
        raise NotImplementedError

    # --- ortak yardımcılar ----------------------------------------------------------------------
    def _publish(self, snap: dict[str, Any]) -> None:
        with self._lock:
            self._snapshot = snap
        self.analysis_rate.tick()
        if self.history and snap["t"] - self._last_history >= self.settings.history_interval_s:
            self._last_history = snap["t"]
            try:
                self.history.add(snap)
            except Exception:  # kayıt hatası canlı analizi durdurmamalı
                log.exception("Geçmişe yazılamadı")

    def _stream_loop(self) -> None:
        interval = 1.0 / self.settings.stream_fps
        last_index = -1
        while not self._stop.is_set():
            t0 = time.monotonic()
            latest = self._latest_image()
            if latest is not None and latest[1] != last_index:
                img, last_index, ts = latest
                if img.shape[1] > self.settings.stream_width:
                    s = self.settings.stream_width / img.shape[1]
                    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                else:
                    img = img.copy()
                if self.privacy_blur:
                    self._blur_faces(img)
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.settings.jpeg_quality])
                if ok:
                    with self._lock:
                        self._frame = EncodedFrame(buf.tobytes(), last_index, img.shape[1], img.shape[0], ts)
                    self.stream_rate.tick()
            self._stop.wait(max(0.0, interval - (time.monotonic() - t0)))

    def _blur_faces(self, img: np.ndarray) -> None:
        snap = self.snapshot()
        if not snap:
            return
        h, w = img.shape[:2]
        for p in snap["people"]:
            region = p.get("face")
            if region is None:  # yüz bulunamadıysa kişi kutusunun üst kısmını bulanıklaştır
                x1, y1, x2, y2 = p["box"]
                region = [x1, y1, x2, y1 + (y2 - y1) * 0.35]
            x1, y1, x2, y2 = region
            pad = 0.15 * (x2 - x1)
            xa, ya = max(0, int((x1 - pad) * w)), max(0, int((y1 - pad) * h))
            xb, yb = min(w, int((x2 + pad) * w)), min(h, int((y2 + pad) * h))
            if xb - xa > 2 and yb - ya > 2:
                roi = img[ya:yb, xa:xb]
                small = cv2.resize(roi, (max(1, (xb - xa) // 12), max(1, (yb - ya) // 12)))
                img[ya:yb, xa:xb] = cv2.resize(small, (xb - xa, yb - ya), interpolation=cv2.INTER_NEAREST)


class VisionEngine(BaseEngine):
    """Gerçek kamera/video ile çalışan motor."""

    mode = "live"

    def __init__(self, settings: Settings, history: History | None = None) -> None:
        super().__init__(settings, history)
        from vibesight.vision.detector import PersonDetector
        from vibesight.vision.face import FaceAnalyzer
        from vibesight.vision.motion import MotionMeter
        from vibesight.vision.tracker import Tracker

        det_path = settings.model_path(settings.detector_model)
        face_path = settings.model_path(settings.face_model)
        emo_path = settings.model_path(settings.emotion_model)
        for p in (det_path, face_path):
            if not p.exists():
                raise FileNotFoundError(f"Model bulunamadı: {p} — önce `make models` çalıştırın.")

        # İki döngü aynı anda çalıştığı için çekirdekleri paylaştır (aksi hâlde birbirlerini yavaşlatırlar)
        cpus = os.cpu_count() or 4
        det_threads = settings.onnx_threads or max(1, cpus // 2)
        emo_threads = settings.onnx_threads or max(1, cpus // 4)
        self.detector = PersonDetector(det_path, conf=settings.person_conf, threads=det_threads)
        self.face = FaceAnalyzer(face_path)
        self.emotion: EmotionClassifier | None = None
        if emo_path.exists():
            self.emotion = EmotionClassifier(emo_path, emo_threads)
            self.labels = self.emotion.labels
        else:
            log.warning("İfade modeli yok (%s); ifade analizi devre dışı.", emo_path.name)
        self.tracker = Tracker()
        self.motion = MotionMeter()
        self.aggregator = RoomAggregator(self.labels)
        self.source = FrameSource(settings.resolved_source())
        self._rr = 0  # çok kişi varsa yüz analizini döngüler arasında paylaştırmak için
        self._tracks_lock = threading.Lock()
        self._tracks: list[tuple[int, np.ndarray, np.ndarray, float]] = []
        self._motion: dict[int, float] = {}
        self.detect_rate = RateMeter()
        self.models = {
            "detector": {"name": det_path.name, "loaded": True},
            "face": {"name": face_path.name, "loaded": True},
            "emotion": {
                "name": self.emotion.meta.name if self.emotion else emo_path.name,
                "loaded": self.emotion is not None,
            },
        }

    def start(self) -> None:
        self.source.start()
        super().start()
        t = threading.Thread(target=self._detect_loop, name="detect", daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self) -> None:
        super().stop()
        self.source.stop()
        self.face.close()

    def status(self) -> dict[str, Any]:
        base = super().status()
        base["detect_fps"] = round(self.detect_rate.rate, 1)
        base["source"] = {
            "label": self.source.label,
            "kind": self.source.kind,
            "status": self.source.status.value,
            "fps": round(self.source.fps, 1),
            "resolution": self.source.resolution,
        }
        return base

    def _latest_image(self) -> tuple[np.ndarray, int, float] | None:
        f = self.source.latest()
        return (f.image, f.index, f.timestamp) if f else None

    def _tick(self, stage: str, t0: float) -> float:
        """Aşama süresini kayan ortalamayla kaydeder; bir sonraki aşamanın başlangıcını döndürür."""
        t1 = time.perf_counter()
        ms = (t1 - t0) * 1000
        prev = self.timings_ms.get(stage)
        self.timings_ms[stage] = ms if prev is None else 0.8 * prev + 0.2 * ms
        return t1

    # --- 1. döngü: kişi tespiti + takip (yavaş, ~detect_hz) ----------------------------------
    def _detect_loop(self) -> None:
        interval = 1.0 / self.settings.detect_hz
        last_index = -1
        while not self._stop.is_set():
            t0 = time.monotonic()
            frame = self.source.latest()
            if frame is None or frame.index == last_index or self.source.status != SourceStatus.LIVE:
                self._stop.wait(0.03)
                continue
            last_index = frame.index
            try:
                t = time.perf_counter()
                detections = self.detector(frame.image)
                t = self._tick("detect", t)
                now = time.time()
                tracks = self.tracker.update(detections, now)
                diff = self.motion.update(frame.image)
                motion = {tr.id: self.motion.energy(diff, tr.box) for tr in tracks}
                with self._tracks_lock:
                    self._tracks = [(tr.id, tr.box.copy(), tr.velocity.copy(), tr.last_seen) for tr in tracks]
                    self._motion = motion
                self._tick("track", t)
                self.detect_rate.tick()
            except Exception:
                log.exception("Tespit döngüsünde hata")
            self._stop.wait(max(0.0, interval - (time.monotonic() - t0)))

    # --- 2. döngü: yüz + ifade (hızlı, ~analysis_hz), takipçinin öngördüğü konumlarda ----------
    def _analysis_loop(self) -> None:
        interval = 1.0 / self.settings.analysis_hz
        last_index = -1
        while not self._stop.is_set():
            t0 = time.monotonic()
            frame = self.source.latest()
            if frame is None or frame.index == last_index or self.source.status != SourceStatus.LIVE:
                self._stop.wait(0.02)
                continue
            last_index = frame.index
            try:
                self._analyze(frame.image, time.time())
            except Exception:
                log.exception("Analiz döngüsünde hata")
            self.latency_ms = (time.monotonic() - t0) * 1000
            self._stop.wait(max(0.0, interval - (time.monotonic() - t0)))

    def _analyze(self, img: np.ndarray, now: float) -> None:
        with self._tracks_lock:
            tracks, motion = list(self._tracks), dict(self._motion)
        # Son tespitten bu yana geçen süre kadar hız ile ileri taşı (en fazla 0.5 sn)
        boxes = {tid: box + vel * min(max(now - seen, 0.0), 0.5) for tid, box, vel, seen in tracks}
        for tid, value in motion.items():
            self.aggregator.person(tid, now).observe_motion(value)

        # Büyük kutular (yakın kişiler) önce; kalanlar sonraki döngülerde sırayla
        order = sorted(boxes, key=lambda tid: -(boxes[tid][2] - boxes[tid][0]))
        limit = self.settings.max_faces_per_cycle
        if len(order) > limit:
            start = self._rr % len(order)
            order = (order[start:] + order[:start])[:limit]
            self._rr += limit

        t = time.perf_counter()
        observations = []
        for tid in order:
            obs = self.face.analyze(img, boxes[tid], min_face_px=self.settings.min_face_px)
            if obs is not None:
                observations.append((tid, obs))
        t = self._tick("face", t)

        probs = va = None
        if self.emotion and observations:
            probs, va = self.emotion.predict(
                [o.aligned_gray for _, o in observations], [o.face_rgb for _, o in observations]
            )
            self._tick("emotion", t)
        for i, (tid, obs) in enumerate(observations):
            self.aggregator.person(tid, now).observe_face(
                now,
                blink=obs.eye_blink,
                jaw_open=obs.jaw_open,
                yaw=obs.yaw,
                pitch=obs.pitch,
                box=obs.box,
                probs=probs[i] if probs is not None else None,
                va=va[i] if va is not None else None,
            )

        h, w = img.shape[:2]
        self._publish(self.aggregator.snapshot(now, list(boxes), boxes, (w, h)))


class MockEngine(BaseEngine):
    """Kamera olmadan arayüz geliştirmek için sentetik sahne ve gerçekçi metrik akışı.

    Gerçek `RoomAggregator` kullanılır; yalnızca model çıktıları simüle edilir.
    Arayüz bu modu açıkça "DEMO" olarak gösterir.
    """

    mode = "mock"
    W, H = 1280, 720

    def __init__(self, settings: Settings, history: History | None = None, seed: int = 7) -> None:
        super().__init__(settings, history)
        self.rng = random.Random(seed)
        self.aggregator = RoomAggregator(self.labels)
        self._index = 0
        self._image: np.ndarray | None = None
        self._img_lock = threading.Lock()
        self._background = self._make_background()
        self._agents = [self._new_agent(i) for i in range(14)]
        self._next_id = 100
        self.models = {k: {"name": "simülasyon", "loaded": True} for k in ("detector", "face", "emotion")}

    def status(self) -> dict[str, Any]:
        base = super().status()
        base["source"] = {
            "label": "Demo sahnesi",
            "kind": "mock",
            "status": "live",
            "fps": self.settings.stream_fps,
            "resolution": (self.W, self.H),
        }
        return base

    def _make_background(self) -> np.ndarray:
        y = np.linspace(0, 1, self.H, dtype=np.float32)[:, None, None]
        top, bottom = np.array([46, 34, 28], np.float32), np.array([20, 16, 14], np.float32)
        bg = (top * (1 - y) + bottom * y).repeat(self.W, axis=1).astype(np.uint8)
        for row in range(3):  # sıra çizgileri
            yy = 270 + row * 150 + 40
            cv2.line(bg, (0, yy + 60), (self.W, yy + 60), (60, 52, 46), 2, cv2.LINE_AA)
        cv2.rectangle(bg, (420, 40), (860, 170), (70, 78, 62), -1, cv2.LINE_AA)  # tahta
        return bg

    def _new_agent(self, i: int) -> dict[str, Any]:
        row, col = divmod(i, 5)
        spread = 190 + row * 45
        return {
            "slot": i,  # koltuk: aynı yere iki kişi oturmasın
            "id": i + 1,
            "x": self.W / 2 + (col - 2) * spread + self.rng.uniform(-18, 18),
            "y": 270 + row * 150,
            "scale": 0.8 + row * 0.28,
            "phase": self.rng.uniform(0, math.tau),
            "mood": self.rng.choice([0, 0, 0, 1, 1, 2, 3]),
            "drowsy": self.rng.random() < 0.15,
            "look": self.rng.uniform(-10, 10),
        }

    def _latest_image(self) -> tuple[np.ndarray, int, float] | None:
        with self._img_lock:
            return (self._image, self._index, time.time()) if self._image is not None else None

    def _analysis_loop(self) -> None:
        interval = 1.0 / self.settings.detect_hz
        while not self._stop.is_set():
            t0 = time.monotonic()
            self._step(time.time())
            self.latency_ms = 38 + 6 * math.sin(time.time())
            self._stop.wait(max(0.0, interval - (time.monotonic() - t0)))

    def _step(self, now: float) -> None:
        rng = self.rng
        if rng.random() < 0.01 and len(self._agents) > 8:
            self._agents.pop(rng.randrange(len(self._agents)))
        if rng.random() < 0.01 and len(self._agents) < 15:
            taken = {ag["slot"] for ag in self._agents}
            a = self._new_agent(rng.choice([i for i in range(15) if i not in taken]))
            a["id"] = self._next_id
            self._next_id += 1
            self._agents.append(a)

        img = self._background.copy()
        boxes, ids = {}, []
        drift = math.sin(now / 45)  # odanın genel ruh hali yavaşça değişir
        for a in self._agents:
            if rng.random() < 0.004:
                a["mood"] = rng.choice([0, 0, 1, 1, 2, 3, 4, 6])
            sway = math.sin(now * 0.8 + a["phase"]) * 6
            s = a["scale"]
            cx, cy = a["x"] + sway, a["y"]
            box = np.array([cx - 42 * s, cy - 70 * s, cx + 42 * s, cy + 95 * s], np.float32)
            color = (88 + a["id"] * 7 % 40, 92, 104)
            cv2.ellipse(
                img,
                (int(cx), int(cy + 60 * s)),
                (int(44 * s), int(52 * s)),
                0,
                180,
                360,
                color,
                -1,
                cv2.LINE_AA,
            )
            cv2.circle(img, (int(cx), int(cy - 28 * s)), int(28 * s), (150, 170, 196), -1, cv2.LINE_AA)
            boxes[a["id"]] = box
            ids.append(a["id"])

            person = self.aggregator.person(a["id"], now)
            person.observe_motion(abs(math.cos(now * 0.8 + a["phase"])) * 0.06 + rng.uniform(0, 0.03))
            probs = np.full(len(self.labels), 0.03, np.float32)
            probs[a["mood"]] += 0.55 + 0.2 * drift
            probs[1] += max(0.0, drift) * 0.6  # olumlu evre
            probs[3] += max(0.0, -drift) * 0.5  # durgun evre
            probs[0] += 0.25
            probs = np.clip(probs + np.array([rng.uniform(0, 0.08) for _ in probs], np.float32), 1e-3, None)
            probs /= probs.sum()
            fs = 26 * s
            face = np.array([cx - fs, cy - 28 * s - fs * 1.1, cx + fs, cy - 28 * s + fs], np.float32)
            sleepy = a["drowsy"] or drift < -0.55
            blink = 0.9 if (sleepy and rng.random() < 0.45) or rng.random() < 0.05 else 0.1
            person.observe_face(
                now,
                blink=blink,
                jaw_open=0.7 if sleepy and rng.random() < 0.05 else 0.1,
                yaw=a["look"] + rng.uniform(-8, 8) + (40 if rng.random() < 0.08 else 0),
                pitch=rng.uniform(-8, 6) - (25 if sleepy and (a["drowsy"] or a["phase"] > math.pi) else 0),
                box=face,
                probs=probs,
            )

        with self._img_lock:
            self._image = img
            self._index += 1
        self._publish(self.aggregator.snapshot(now, ids, boxes, (self.W, self.H)))


def create_engine(settings: Settings, history: History | None = None) -> BaseEngine:
    if settings.source.lower() == "mock":
        return MockEngine(settings, history)
    return VisionEngine(settings, history)
