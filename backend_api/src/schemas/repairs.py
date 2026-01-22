from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RepairStatus(str):
    """
    Supported repair status values.

    Kept as string subclass (not Enum) to avoid coupling to DB enum configuration.
    """

    # common statuses:
    # requested -> diagnosed -> in_progress -> ready -> completed
    # plus: cancelled
    pass


class RepairCreate(BaseModel):
    """Payload to create a repair request (customer)."""

    device_type: str = Field(..., description="Device type (e.g., iPhone 13, Galaxy S21).")
    issue_description: str = Field(..., description="Problem description from customer.")
    preferred_contact: Optional[str] = Field(
        default=None, description="Optional contact preference/notes."
    )


class RepairUpdate(BaseModel):
    """Patchable fields for a repair (admin/customer limited by role guards)."""

    device_type: Optional[str] = Field(default=None, description="Device type.")
    issue_description: Optional[str] = Field(default=None, description="Issue description.")
    preferred_contact: Optional[str] = Field(default=None, description="Contact notes.")


class RepairAssignRequest(BaseModel):
    """Assign a technician to a repair (admin)."""

    technician_user_id: str = Field(..., description="Supabase user id of technician.")


class RepairStatusChangeRequest(BaseModel):
    """Request to transition status and add a history note."""

    new_status: str = Field(..., description="New status to set.")
    note: Optional[str] = Field(default=None, description="Optional status change note.")


class RepairStatusHistoryItem(BaseModel):
    """One status transition history item."""

    id: str = Field(..., description="History row id.")
    repair_id: str = Field(..., description="Repair id.")
    from_status: Optional[str] = Field(default=None, description="Previous status.")
    to_status: str = Field(..., description="New status.")
    note: Optional[str] = Field(default=None, description="Optional note.")
    changed_by: str = Field(..., description="User id who performed the change.")
    created_at: Optional[datetime] = Field(default=None, description="When the change happened.")


class RepairRead(BaseModel):
    """Repair object returned by API."""

    id: str = Field(..., description="Repair id.")
    customer_user_id: str = Field(..., description="Customer owner user id.")
    technician_user_id: Optional[str] = Field(
        default=None, description="Assigned technician user id."
    )

    device_type: str = Field(..., description="Device type.")
    issue_description: str = Field(..., description="Issue description.")
    preferred_contact: Optional[str] = Field(default=None, description="Contact notes.")

    status: str = Field(..., description="Current repair status.")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp.")
    updated_at: Optional[datetime] = Field(default=None, description="Update timestamp.")


class RepairDetail(RepairRead):
    """Repair detail including status history."""

    history: List[RepairStatusHistoryItem] = Field(
        default_factory=list, description="Status change history (newest first)."
    )


class RepairsListResponse(BaseModel):
    """List wrapper for consistent API responses."""

    items: List[RepairRead] = Field(default_factory=list, description="Repair items.")


class AdminRepairsSummary(BaseModel):
    """High-level admin summary for dashboard stats and recent repairs list."""

    total: int = Field(..., description="Total number of repairs.")
    counts_by_status: Dict[str, int] = Field(
        default_factory=dict, description="Counts grouped by current repair status."
    )
    recent_repairs: List[RepairRead] = Field(
        default_factory=list,
        description="Most recently created repairs (newest first).",
    )
