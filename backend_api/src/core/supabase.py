from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client  # type: ignore

from src.core.settings import Settings, get_settings


@lru_cache(maxsize=1)
# PUBLIC_INTERFACE
def get_supabase_client() -> Client:
    """
    Return a cached Supabase client configured from environment settings.

    Requires:
      - SUPABASE_URL
      - SUPABASE_KEY

    Notes:
    - Do not hardcode secrets. Values are read via Settings from environment.
    """
    settings: Settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError(
            "Supabase client not configured: set SUPABASE_URL and SUPABASE_KEY"
        )
    return create_client(settings.supabase_url, settings.supabase_key)
