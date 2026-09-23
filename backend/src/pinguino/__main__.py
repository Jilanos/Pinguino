"""Launch the local workbench: ``uv run python -m pinguino``."""

from __future__ import annotations

import multiprocessing

import uvicorn

from pinguino.config import load_settings


def main() -> None:
    settings = load_settings()
    print(f"Pinguino : http://{settings.host}:{settings.port}/", flush=True)
    uvicorn.run(
        "pinguino.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
