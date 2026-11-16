import numpy as np
import pytest

from vibesight.analytics.affect import CIRCUMPLEX, valence_arousal
from vibesight.analytics.state import PersonState, RoomAggregator, classify_atmosphere
from vibesight.vision.emotion import FERPLUS_LABELS, softmax


def onehot(label: str) -> np.ndarray:
    v = np.zeros(len(FERPLUS_LABELS), np.float32)
    v[FERPLUS_LABELS.index(label)] = 1
    return v


def test_valence_arousal_matches_circumplex() -> None:
    assert valence_arousal(onehot("happiness"), FERPLUS_LABELS) == pytest.approx(CIRCUMPLEX["happiness"])
    assert valence_arousal(onehot("neutral"), FERPLUS_LABELS) == (0.0, 0.0)


def test_softmax_is_distribution() -> None:
    p = softmax(np.array([[1.0, 2.0, 3.0]]), temperature=2.0)
    assert p.sum() == pytest.approx(1.0)
    assert np.argmax(p) == 2


def feed(
    p: PersonState, t0: float, n: int, *, blink: float, jaw: float = 0.0, label: str = "neutral"
) -> None:
    for i in range(n):
        p.observe_face(
            t0 + i * 0.2,
            blink=blink,
            jaw_open=jaw,
            yaw=0,
            pitch=0,
            box=np.zeros(4, np.float32),
            probs=onehot(label),
        )


def test_perclos_and_energy_drop_when_eyes_closed() -> None:
    alert, sleepy = PersonState(1), PersonState(2)
    feed(alert, 0, 50, blink=0.05, label="happiness")
    feed(sleepy, 0, 50, blink=0.9, label="sadness")
    assert alert.perclos == 0.0
    assert sleepy.perclos == 1.0
    assert alert.energy(10, FERPLUS_LABELS) > 55 > 20 > sleepy.energy(10, FERPLUS_LABELS)


def test_yawn_requires_sustained_jaw_open() -> None:
    p = PersonState(1)
    feed(p, 0, 3, blink=0, jaw=0.8)  # 0.4 sn
    assert p.yawns == 0
    feed(p, 1, 10, blink=0, jaw=0.8)  # 1.8 sn
    assert p.yawns == 1


def test_atmosphere_rules() -> None:
    kw = {"faces": 5, "attention": 0.8, "perclos": 0.0}
    assert classify_atmosphere(energy=None, valence=None, arousal=None, **kw).key == "unknown"
    assert classify_atmosphere(energy=30, valence=0, arousal=0, **{**kw, "perclos": 0.4}).key == "tired"
    assert classify_atmosphere(energy=60, valence=-0.5, arousal=0.6, **kw).key == "tense"
    assert (
        classify_atmosphere(energy=70, valence=0.5, arousal=0.4, dominant="happiness", **kw).key == "positive"
    )
    # nötr baskınken "pozitif" denmemeli (canlı testte görülen tutarsızlık)
    assert (
        classify_atmosphere(energy=70, valence=0.5, arousal=0.4, dominant="neutral", **kw).key != "positive"
    )
    assert classify_atmosphere(energy=50, valence=0, arousal=0, **kw).key == "focused"
    assert classify_atmosphere(energy=50, valence=None, arousal=None, **kw).key == "focused"


def test_room_snapshot_counts_and_normalizes() -> None:
    agg = RoomAggregator(FERPLUS_LABELS)
    boxes = {1: np.array([0, 0, 64, 48], np.float32), 2: np.array([64, 48, 128, 96], np.float32)}
    for tid in boxes:
        feed(agg.person(tid, 0), 0, 5, blink=0.0, label="happiness")
    snap = agg.snapshot(1.0, [1, 2], boxes, (128, 96))
    assert snap["count"] == 2
    assert snap["faces_analyzed"] == 2
    assert snap["dominant_emotion"] == "happiness"
    assert snap["people"][1]["box"] == [0.5, 0.5, 1.0, 1.0]
    assert sum(snap["emotions"].values()) == pytest.approx(1.0)


def test_room_forgets_people() -> None:
    agg = RoomAggregator(FERPLUS_LABELS, forget_s=5)
    agg.person(1, 0)
    agg.snapshot(20, [], {}, (10, 10))
    assert agg.people == {}


def test_emotion_meta_reads_sidecar(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from vibesight.vision.emotion import EmotionMeta

    model = tmp_path / "emotion.onnx"
    model.write_bytes(b"")
    model.with_suffix(".json").write_text(
        json.dumps({"name": "x", "input_size": 112, "source_size": 48, "temperature": 1.3, "extra": 1})
    )
    meta = EmotionMeta.for_model(model)
    assert (meta.name, meta.input_size, meta.source_size, meta.temperature) == ("x", 112, 48, 1.3)


def test_energy_calibration_points() -> None:
    """Hareketsiz-nötr-uyanık ≈ Orta; gülümseyen-hareketli = Yüksek; gözleri kapalı = Çok düşük."""
    neutral, lively, sleepy = PersonState(1), PersonState(2), PersonState(3)
    feed(neutral, 0, 50, blink=0.05, label="neutral")
    feed(lively, 0, 50, blink=0.05, label="happiness")
    feed(sleepy, 0, 50, blink=0.9, label="neutral")
    lively.motion = 0.08
    e = {n: p.energy(10, FERPLUS_LABELS) for n, p in (("n", neutral), ("l", lively), ("s", sleepy))}
    assert 40 <= e["n"] <= 55
    assert e["l"] >= 65
    assert e["s"] < 15


def test_model_valence_arousal_overrides_circumplex() -> None:
    """Model valans/uyarılmışlık veriyorsa (EmotiEffLib) çember eşlemesi yerine o kullanılır."""
    p = PersonState(1)
    p.observe_face(
        0,
        blink=0,
        jaw_open=0,
        yaw=0,
        pitch=0,
        box=np.zeros(4, np.float32),
        probs=onehot("neutral"),
        va=np.array([0.7, -0.2], np.float32),
    )
    assert p.valence_arousal(FERPLUS_LABELS) == pytest.approx((0.7, -0.2))


def test_color_model_preprocessing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Renkli (ImageNet normalizasyonlu) model girdisi doğru şekil ve ölçekte hazırlanır."""
    import json

    from vibesight.vision.emotion import EmotionClassifier, EmotionMeta

    model = tmp_path / "m.onnx"
    model.write_bytes(b"")
    model.with_suffix(".json").write_text(
        json.dumps(
            {
                "input_size": 224,
                "color": True,
                "va_outputs": True,
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
                "scale": 255.0,
            }
        )
    )
    clf = EmotionClassifier.__new__(EmotionClassifier)
    clf.meta = EmotionMeta.for_model(model)
    x = clf.preprocess([np.full((60, 50, 3), 255, np.uint8)])
    assert x.shape == (1, 3, 224, 224)
    assert x[0, 0, 0, 0] == pytest.approx((1 - 0.485) / 0.229, rel=1e-4)
