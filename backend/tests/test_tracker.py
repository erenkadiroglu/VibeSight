import numpy as np

from vibesight.vision.detector import Detection
from vibesight.vision.tracker import Tracker, iou_matrix


def det(x1: float, y1: float, x2: float, y2: float) -> Detection:
    return Detection(np.array([x1, y1, x2, y2], np.float32), 0.9)


def test_iou_identity_and_disjoint() -> None:
    a = np.array([[0, 0, 10, 10]], np.float32)
    b = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], np.float32)
    m = iou_matrix(a, b)
    assert m[0, 0] == 1.0
    assert m[0, 1] == 0.0


def test_ids_are_stable_while_moving() -> None:
    tr = Tracker()
    tr.update([det(0, 0, 50, 100), det(200, 0, 250, 100)], 0.0)
    out = tr.update([det(5, 0, 55, 100), det(205, 0, 255, 100)], 0.2)
    ids = sorted(t.id for t in out)
    out2 = tr.update([det(10, 0, 60, 100), det(210, 0, 260, 100)], 0.4)
    assert sorted(t.id for t in out2) == ids == [1, 2]


def test_tracks_need_confirmation_and_expire() -> None:
    tr = Tracker(max_age_s=1.0)
    assert tr.update([det(0, 0, 50, 100)], 0.0) == []  # tek görüş yetmez
    assert len(tr.update([det(0, 0, 50, 100)], 0.1)) == 1
    tr.update([], 2.0)
    assert tr.tracks == []
