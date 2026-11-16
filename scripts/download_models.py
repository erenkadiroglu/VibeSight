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
    # İfade + valans/uyarılmışlık — Apache-2.0 — github.com/sb-ai-lab/EmotiEffLib (Savchenko, IEEE TAC 2022)
    {
        "file": "enet_b0_8_va_mtl.onnx",
        "url": "https://raw.githubusercontent.com/sb-ai-lab/EmotiEffLib/main/models/affectnet_emotions/onnx/enet_b0_8_va_mtl.onnx",
        "sha256": "c43e056ad388d4a8dc911832b8291435b2af537f967e5870ebd731574ec7e812",
        "meta": {
            "name": "EmotiEffLib enet_b0_8_va_mtl (AffectNet)",
            "labels": ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"],
            "input_size": 224,
            "channels": 3,
            "color": True,
            "va_outputs": True,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
            "scale": 255.0,
            "temperature": 1.0,
        },
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_meta(m: dict, dest: Path) -> None:
    """Modelin tanım dosyasını (ön işleme, etiketler) yazar; var olan tanıma dokunmaz."""
    meta_path = dest.with_suffix(".json")
    if "meta" in m and not meta_path.exists():
        meta_path.write_text(json.dumps(m["meta"], ensure_ascii=False, indent=2), "utf-8")


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    failed = False
    for m in MODELS:
        dest = MODELS_DIR / m["file"]
        if dest.exists() and (m.get("keep_existing") or (m["sha256"] and sha256(dest) == m["sha256"])):
            print(f"✓ {m['file']} zaten var")
            write_meta(m, dest)
            continue
        print(f"↓ {m['file']} indiriliyor…")
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with urllib.request.urlopen(m["url"], timeout=60) as r, tmp.open("wb") as f:
                shutil.copyfileobj(r, f)
            if m["sha256"] and sha256(tmp) != m["sha256"]:
                raise ValueError("SHA-256 uyuşmuyor")
            tmp.replace(dest)
            write_meta(m, dest)
            print(f"✓ {m['file']} hazır")
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            print(f"✗ {m['file']}: {exc}", file=sys.stderr)
            failed = failed or not m.get("optional")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
