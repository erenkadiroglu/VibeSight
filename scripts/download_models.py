"""Çalışma zamanı modellerini indirir ve SHA-256 ile doğrular.

Kullanım:  python scripts/download_models.py   (veya: make models)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[1] / "backend" / "models"

MODELS = [
    {  # Kişi tespiti — Apache-2.0 — github.com/Megvii-BaseDetection/YOLOX
        "file": "yolox_s.onnx",
        "url": "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx",
        "sha256": "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
    },
    {  # Yüz noktaları + blendshape — Apache-2.0 — ai.google.dev/edge/mediapipe
        "file": "face_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    },
    {  # Taban ifade modeli (kendi modelimiz eğitilene kadar) — MIT — ONNX Model Zoo
        "file": "emotion.onnx",
        "url": "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
        "sha256": None,
        "meta": {
            "name": "emotion-ferplus-8 (taban)",
            "labels": ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"],
            "input_size": 64,
            "channels": 1,
            "mean": [0.0],
            "std": [1.0],
            "scale": 1.0,
            "temperature": 1.0,
        },
        "optional": True,
        "keep_existing": True,  # kendi eğittiğimiz model varsa üzerine yazma
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    failed = False
    for m in MODELS:
        dest = MODELS_DIR / m["file"]
        if dest.exists() and (m.get("keep_existing") or (m["sha256"] and sha256(dest) == m["sha256"])):
            print(f"✓ {m['file']} zaten var")
            continue
        print(f"↓ {m['file']} indiriliyor…")
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with urllib.request.urlopen(m["url"], timeout=60) as r, tmp.open("wb") as f:
                shutil.copyfileobj(r, f)
            if m["sha256"] and sha256(tmp) != m["sha256"]:
                raise ValueError("SHA-256 uyuşmuyor")
            tmp.replace(dest)
            if "meta" in m:
                dest.with_suffix(".json").write_text(
                    json.dumps(m["meta"], ensure_ascii=False, indent=2), "utf-8"
                )
            print(f"✓ {m['file']} hazır")
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            print(f"✗ {m['file']}: {exc}", file=sys.stderr)
            failed = failed or not m.get("optional")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
