"""Kamera bağlantısını VibeSight'ı başlatmadan test eder.

Kullanım:  make camera-test   (veya: cd backend && uv run python ../scripts/camera_test.py)
"""

from __future__ import annotations

import sys
import time

import cv2

from vibesight.config import get_settings, redact
from vibesight.sources.capture import FrameSource, SourceStatus


def main() -> int:
    settings = get_settings()
    try:
        uri = settings.resolved_source()
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    if uri == "mock":
        print(
            "✗ Kaynak demo modunda. Kamerayı test etmek için backend/.env içinde VIBESIGHT_SOURCE=tapo yapın."
        )
        return 1

    print(f"→ Bağlanılıyor: {redact(uri)}")
    src = FrameSource(uri).start()
    deadline = time.time() + 15
    while time.time() < deadline and src.status != SourceStatus.LIVE:
        time.sleep(0.2)
    if src.status != SourceStatus.LIVE:
        src.stop()
        print("✗ 15 sn içinde görüntü alınamadı. docs/CAMERA_SETUP.md → Sorun giderme bölümüne bakın.")
        return 1

    time.sleep(3)
    frame = src.latest()
    src.stop()
    assert frame is not None
    cv2.imwrite("camera_test.jpg", frame.image)
    w, h = src.resolution or (0, 0)
    print(f"✓ Bağlantı başarılı: {w}×{h}, ~{src.fps:.1f} FPS")
    print("✓ Örnek kare kaydedildi: backend/camera_test.jpg (kontrol ettikten sonra silebilirsiniz)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
