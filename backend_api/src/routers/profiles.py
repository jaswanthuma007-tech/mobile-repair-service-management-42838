from __future__ import annotations

from fastapi import APIRouter, Depends

from src.auth.deps import CurrentUser, Role, get_current_user, require_role
from src.core.supabase import get_supabase_client
from src.schemas.profiles import ProfileRead, ProfileUpsert
from src.services.profiles import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def _svc() -> ProfileService:
    return ProfileService(get_supabase_client())


@router.get(
    "/me",
    summary="Get current user's profile",
    description="Returns the profile row for the authenticated user.",
    response_model=ProfileRead,
    operation_id="profiles_me_get",
)
# PUBLIC_INTERFACE
async def get_my_profile(user: CurrentUser = Depends(get_current_user)) -> ProfileRead:
    """Get the profile for the current user."""
    return _svc().get_profile(user.user_id)


@router.put(
    "/me",
    summary="Upsert current user's profile",
    description="Creates or updates the caller's profile row.",
    response_model=ProfileRead,
    operation_id="profiles_me_put",
)
# PUBLIC_INTERFACE
async def upsert_my_profile(
    payload: ProfileUpsert, user: CurrentUser = Depends(get_current_user)
) -> ProfileRead:
    """Upsert the profile for the current user."""
    return _svc().upsert_profile(user.user_id, payload)


@router.get(
    "/{user_id}",
    summary="Get a user's profile (admin)",
    description="Admin-only endpoint to fetch an arbitrary user's profile.",
    response_model=ProfileRead,
    operation_id="profiles_user_get",
)
# PUBLIC_INTERFACE
async def get_profile_admin(
    user_id: str, _: CurrentUser = Depends(require_role(Role.admin))
) -> ProfileRead:
    """Fetch a profile by user_id (admin only)."""
    return _svc().get_profile(user_id)
