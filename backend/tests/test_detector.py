from pathlib import Path

import numpy as np
import pytest

MODEL = Path(__file__).resolve().parents[1] / "models" / "yolox_s.onnx"


@pytest.mark.skipif(not MODEL.exists(), reason="model indirilmemiş (make models)")
def test_blank_frame_has_no_people() -> None:
    from vibesight.vision.detector import PersonDetector

    det = PersonDetector(MODEL)
    assert det(np.zeros((480, 640, 3), np.uint8)) == []
