"""Model katmanı testleri.

Modeller ve referans görüntü yoksa (ilk kurulum öncesi / ağ yoksa) ilgili testler atlanır.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import pytest

MODELS = Path(__file__).resolve().parents[1] / "models"
REF_URL = "https://raw.githubusercontent.com/sb-ai-lab/EmotiEffLib/main/tests/test_images/20180720_174416.jpg"


def test_engagement_forward_matches_reference_formula(tmp_path: Path) -> None:
    """NumPy katılım ağı, Keras modelinin tanımıyla (dikkat → gizli katman → softmax) aynı hesabı yapar."""
    import h5py

    from vibesight.vision.engagement import EngagementModel

    rng = np.random.default_rng(0)
    w = {
        "e/e/kernel:0": rng.normal(0, 0.05, (2560, 1)),
        "e/e/bias:0": np.zeros(1),
        "hidden_FC/hidden_FC/kernel:0": rng.normal(0, 0.05, (2560, 512)),
        "hidden_FC/hidden_FC/bias:0": rng.normal(0, 0.1, 512),
        "dense/dense/kernel:0": rng.normal(0, 0.1, (512, 2)),
        "dense/dense/bias:0": np.zeros(2),
    }
    path = tmp_path / "w.h5"
    with h5py.File(path, "w") as f:
        for k, v in w.items():
            f[k] = v.astype(np.float32)
    feats = rng.normal(0, 1, (40, 1280)).astype(np.float32)

    x = np.concatenate([np.repeat(feats.std(0, keepdims=True), 40, 0), feats], 1)
    e = x @ w["e/e/kernel:0"][:, 0]
    a = np.exp(e - e.max()) / np.exp(e - e.max()).sum()
    h = np.maximum((a @ x) @ w["hidden_FC/hidden_FC/kernel:0"] + w["hidden_FC/hidden_FC/bias:0"], 0)
    lo = h @ w["dense/dense/kernel:0"]
    expected = np.exp(lo[1]) / np.exp(lo).sum()

    assert EngagementModel(path)(feats) == pytest.approx(float(expected), rel=1e-4)


@pytest.mark.skipif(
    not all((MODELS / m).exists() for m in ("yolox_s.onnx", "face_landmarker.task", "enet_b0_8_va_mtl.onnx")),
    reason="modeller indirilmemiş (vs.ps1 setup / make models)",
)
def test_reference_image_matches_official_library(tmp_path: Path) -> None:
    """EmotiEffLib'in kendi testindeki fotoğraf: resmî beklenti [Mutlu, Kızgın, Mutlu].

    Hattımız (YOLOX + MediaPipe + MTCNN eşdeğeri kırpma) aynı sonucu vermeli; kırpma veya ön işleme
    bozulursa bu test yakalar.
    """
    import cv2

    from vibesight.vision.detector import PersonDetector
    from vibesight.vision.emotion import EmotionClassifier
    from vibesight.vision.face import FaceAnalyzer

    ref = tmp_path / "ref.jpg"
    try:
        urllib.request.urlretrieve(REF_URL, ref)
    except OSError:
        pytest.skip("referans görüntü indirilemedi (ağ yok)")
    img = cv2.imread(str(ref))
    detector = PersonDetector(MODELS / "yolox_s.onnx")
    face = FaceAnalyzer(MODELS / "face_landmarker.task")
    emotion = EmotionClassifier(MODELS / "enet_b0_8_va_mtl.onnx")
    got = []
    for det in sorted(detector(img), key=lambda d: d.box[0]):
        obs = face.analyze(img, det.box)
        assert obs is not None
        probs, _ = emotion.predict([obs.aligned_gray], [obs.face_rgb])
        got.append(emotion.labels[int(probs[0].argmax())])
    face.close()
    assert got == ["happiness", "anger", "happiness"]
