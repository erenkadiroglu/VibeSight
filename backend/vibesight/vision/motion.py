"""Kişi başı hareket enerjisi: küçültülmüş gri karelerde kutu içi mutlak fark."""

from __future__ import annotations

import cv2
import numpy as np

WORK_WIDTH = 320


class MotionMeter:
    def __init__(self) -> None:
        self._prev: np.ndarray | None = None
        self._scale = 1.0

    def update(self, frame: np.ndarray) -> np.ndarray | None:
        """Yeni kareyi işler ve fark haritasını (0–1) döndürür."""
        self._scale = WORK_WIDTH / frame.shape[1]
        small = cv2.resize(frame, None, fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        diff = None
        if self._prev is not None and self._prev.shape == gray.shape:
            d = cv2.absdiff(gray, self._prev)
            diff = (d > 18).astype(np.float32)
        self._prev = gray
        return diff

    def energy(self, diff: np.ndarray | None, box: np.ndarray) -> float:
        """Kutu içindeki hareketli piksel oranı (0–1)."""
        if diff is None:
            return 0.0
        x1, y1, x2, y2 = (box * self._scale).astype(int)
        region = diff[max(0, y1) : max(0, y2), max(0, x1) : max(0, x2)]
        return float(region.mean()) if region.size else 0.0
