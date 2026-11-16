"""MediaPipe Face Landmarker (Apache-2.0) ile yüz noktaları, göz/çene blendshape'leri ve baş pozu.

Uzak/küçük yüzlerde başarımı artırmak için landmarker tüm kareye değil, her kişi kutusunun **baş bölgesine**
(büyütülmüş kırpıntı) uygulanır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

LEFT_EYE_OUTER, RIGHT_EYE_OUTER = 33, 263
CROP_TARGET = 288


@dataclass(slots=True)
class FaceObservation:
    box: np.ndarray  # yüz kutusu, kare koordinatlarında [x1, y1, x2, y2]
    aligned_gray: np.ndarray  # hizalanmış, kare, gri yüz kırpıntısı (FER2013 tarzı modeller için)
    face_rgb: np.ndarray  # yüz kutusunun renkli kırpıntısı (AffectNet tarzı modeller için)
    eye_blink: float  # 0 açık … 1 kapalı (iki gözün ortalaması)
    jaw_open: float  # 0 … 1
    smile: float  # 0 … 1
    yaw: float  # derece; 0 = kameraya dönük
    pitch: float  # derece; negatif = aşağı bakıyor
    roll: float

    @property
    def size(self) -> float:
        return float(min(self.box[2] - self.box[0], self.box[3] - self.box[1]))


def rotation_to_euler(matrix: np.ndarray) -> tuple[float, float, float]:
    """4×4 yüz dönüşüm matrisinden (yaw, pitch, roll) derece cinsinden."""
    r = matrix[:3, :3]
    sy = math.hypot(r[0, 0], r[1, 0])
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    yaw = math.degrees(math.atan2(-r[2, 0], sy))
    roll = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return yaw, pitch, roll


def head_region(box: np.ndarray, frame_shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    """Kişi kutusunun üst kısmından kare bir baş bölgesi seçer (oturan/ayakta kişiler için)."""
    x1, y1, x2, y2 = box
    w = x2 - x1
    side = min(w * 1.1, (y2 - y1))
    cx = (x1 + x2) / 2
    top = y1 - 0.05 * side
    h, fw = frame_shape[:2]
    rx1, ry1 = max(0, int(cx - side / 2)), max(0, int(top))
    rx2, ry2 = min(fw, int(cx + side / 2)), min(h, int(top + side))
    return rx1, ry1, rx2, ry2


class FaceAnalyzer:
    def __init__(self, model_path: Path) -> None:
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def close(self) -> None:
        self._landmarker.close()

    def analyze(
        self, frame: np.ndarray, person_box: np.ndarray, *, min_face_px: int = 40
    ) -> FaceObservation | None:
        x1, y1, x2, y2 = head_region(person_box, frame.shape)
        if x2 - x1 < min_face_px or y2 - y1 < min_face_px:
            return None
        crop = frame[y1:y2, x1:x2]
        scale = CROP_TARGET / max(crop.shape[:2])
        if scale > 1:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        else:
            scale = 1.0
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not result.face_landmarks:
            return None

        ch, cw = crop.shape[:2]
        pts = np.array([(p.x * cw, p.y * ch) for p in result.face_landmarks[0]], dtype=np.float32)
        fx1, fy1 = pts.min(axis=0)
        fx2, fy2 = pts.max(axis=0)
        face_box = np.array(
            [fx1 / scale + x1, fy1 / scale + y1, fx2 / scale + x1, fy2 / scale + y1], np.float32
        )
        if min(face_box[2] - face_box[0], face_box[3] - face_box[1]) < min_face_px * 0.6:
            return None

        bs = {c.category_name: c.score for c in result.face_blendshapes[0]} if result.face_blendshapes else {}
        if result.facial_transformation_matrixes:
            yaw, pitch, roll = rotation_to_euler(np.asarray(result.facial_transformation_matrixes[0]))
        else:
            yaw = pitch = roll = 0.0

        return FaceObservation(
            box=face_box,
            aligned_gray=self._align(crop, pts),
            face_rgb=self._box_crop(crop, pts),
            eye_blink=(bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0)) / 2,
            jaw_open=bs.get("jawOpen", 0.0),
            smile=(bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0)) / 2,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
        )

    @staticmethod
    def _box_crop(crop: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Yüz noktalarının kapsadığı kutu, RGB (EmotiEffLib modelleri hizalamasız yüz kutusuyla eğitildi)."""
        h, w = crop.shape[:2]
        x1, y1 = np.floor(pts.min(axis=0)).astype(int)
        x2, y2 = np.ceil(pts.max(axis=0)).astype(int)
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        return cv2.cvtColor(crop[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)

    @staticmethod
    def _align(crop: np.ndarray, pts: np.ndarray, out: int = 128) -> np.ndarray:
        """Gözleri yatay hizaya getirip yüzü kare olarak kırpar (FER veri setleriyle benzer kadraj)."""
        le, re = pts[LEFT_EYE_OUTER], pts[RIGHT_EYE_OUTER]
        angle = math.degrees(math.atan2(re[1] - le[1], re[0] - le[0]))
        center = pts.mean(axis=0)
        size = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))) * 1.15
        m = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), angle, out / size)
        m[0, 2] += out / 2 - center[0]
        m[1, 2] += out / 2 - center[1]
        aligned = cv2.warpAffine(crop, m, (out, out), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
