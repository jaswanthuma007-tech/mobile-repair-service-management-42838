from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    """Base profile fields."""

    user_id: str = Field(..., description="Supabase auth user id.")
    role: str = Field(..., description="Application role: customer|technician|admin.")
    full_name: Optional[str] = Field(default=None, description="Display name.")


class ProfileRead(ProfileBase):
    """Profile returned by API."""

    created_at: Optional[datetime] = Field(
        default=None, description="Creation timestamp (if available)."
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Last update timestamp (if available)."
    )


class ProfileUpsert(BaseModel):
    """Upsert the caller's profile record."""

    role: str = Field(..., description="Role to set for the user profile.")
    full_name: Optional[str] = Field(default=None, description="Display name.")


class ProfilesListResponse(BaseModel):
    """List wrapper for consistent API responses."""

    items: List[ProfileRead] = Field(default_factory=list, description="Profile items.")
