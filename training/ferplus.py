"""FER2013 görüntüleri + FER+ (Microsoft, MIT) oy etiketlerinden PyTorch veri kümesi.

Kaynaklar
---------
* FER2013 (Goodfellow ve ark., 2013): `fer2013.csv` — Kaggle'da ücretsiz. Sütunlar: emotion, pixels, Usage
  (yarışma sürümündeki `icml_face_data.csv` de desteklenir).
* FER+ (Barsoum ve ark., 2016): `fer2013new.csv` — https://github.com/microsoft/FERPlus (MIT).
  Her görüntü için 10 etiketleyicinin 8 duygu + "unknown" + "NF (yüz değil)" oyları.

Satırlar iki dosyada aynı sıradadır. FER+ makalesindeki ön işleme uygulanır:
  1. Tek oy alan duygular gürültü kabul edilip sıfırlanır.
  2. "unknown" veya "NF" çoğunluktaysa görüntü atılır.
  3. Kalan oylar 8 sınıf üzerinde normalize edilip **olasılık dağılımı** (soft label) olarak kullanılır.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

LABELS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]
SPLITS = {"train": "Training", "val": "PublicTest", "test": "PrivateTest"}
FERPLUS_URL = "https://raw.githubusercontent.com/microsoft/FERPlus/master/fer2013new.csv"


def _read_fer2013(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if not {"pixels", "usage"} <= set(df.columns):
        raise ValueError(f"{path} beklenen sütunları içermiyor: {list(df.columns)}")
    return df


def load_ferplus(fer2013_csv: Path, ferplus_csv: Path | str = FERPLUS_URL) -> pd.DataFrame:
    """Birleştirilmiş tablo: pixels, split, ve LABELS sütunlarında normalize olasılıklar."""
    fer = _read_fer2013(Path(fer2013_csv))
    plus = pd.read_csv(ferplus_csv)
    plus.columns = [c.strip() for c in plus.columns]
    if len(fer) != len(plus):
        raise ValueError(f"Satır sayıları uyuşmuyor: FER2013={len(fer)} FER+={len(plus)}")

    votes = plus[LABELS].to_numpy(dtype=np.float32)
    other = plus[["unknown", "NF"]].to_numpy(dtype=np.float32)
    votes[votes <= 1] = 0  # tek oylar gürültü
    total = votes.sum(1)
    keep = (total > 0) & (other.max(1) < votes.max(1)) & plus["Image name"].notna().to_numpy()

    probs = np.zeros_like(votes)
    probs[keep] = votes[keep] / total[keep, None]
    out = pd.DataFrame(probs, columns=LABELS)
    out["pixels"] = fer["pixels"].to_numpy()
    out["split"] = plus["Usage"].map({v: k for k, v in SPLITS.items()}).to_numpy()
    return out[keep].reset_index(drop=True)


def pixels_to_image(pixels: str) -> np.ndarray:
    return np.asarray(pixels.split(), dtype=np.uint8).reshape(48, 48)


class FerPlusDataset(Dataset):
    def __init__(self, table: pd.DataFrame, split: str, transform=None) -> None:
        part = table[table["split"] == split]
        self.images = np.stack([pixels_to_image(p) for p in part["pixels"]])
        self.targets = torch.tensor(part[LABELS].to_numpy(np.float32))
        self.transform = transform

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        img = torch.from_numpy(self.images[i]).unsqueeze(0)  # 1×48×48 uint8
        if self.transform is not None:
            img = self.transform(img)
        return img, self.targets[i]

    @property
    def hard_labels(self) -> np.ndarray:
        return self.targets.argmax(1).numpy()
