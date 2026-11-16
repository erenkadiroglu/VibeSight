"""Kişi başı zamansal durum ve oda düzeyinde toplama.

Tüm metrikler gürültülü tek kare tahminleri yerine zaman içinde yumuşatılmış değerlerdir.
Saklanan hiçbir şey bir kimliğe bağlı değildir; kişi durumu, kişi kadrajdan çıktıktan kısa süre sonra silinir.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from vibesight.analytics.affect import LABELS_TR, valence_arousal

ENGAGEMENT_WINDOW = 128  # EmotiEffLib'in eğitimdeki kayan pencere uzunluğu
ENGAGEMENT_MIN_FRAMES = 32  # daha kısa dizide tahmin verilmez ("ısınıyor")
ENGAGEMENT_EVERY_S = 1.0
EMOTION_ALPHA = 0.5  # 6 Hz'de ~0.3 sn'lik yumuşatma: tek kare gürültüsünü bastırır, gecikme hissettirmez
PERCLOS_WINDOW_S = 30.0
EYES_CLOSED_THRESHOLD = 0.55
YAWN_THRESHOLD = 0.55
YAWN_MIN_S = 1.2
YAWN_MEMORY_S = 60.0
FACE_STALE_S = 3.0
ATTENTION_MAX_YAW = 25.0
ATTENTION_MIN_PITCH = -20.0

# Enerji endeksi (docs/PLAN.md §2.3):
#   canlılık = 0.6·uyarılmışlık' + 0.4·hareket'          (ifade ve beden ne kadar hareketli)
#   enerji   = 100 · (0.25 + 0.75·canlılık) · uyanıklık · (esneme varsa 0.8)
# Ayar noktaları: hareketsiz, nötr, uyanık kişi ≈ 47 (Orta); gülümseyen ve hareketli ≈ 75 (Yüksek);
# gözleri sık kapanan kişi < 20 (Çok düşük).
W_AROUSAL, W_MOTION = 0.6, 0.4
ENERGY_FLOOR = 0.25
YAWN_PENALTY = 0.8
POSITIVE_EMOTIONS = {"happiness", "surprise"}


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def ema(prev: float | None, value: float, alpha: float) -> float:
    return value if prev is None else alpha * value + (1 - alpha) * prev


@dataclass
class PersonState:
    track_id: int
    emotion: np.ndarray | None = None
    va: np.ndarray | None = None  # modelin doğrudan verdiği (valans, uyarılmışlık), varsa
    yaw: float | None = None
    pitch: float | None = None
    motion: float | None = None
    last_face_t: float = 0.0
    face_box: np.ndarray | None = None
    _eyes: deque[tuple[float, bool]] = field(default_factory=deque)
    _jaw_open_since: float | None = None
    _last_yawn_t: float = -1e9
    yawns: int = 0
    # Öğrenilmiş katılım modeli için son ~10 sn'nin yüz öznitelikleri ve son tahmin
    features: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=ENGAGEMENT_WINDOW))
    engagement: float | None = None
    engagement_t: float = 0.0

    @property
    def engagement_progress(self) -> float:
        """Katılım tahmini için gereken en az kare sayısına ne kadar yaklaşıldı (0–1)."""
        return min(1.0, len(self.features) / ENGAGEMENT_MIN_FRAMES)

    def observe_motion(self, value: float) -> None:
        self.motion = ema(self.motion, value, 0.3)

    def observe_face(
        self,
        now: float,
        *,
        blink: float,
        jaw_open: float,
        yaw: float,
        pitch: float,
        box: np.ndarray,
        probs: np.ndarray | None,
        va: np.ndarray | None = None,
    ) -> None:
        self.last_face_t = now
        self.face_box = box
        self.yaw = ema(self.yaw, yaw, 0.4)
        self.pitch = ema(self.pitch, pitch, 0.4)
        if probs is not None:
            self.emotion = (
                probs if self.emotion is None else EMOTION_ALPHA * probs + (1 - EMOTION_ALPHA) * self.emotion
            )
        if va is not None:
            self.va = va if self.va is None else EMOTION_ALPHA * va + (1 - EMOTION_ALPHA) * self.va

        self._eyes.append((now, blink >= EYES_CLOSED_THRESHOLD))
        while self._eyes and now - self._eyes[0][0] > PERCLOS_WINDOW_S:
            self._eyes.popleft()

        if jaw_open >= YAWN_THRESHOLD:
            if self._jaw_open_since is None:
                self._jaw_open_since = now
            elif now - self._jaw_open_since >= YAWN_MIN_S and now - self._last_yawn_t > 5.0:
                self._last_yawn_t = now
                self.yawns += 1
        else:
            self._jaw_open_since = None

    def has_face(self, now: float) -> bool:
        return now - self.last_face_t <= FACE_STALE_S

    @property
    def perclos(self) -> float:
        if len(self._eyes) < 3:
            return 0.0
        return sum(closed for _, closed in self._eyes) / len(self._eyes)

    def yawned_recently(self, now: float) -> bool:
        return now - self._last_yawn_t <= YAWN_MEMORY_S

    @property
    def attentive(self) -> bool | None:
        if self.yaw is None or self.pitch is None:
            return None
        return abs(self.yaw) <= ATTENTION_MAX_YAW and self.pitch >= ATTENTION_MIN_PITCH

    def valence_arousal(self, labels: list[str]) -> tuple[float, float]:
        """Modelin valans/uyarılmışlık çıktısı; yoksa ifade olasılıklarının çember eşlemesi."""
        if self.va is not None:
            return float(self.va[0]), float(self.va[1])
        if self.emotion is not None:
            return valence_arousal(self.emotion, labels)
        return 0.0, 0.0

    def energy_components(self, now: float, labels: list[str]) -> dict[str, float] | None:
        """Enerjiyi oluşturan bileşenler (0–1); arayüz bunları kişi ayrıntısında gösterir."""
        if not self.has_face(now):
            return None
        arousal = self.valence_arousal(labels)[1]
        return {
            "arousal": (arousal + 1) / 2,
            "motion": clamp01((self.motion or 0.0) / 0.12),
            # Gözler sık kapansa da 0'a inmez: çok uykulu biri "çok düşük" enerjidedir, "sıfır" değil
            "alertness": 1.0 - 0.85 * clamp01(self.perclos / 0.4),
            "yawn": 1.0 if self.yawned_recently(now) else 0.0,
        }

    def energy(self, now: float, labels: list[str]) -> float | None:
        c = self.energy_components(now, labels)
        if c is None:
            return None
        liveliness = W_AROUSAL * c["arousal"] + W_MOTION * c["motion"]
        score = (ENERGY_FLOOR + (1 - ENERGY_FLOOR) * liveliness) * c["alertness"]
        return 100.0 * score * (YAWN_PENALTY if c["yawn"] else 1.0)


@dataclass
class Atmosphere:
    key: str
    label: str
    tone: str  # positive | focused | calm | tired | tense | unknown
    description: str


def classify_atmosphere(
    *,
    faces: int,
    energy: float | None,
    valence: float | None,
    arousal: float | None,
    attention: float | None,
    perclos: float | None,
    dominant: str | None = None,
    engagement: float | None = None,
) -> Atmosphere:
    if faces == 0 or energy is None:
        return Atmosphere("unknown", "Veri bekleniyor", "unknown", "Analiz için yeterli yüz görünmüyor.")
    if energy < 35 and (perclos or 0) >= 0.2:
        return Atmosphere(
            "tired", "Yorgun", "tired", "Göz kapanma oranı yüksek, enerji düşük. Kısa bir mola iyi gelebilir."
        )
    if valence is not None and arousal is not None and valence <= -0.2 and arousal >= 0.25:
        return Atmosphere(
            "tense", "Gergin", "tense", "Olumsuz ve yüksek uyarılmışlık gösteren ifadeler baskın."
        )
    if dominant in POSITIVE_EMOTIONS and valence is not None and valence >= 0.3 and energy >= 55:
        return Atmosphere(
            "positive", "Pozitif & Enerjik", "positive", "Olumlu ifadeler ve yüksek enerji gözleniyor."
        )
    if engagement is not None:  # öğrenilmiş katılım modeli varsa baş açısı kuralının yerine o kullanılır
        if engagement < 0.35:
            return Atmosphere(
                "distracted",
                "Dikkat dağınık",
                "tired",
                "Katılım modeli çoğunluğu dalgın olarak sınıflandırıyor.",
            )
        if engagement >= 0.6 and energy >= 40:
            return Atmosphere(
                "focused", "Odaklı", "focused", "Katılım modeli çoğunluğu derse katılımcı görüyor."
            )
    elif (attention or 0) >= 0.65 and energy >= 40:
        return Atmosphere("focused", "Odaklı", "focused", "Çoğunluk ön tarafa dönük ve uyanık görünüyor.")
    if energy < 40:
        return Atmosphere("calm", "Sakin / Düşük tempo", "calm", "Enerji ortalamanın altında, ortam durgun.")
    return Atmosphere("balanced", "Dengeli", "focused", "Belirgin bir eğilim yok; ortam dengeli.")


class RoomAggregator:
    """Kişi durumlarını tutar ve her analiz döngüsünde oda anlık görüntüsünü üretir."""

    def __init__(self, labels: list[str], *, count_window_s: float = 2.0, forget_s: float = 10.0) -> None:
        self.labels = labels
        self.count_window_s = count_window_s
        self.forget_s = forget_s
        self.people: dict[int, PersonState] = {}
        self._counts: deque[tuple[float, int]] = deque()
        self._last_seen: dict[int, float] = {}
        self.peak_count = 0

    def person(self, track_id: int, now: float) -> PersonState:
        self._last_seen[track_id] = now
        return self.people.setdefault(track_id, PersonState(track_id))

    def snapshot(
        self, now: float, active_ids: list[int], boxes: dict[int, np.ndarray], frame_size: tuple[int, int]
    ) -> dict[str, Any]:
        for tid in [t for t, seen in self._last_seen.items() if now - seen > self.forget_s]:
            self._last_seen.pop(tid, None)
            self.people.pop(tid, None)

        self._counts.append((now, len(active_ids)))
        while self._counts and now - self._counts[0][0] > self.count_window_s:
            self._counts.popleft()
        count = round(statistics.median(c for _, c in self._counts))
        self.peak_count = max(self.peak_count, count)

        w, h = frame_size
        faced = [self.people[t] for t in active_ids if t in self.people and self.people[t].has_face(now)]
        with_emotion = [p for p in faced if p.emotion is not None]

        distribution = None
        valence = arousal = None
        if with_emotion:
            mean_probs = np.mean([p.emotion for p in with_emotion if p.emotion is not None], axis=0)
            distribution = {lbl: float(v) for lbl, v in zip(self.labels, mean_probs, strict=True)}
            vas = [p.valence_arousal(self.labels) for p in with_emotion]
            valence = float(np.mean([v for v, _ in vas]))
            arousal = float(np.mean([a for _, a in vas]))

        energies = [e for p in faced if (e := p.energy(now, self.labels)) is not None]
        energy = float(np.mean(energies)) if energies else None
        att_flags = [a for p in faced if (a := p.attentive) is not None]
        attention = (sum(att_flags) / len(att_flags)) if att_flags else None
        perclos = float(np.mean([p.perclos for p in faced])) if faced else None
        engaged = [p.engagement for p in faced if p.engagement is not None]
        engagement = float(np.mean(engaged)) if engaged else None
        motion = [p.motion for t in active_ids if (p := self.people.get(t)) and p.motion is not None]
        activity = clamp01(float(np.mean(motion)) / 0.12) * 100 if motion else None

        dominant = max(distribution, key=lambda k: distribution[k]) if distribution else None
        atmosphere = classify_atmosphere(
            dominant=dominant,
            faces=len(faced),
            energy=energy,
            valence=valence,
            arousal=arousal,
            attention=attention,
            perclos=perclos,
            engagement=engagement,
        )

        people_out = []
        for tid in active_ids:
            p = self.people.get(tid)
            box = boxes[tid]
            item: dict[str, Any] = {
                "id": tid,
                "box": [
                    round(float(box[0]) / w, 4),
                    round(float(box[1]) / h, 4),
                    round(float(box[2]) / w, 4),
                    round(float(box[3]) / h, 4),
                ],
            }
            if p is not None and p.has_face(now):
                if p.face_box is not None:
                    fb = p.face_box
                    item["face"] = [
                        round(float(fb[0]) / w, 4),
                        round(float(fb[1]) / h, 4),
                        round(float(fb[2]) / w, 4),
                        round(float(fb[3]) / h, 4),
                    ]
                if p.emotion is not None:
                    i = int(np.argmax(p.emotion))
                    item["emotion"] = self.labels[i]
                    item["emotion_label"] = LABELS_TR.get(self.labels[i], self.labels[i])
                    item["confidence"] = round(float(p.emotion[i]), 3)
                    item["probs"] = {
                        lbl: round(float(v), 3) for lbl, v in zip(self.labels, p.emotion, strict=True)
                    }
                e = p.energy(now, self.labels)
                item["energy"] = round(e, 1) if e is not None else None
                item["attentive"] = p.attentive
                item["engagement"] = round(p.engagement, 3) if p.engagement is not None else None
                item["engagement_progress"] = round(p.engagement_progress, 2)
                # Ayrıntı kartı için ham sinyaller: kullanıcı her sayının nereden geldiğini görebilsin
                comps = p.energy_components(now, self.labels)
                item["signals"] = {
                    "perclos": round(p.perclos, 3),
                    "yaw": round(p.yaw, 1) if p.yaw is not None else None,
                    "pitch": round(p.pitch, 1) if p.pitch is not None else None,
                    "yawns": p.yawns,
                    "valence": round(p.valence_arousal(self.labels)[0], 3),
                    **({k: round(v, 3) for k, v in comps.items()} if comps else {}),
                }
            people_out.append(item)

        return {
            "t": now,
            "count": count,
            "raw_count": len(active_ids),
            "peak_count": self.peak_count,
            "faces_analyzed": len(faced),
            "emotions": distribution,
            "dominant_emotion": dominant,
            "dominant_emotion_label": LABELS_TR.get(dominant, dominant) if dominant else None,
            "valence": valence,
            "arousal": arousal,
            "energy": energy,
            "attention": attention,
            "engagement": engagement,
            "engagement_people": len(engaged),
            "perclos": perclos,
            "activity": activity,
            "yawns_recent": sum(p.yawned_recently(now) for p in faced),
            "atmosphere": asdict(atmosphere),
            "people": people_out,
        }
