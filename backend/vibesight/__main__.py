"""`python -m vibesight` veya `vibesight` komutu ile sunucuyu başlatır."""

from __future__ import annotations

import argparse
import logging

import uvicorn

from vibesight.api.app import create_app
from vibesight.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vibesight", description="VibeSight — gerçek zamanlı ortam analizi sunucusu"
    )
    parser.add_argument("--source", help="tapo | mock | 0 (webcam) | rtsp://… | video.mp4")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()

    settings = get_settings()
    if args.source:
        settings.source = args.source
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
