"""Uygulama yapılandırması.

Tüm değerler ortam değişkenlerinden veya `.env` dosyasından okunur (önek: VIBESIGHT_).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIBESIGHT_", env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"), extra="ignore"
    )

    # --- Kaynak -------------------------------------------------------------------------------
    # "tapo" → aşağıdaki Tapo ayarlarından RTSP adresi kurulur
    # "0", "1" … → bilgisayar kamerası, "rtsp://…" → doğrudan adres, dosya yolu → video, "mock" → demo verisi
    source: str = "mock"
    tapo_host: str = ""
    tapo_user: str = ""
    tapo_password: str = ""
    tapo_stream: str = Field("stream1", pattern=r"^stream[12]$")

    # --- Modeller ------------------------------------------------------------------------------
    models_dir: Path = BACKEND_DIR / "models"
    detector_model: str = "yolox_s.onnx"
    face_model: str = "face_landmarker.task"
    emotion_model: str = "emotion.onnx"
    person_conf: float = 0.45
    min_face_px: int = 40
    max_faces_per_cycle: int = 12

    # --- Çalışma hızı ----------------------------------------------------------------------------
    analysis_hz: float = 6.0
    stream_fps: float = 15.0
    stream_width: int = 1280
    jpeg_quality: int = 80
    onnx_threads: int = 0  # 0 → otomatik

    # --- Gizlilik ve kayıt ------------------------------------------------------------------------
    privacy_blur: bool = False
    db_path: Path = BACKEND_DIR / "data" / "vibesight.sqlite3"
    history_interval_s: float = 5.0
    history_retention_days: int = 30

    # --- Sunucu ---------------------------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def resolved_source(self) -> str:
        """Ham kaynak dizgesini OpenCV'nin açabileceği bir değere çevirir."""
        if self.source.lower() == "tapo":
            if not (self.tapo_host and self.tapo_user and self.tapo_password):
                raise ValueError(
                    "Tapo kaynağı için VIBESIGHT_TAPO_HOST, VIBESIGHT_TAPO_USER ve "
                    "VIBESIGHT_TAPO_PASSWORD gerekli."
                )
            user = quote(self.tapo_user, safe="")
            pwd = quote(self.tapo_password, safe="")
            return f"rtsp://{user}:{pwd}@{self.tapo_host}:554/{self.tapo_stream}"
        return self.source

    def model_path(self, name: str) -> Path:
        return self.models_dir / name


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def redact(url: str) -> str:
    """Günlüklere şifre sızmaması için RTSP adresindeki kimlik bilgilerini gizler."""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***:***@{rest.split('@', 1)[1]}"
    return url
