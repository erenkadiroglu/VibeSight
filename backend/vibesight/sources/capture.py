"""Görüntü kaynakları: RTSP (Tapo C200), bilgisayar kamerası ve video dosyası.

Kaynak ayrı bir iş parçacığında sürekli okunur ve yalnızca **en son kare** tutulur; böylece analiz
yavaş kalsa bile gecikme birikmez. Bağlantı koparsa üstel geri çekilme ile yeniden bağlanılır.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np

from vibesight.config import redact

log = logging.getLogger(__name__)

# RTSP'yi TCP üzerinden ve düşük tamponla aç: Wi-Fi'da UDP paket kaybı görüntüyü bozar.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|fflags;nobuffer|max_delay;500000")


class SourceStatus(StrEnum):
    CONNECTING = "connecting"
    LIVE = "live"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass(slots=True)
class Frame:
    image: np.ndarray  # BGR
    timestamp: float
    index: int


class FrameSource:
    """Arka planda okunan, otomatik yeniden bağlanan kare kaynağı."""

    def __init__(self, uri: str, *, max_width: int = 1920) -> None:
        self.uri = uri
        self.max_width = max_width
        self.kind = self._kind(uri)
        self.status = SourceStatus.CONNECTING
        self.fps = 0.0
        self.resolution: tuple[int, int] | None = None
        self._frame: Frame | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="frame-source", daemon=True)

    @staticmethod
    def _kind(uri: str) -> str:
        if uri.isdigit():
            return "webcam"
        if uri.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return "stream"
        return "file"

    @property
    def label(self) -> str:
        return {"webcam": f"Kamera #{self.uri}", "stream": redact(self.uri), "file": Path(self.uri).name}[
            self.kind
        ]

    def start(self) -> FrameSource:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self.status = SourceStatus.STOPPED

    def latest(self) -> Frame | None:
        with self._lock:
            return self._frame

    def _open(self) -> cv2.VideoCapture:
        if self.kind == "webcam":
            cap = cv2.VideoCapture(int(self.uri))
        elif self.kind == "stream":
            cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(self.uri)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _run(self) -> None:
        backoff = 1.0
        index = 0
        while not self._stop.is_set():
            cap = self._open()
            if not cap.isOpened():
                self.status = SourceStatus.RECONNECTING
                log.warning("Kaynak açılamadı: %s — %.0f sn sonra tekrar denenecek", self.label, backoff)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 30.0)
                continue

            log.info("Kaynak bağlandı: %s", self.label)
            backoff = 1.0
            native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            frame_interval = 1.0 / native_fps if self.kind == "file" else 0.0
            window_start, window_frames = time.monotonic(), 0

            while not self._stop.is_set():
                t0 = time.monotonic()
                ok, img = cap.read()
                if not ok or img is None:
                    if self.kind == "file":  # dosya bitti → başa sar
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    log.warning("Kaynaktan kare alınamadı, yeniden bağlanılıyor: %s", self.label)
                    break

                h, w = img.shape[:2]
                if w > self.max_width:
                    scale = self.max_width / w
                    img = cv2.resize(img, (self.max_width, round(h * scale)), interpolation=cv2.INTER_AREA)
                self.resolution = (img.shape[1], img.shape[0])

                index += 1
                with self._lock:
                    self._frame = Frame(img, time.time(), index)
                self.status = SourceStatus.LIVE

                window_frames += 1
                elapsed = time.monotonic() - window_start
                if elapsed >= 1.0:
                    self.fps = window_frames / elapsed
                    window_start, window_frames = time.monotonic(), 0

                if frame_interval:  # dosyayı gerçek hızında oynat
                    self._stop.wait(max(0.0, frame_interval - (time.monotonic() - t0)))

            cap.release()
            if not self._stop.is_set():
                self.status = SourceStatus.RECONNECTING
                self._stop.wait(backoff)
