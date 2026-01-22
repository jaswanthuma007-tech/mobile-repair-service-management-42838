from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """
    Application settings loaded from environment variables.

    Notes:
    - SUPABASE_URL and SUPABASE_KEY are required for server-side verification via Supabase Auth API.
    - SUPABASE_JWT_SECRET is optional. If provided, we will validate JWTs locally using PyJWT
      (recommended). If not provided, we'll fall back to Supabase's auth.get_user(jwt) which
      requires a key that can access the Auth endpoint (service role key works).
    """

    # PUBLIC_INTERFACE
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase project URL (e.g., https://xyzcompany.supabase.co).",
    )

    # PUBLIC_INTERFACE
    supabase_key: Optional[str] = Field(
        default=None,
        description=(
            "Supabase API key for backend usage. Prefer SERVICE_ROLE key for server-side validation "
            "fallback if SUPABASE_JWT_SECRET is not provided."
        ),
    )

    # PUBLIC_INTERFACE
    supabase_jwt_secret: Optional[str] = Field(
        default=None,
        description=(
            "Optional: Supabase JWT secret used to verify access tokens locally (HS256). "
            "If absent, backend will validate via Supabase Auth API."
        ),
    )

    # PUBLIC_INTERFACE
    backend_base_url: Optional[str] = Field(
        default=None,
        description="Optional: externally reachable base URL of backend (for docs/links).",
    )


@lru_cache(maxsize=1)
# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Return cached Settings loaded from environment variables."""
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET"),
        backend_base_url=os.getenv("BACKEND_BASE_URL"),
    )
