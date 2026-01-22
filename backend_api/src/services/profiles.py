from __future__ import annotations

from typing import Any, Dict, Optional

from supabase import Client  # type: ignore

from src.api.errors import http_400, http_404
from src.schemas.profiles import ProfileRead, ProfileUpsert


def _as_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "model_dump"):
        return row.model_dump()
    return dict(row)


class ProfileService:
    """Service layer for profile data access."""

    def __init__(self, sb: Client):
        self._sb = sb

    # PUBLIC_INTERFACE
    def get_profile(self, user_id: str) -> ProfileRead:
        """Fetch a user's profile row."""
        res = self._sb.table("profiles").select("*").eq("user_id", user_id).limit(1).execute()
        data = getattr(res, "data", None)
        if not data:
            raise http_404("Profile not found")
        return ProfileRead(**_as_dict(data[0]))

    # PUBLIC_INTERFACE
    def upsert_profile(self, user_id: str, payload: ProfileUpsert) -> ProfileRead:
        """
        Upsert the profile row for a user.

        Requires a `profiles` table with unique constraint on `user_id`.
        """
        if payload.role not in {"customer", "technician", "admin"}:
            raise http_400("Invalid role")

        row = {"user_id": user_id, "role": payload.role, "full_name": payload.full_name}
        res = (
            self._sb.table("profiles")
            .upsert(row, on_conflict="user_id")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", None)
        if not data:
            # Some PostgREST setups return data only if `Prefer: return=representation`
            # Supabase python client sets this automatically for select() chaining.
            raise http_400("Unable to upsert profile")
        return ProfileRead(**_as_dict(data[0]))

    # PUBLIC_INTERFACE
    def get_role_for_user(self, user_id: str) -> Optional[str]:
        """Convenience helper to read role string for authorization decisions."""
        res = self._sb.table("profiles").select("role").eq("user_id", user_id).limit(1).execute()
        data = getattr(res, "data", None)
        if not data:
            return None
        d = _as_dict(data[0])
        role = d.get("role")
        return role if isinstance(role, str) else None
