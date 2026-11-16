"""Bağımlılıksız, hafif çok-nesne takipçisi (IoU + merkez mesafesi, açgözlü eşleştirme).

Sınıf ortamında insanlar yavaş hareket eder; SORT benzeri bu yaklaşım yeterli ve deterministiktir.
ID'ler geçicidir ve hiçbir şekilde kimlikle ilişkilendirilmez.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from vibesight.vision.detector import Detection


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-6)


@dataclass
class Track:
    id: int
    box: np.ndarray
    score: float
    first_seen: float
    last_seen: float
    hits: int = 1
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(4, dtype=np.float32))

    @property
    def confirmed(self) -> bool:
        return self.hits >= 2

    def predicted(self, now: float) -> np.ndarray:
        dt = min(now - self.last_seen, 1.0)
        return self.box + self.velocity * dt


class Tracker:
    def __init__(
        self, *, iou_threshold: float = 0.25, max_age_s: float = 1.5, smoothing: float = 0.6
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_age_s = max_age_s
        self.smoothing = smoothing
        self.tracks: list[Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection], now: float) -> list[Track]:
        det_boxes = np.array([d.box for d in detections], dtype=np.float32).reshape(-1, 4)
        pred_boxes = np.array([t.predicted(now) for t in self.tracks], dtype=np.float32).reshape(-1, 4)
        ious = iou_matrix(pred_boxes, det_boxes)

        matched_t: set[int] = set()
        matched_d: set[int] = set()
        if ious.size:
            for flat in np.argsort(-ious, axis=None):
                ti, di = (int(v) for v in np.unravel_index(flat, ious.shape))
                if ious[ti, di] < self.iou_threshold:
                    break
                if ti in matched_t or di in matched_d:
                    continue
                matched_t.add(int(ti))
                matched_d.add(int(di))
                self._apply(self.tracks[ti], detections[di], now)

        for di, det in enumerate(detections):
            if di not in matched_d:
                self.tracks.append(Track(self._next_id, det.box.astype(np.float32), det.score, now, now))
                self._next_id += 1

        self.tracks = [t for t in self.tracks if now - t.last_seen <= self.max_age_s]
        return [t for t in self.tracks if t.confirmed and t.last_seen == now]

    def _apply(self, track: Track, det: Detection, now: float) -> None:
        dt = max(now - track.last_seen, 1e-3)
        new_box = self.smoothing * det.box + (1 - self.smoothing) * track.box
        track.velocity = 0.5 * track.velocity + 0.5 * (new_box - track.box) / dt
        track.box = new_box.astype(np.float32)
        track.score = det.score
        track.last_seen = now
        track.hits += 1
