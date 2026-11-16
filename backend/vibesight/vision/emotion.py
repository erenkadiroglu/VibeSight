"""Yüz ifadesi sınıflandırıcısı (ONNX).

Model, yanındaki `<model>.json` dosyasıyla tanımlanır; böylece farklı modeller aynı sınıfla çalışır:
  * EmotiEffLib `enet_b0_8_va_mtl` (varsayılan; AffectNet, renkli 224×224, valans/uyarılmışlık çıktılı)
  * `training/` altında FER+ ile eğittiğimiz model (gri, 48→112)
  * ONNX Model Zoo `emotion-ferplus-8` (gri, 64×64)

Örnek `emotion.json`:
    {"labels": ["neutral", ...], "input_size": 112, "channels": 3,
     "mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5], "scale": 255.0, "temperature": 1.0}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vibesight.vision.detector import make_session

FERPLUS_LABELS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]

# ONNX Model Zoo emotion-ferplus-8: 1×1×64×64, ham 0–255 piksel, 8 logit.
BASELINE_META = {
    "labels": FERPLUS_LABELS,
    "input_size": 64,
    "channels": 1,
    "mean": [0.0],
    "std": [1.0],
    "scale": 1.0,
    "temperature": 1.0,
}


@dataclass
class EmotionMeta:
    labels: list[str] = field(default_factory=lambda: list(FERPLUS_LABELS))
    input_size: int = 112
    channels: int = 3
    mean: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    std: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    scale: float = 255.0
    temperature: float = 1.0
    source_size: int | None = None  # eğitim verisinin çözünürlüğü (FER2013: 48) — aynı bulanıklığı üretir
    color: bool = False  # True: renkli yüz kutusu (RGB); False: hizalanmış gri yüz
    va_outputs: bool = False  # True: son iki çıktı valans ve uyarılmışlık ([-1, 1])
    name: str = "emotion"

    @classmethod
    def for_model(cls, model_path: Path) -> EmotionMeta:
        meta_path = model_path.with_suffix(".json")
        raw = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else BASELINE_META
        data: dict[str, Any] = dict(raw)
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "name"}
        return cls(**known, name=str(data.get("name", model_path.stem)))


def softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = x / max(temperature, 1e-6)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class EmotionClassifier:
    def __init__(self, model_path: Path, threads: int = 0) -> None:
        self.meta = EmotionMeta.for_model(model_path)
        self.session = make_session(model_path, threads)
        self.input_name = self.session.get_inputs()[0].name

    @property
    def labels(self) -> list[str]:
        return self.meta.labels

    def preprocess(self, faces: list[np.ndarray]) -> np.ndarray:
        m = self.meta
        mean = np.array(m.mean, np.float32).reshape(-1, 1, 1)
        std = np.array(m.std, np.float32).reshape(-1, 1, 1)
        batch = []
        for face in faces:
            if m.color:
                img = cv2.resize(face, (m.input_size, m.input_size)).astype(np.float32) / m.scale
                chw = img.transpose(2, 0, 1)
            else:
                gray = face
                if m.source_size:
                    gray = cv2.resize(gray, (m.source_size, m.source_size), interpolation=cv2.INTER_AREA)
                interp = cv2.INTER_LINEAR if gray.shape[0] < m.input_size else cv2.INTER_AREA
                img = cv2.resize(gray, (m.input_size, m.input_size), interpolation=interp).astype(np.float32)
                chw = np.repeat((img / m.scale)[None], m.channels, axis=0)
            batch.append((chw - mean) / std)
        return np.stack(batch).astype(np.float32)

    def predict(self, gray: list[np.ndarray], rgb: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray | None]:
        """Yüz kırpıntıları → (olasılıklar (N, C), valans-uyarılmışlık (N, 2) veya None)."""
        n_cls = len(self.labels)
        if not gray:
            return np.zeros((0, n_cls), np.float32), None
        x = self.preprocess(rgb if self.meta.color else gray)
        # Bazı modeller sabit batch=1 ister; güvenli olmak için tek tek çalıştır.
        fixed_batch = self.session.get_inputs()[0].shape[0] == 1
        out = (
            np.concatenate(
                [self.session.run(None, {self.input_name: x[i : i + 1]})[0] for i in range(len(x))]
            )
            if fixed_batch
            else self.session.run(None, {self.input_name: x})[0]
        ).reshape(len(x), -1)
        probs = softmax(out[:, :n_cls], self.meta.temperature)
        va = np.clip(out[:, n_cls : n_cls + 2], -1, 1) if self.meta.va_outputs else None
        return probs, va

    def __call__(self, faces: list[np.ndarray]) -> np.ndarray:
        """Geriye uyumluluk: yalnızca olasılıklar."""
        return self.predict(faces, faces)[0]
