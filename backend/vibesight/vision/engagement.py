"""Öğrenilmiş katılım (engagement) modeli — EmotiEffLib, EngageWild veri setinde eğitildi.

Kaynak: Savchenko ve ark., "Classifying emotions and engagement in online learning based on a single
facial expression recognition neural network", IEEE Transactions on Affective Computing, 2022.
Ağırlıklar: github.com/sb-ai-lab/EmotiEffLib (Apache-2.0), `engagement_single_attention.h5`.

Model, bir kişinin son birkaç saniyesindeki yüz özniteliklerine (ifade ağının 1280 boyutlu son gizli katmanı)
bakar: her kareyi, dizinin standart sapmasıyla birleştirir (2560 boyut), dikkat mekanizmasıyla hangi karelerin
önemli olduğunu öğrenilmiş ağırlıklarla seçer ve "Dalgın / Katılımcı" olasılığı üretir.
Orijinal Keras modeli burada NumPy ile birebir çalıştırılır (TensorFlow gerekmez).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

FEATURE_DIM = 1280
ENGAGED = 1  # sınıf sırası: 0 = Distracted, 1 = Engaged


class EngagementModel:
    def __init__(self, weights_path: Path) -> None:
        import h5py

        with h5py.File(weights_path, "r") as f:
            self.w_e = np.asarray(f["e/e/kernel:0"], np.float32)  # (2560, 1)
            self.b_e = np.asarray(f["e/e/bias:0"], np.float32)
            self.w_h = np.asarray(f["hidden_FC/hidden_FC/kernel:0"], np.float32)  # (2560, 512)
            self.b_h = np.asarray(f["hidden_FC/hidden_FC/bias:0"], np.float32)
            self.w_o = np.asarray(f["dense/dense/kernel:0"], np.float32)  # (512, 2)
            self.b_o = np.asarray(f["dense/dense/bias:0"], np.float32)
        if self.w_e.shape != (2 * FEATURE_DIM, 1):
            raise ValueError(f"Beklenmeyen katılım modeli boyutu: {self.w_e.shape}")

    def __call__(self, features: np.ndarray) -> float:
        """(T, 1280) öznitelik dizisi → katılım olasılığı (0–1)."""
        x = np.asarray(features, np.float32)
        x = np.concatenate([np.repeat(x.std(axis=0, keepdims=True), len(x), axis=0), x], axis=1)  # (T, 2560)
        e = (x @ self.w_e + self.b_e)[:, 0]
        alpha = np.exp(e - e.max())
        alpha /= alpha.sum()
        context = alpha @ x  # dikkat ağırlıklı özet (2560,)
        hidden = np.maximum(context @ self.w_h + self.b_h, 0.0)
        logits = hidden @ self.w_o + self.b_o
        p = np.exp(logits - logits.max())
        return float(p[ENGAGED] / p.sum())
