"""Kategorik ifadeleri Russell'ın (1980) duygu çemberindeki (valans, uyarılmışlık) koordinatlara eşler.

Koordinatlar [-1, 1] aralığındadır ve Russell (1980) ile AffectNet (Mollahosseini ve ark., 2017)
sınıf ortalamalarına yakın değerlerdir. Olasılık ağırlıklı ortalama, sürekli bir duygu-durum tahmini verir.
"""

from __future__ import annotations

import numpy as np

CIRCUMPLEX: dict[str, tuple[float, float]] = {
    "neutral": (0.0, 0.0),
    "happiness": (0.80, 0.45),
    "surprise": (0.35, 0.80),
    "sadness": (-0.70, -0.40),
    "anger": (-0.60, 0.70),
    "disgust": (-0.70, 0.30),
    "fear": (-0.60, 0.75),
    "contempt": (-0.50, 0.20),
}

LABELS_TR: dict[str, str] = {
    "neutral": "Nötr",
    "happiness": "Mutlu",
    "surprise": "Şaşkın",
    "sadness": "Üzgün",
    "anger": "Kızgın",
    "disgust": "Hoşnutsuz",
    "fear": "Endişeli",
    "contempt": "Küçümseyen",
}


def valence_arousal(probs: np.ndarray, labels: list[str]) -> tuple[float, float]:
    coords = np.array([CIRCUMPLEX.get(label, (0.0, 0.0)) for label in labels], dtype=np.float32)
    v, a = (np.asarray(probs, np.float32) @ coords).tolist()
    return float(v), float(a)
