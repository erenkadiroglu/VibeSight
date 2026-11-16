"""YOLOX (Apache-2.0) ile kişi tespiti — ONNX Runtime üzerinde, PyTorch gerektirmez."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

PERSON_CLASS = 0  # COCO


@dataclass(slots=True)
class Detection:
    box: np.ndarray  # [x1, y1, x2, y2] piksel
    score: float


def make_session(path: Path | bytes, threads: int = 0) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if threads:
        opts.intra_op_num_threads = threads
    providers = [
        p
        for p in ("CUDAExecutionProvider", "CoreMLExecutionProvider", "DmlExecutionProvider")
        if p in ort.get_available_providers()
    ] + ["CPUExecutionProvider"]
    return ort.InferenceSession(
        path if isinstance(path, bytes) else str(path), sess_options=opts, providers=providers
    )


class PersonDetector:
    def __init__(self, model_path: Path, *, conf: float = 0.45, nms: float = 0.5, threads: int = 0) -> None:
        self.session = make_session(model_path, threads)
        self.input_name = self.session.get_inputs()[0].name
        _, _, h, w = self.session.get_inputs()[0].shape
        self.input_size = (int(h), int(w))
        self.conf = conf
        self.nms = nms
        self._grids, self._strides = self._make_grids(self.input_size)

    @staticmethod
    def _make_grids(size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
        grids, strides = [], []
        for stride in (8, 16, 32):
            hs, ws = size[0] // stride, size[1] // stride
            xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((hs * ws, 1), stride))
        return np.concatenate(grids).astype(np.float32), np.concatenate(strides).astype(np.float32)

    def _letterbox(self, img: np.ndarray) -> tuple[np.ndarray, float]:
        ih, iw = self.input_size
        r = min(ih / img.shape[0], iw / img.shape[1])
        resized = cv2.resize(
            img, (int(img.shape[1] * r), int(img.shape[0] * r)), interpolation=cv2.INTER_LINEAR
        )
        padded = np.full((ih, iw, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized
        return np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32), r

    def decode(self, raw: np.ndarray, ratio: float) -> list[Detection]:
        """Ham YOLOX çıktısını (1, N, 85) kişi kutularına çevirir."""
        out = raw[0]
        xy = (out[:, :2] + self._grids) * self._strides
        wh = np.exp(out[:, 2:4]) * self._strides
        scores = out[:, 4] * out[:, 5 + PERSON_CLASS]
        keep = scores >= self.conf
        if not keep.any():
            return []
        xy, wh, scores = xy[keep], wh[keep], scores[keep]
        boxes = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1) / ratio
        xywh = np.concatenate([boxes[:, :2], boxes[:, 2:] - boxes[:, :2]], axis=1)
        idx = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), self.conf, self.nms)
        return [Detection(boxes[i], float(scores[i])) for i in np.array(idx).flatten()]

    def __call__(self, img: np.ndarray) -> list[Detection]:
        tensor, ratio = self._letterbox(img)
        raw = self.session.run(None, {self.input_name: tensor})[0]
        dets = self.decode(raw, ratio)
        h, w = img.shape[:2]
        for d in dets:
            d.box = np.clip(d.box, [0, 0, 0, 0], [w - 1, h - 1, w - 1, h - 1])
        return [d for d in dets if (d.box[2] - d.box[0]) > 8 and (d.box[3] - d.box[1]) > 8]
