"""
Module entrypoint for running the backend API.

This is intentionally provided so environments that don't have a custom start
script can run:

    python -m src

It will:
- Load environment variables (including from `.env` if present, via src.api.main import side-effects)
- Start uvicorn bound to 0.0.0.0 and PORT (default 3001)

Note:
- In production you may still prefer: uvicorn src.api.main:app --host 0.0.0.0 --port 3001
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run uvicorn server for the FastAPI app on the configured port."""
    host = os.getenv("HOST") or os.getenv("UVICORN_HOST") or "0.0.0.0"
    port_raw = os.getenv("PORT", "3001")
    try:
        port = int(port_raw)
    except ValueError:
        port = 3001

    uvicorn.run("src.api.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
