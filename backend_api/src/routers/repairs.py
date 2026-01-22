from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.errors import http_403
from src.auth.deps import CurrentUser, Role, get_current_user, require_role
from src.core.supabase import get_supabase_client
from src.schemas.repairs import (
    RepairAssignRequest,
    RepairCreate,
    RepairDetail,
    RepairRead,
    RepairStatusChangeRequest,
    RepairStatusHistoryItem,
    RepairUpdate,
    RepairsListResponse,
)
from src.services.repairs import RepairService

router = APIRouter(prefix="/repairs", tags=["Repairs"])


def _svc() -> RepairService:
    return RepairService(get_supabase_client())


def _has_role(user: CurrentUser, role: Role) -> bool:
    return role.value in user.role_set()


def _assert_can_view_repair(user: CurrentUser, repair: RepairRead) -> None:
    if _has_role(user, Role.admin):
        return
    if _has_role(user, Role.customer) and repair.customer_user_id == user.user_id:
        return
    if _has_role(user, Role.technician) and repair.technician_user_id == user.user_id:
        return
    raise http_403("Not allowed to view this repair")


@router.post(
    "",
    summary="Create a repair (customer)",
    description="Customer-only: create a new repair request owned by the authenticated user.",
    response_model=RepairRead,
    operation_id="repairs_create",
)
# PUBLIC_INTERFACE
async def create_repair(
    payload: RepairCreate,
    user: CurrentUser = Depends(require_role(Role.customer, Role.admin)),
) -> RepairRead:
    """
    Create a repair request.

    Notes:
    - Customers create their own repairs.
    - Admins may also create repairs (for assisted intake flows).
    """
    return _svc().create_repair(user.user_id, payload)


@router.get(
    "",
    summary="List repairs (role-scoped)",
    description=(
        "Customers: list own repairs. Technicians: list assigned repairs. Admins: list all repairs."
    ),
    response_model=RepairsListResponse,
    operation_id="repairs_list",
)
# PUBLIC_INTERFACE
async def list_repairs(user: CurrentUser = Depends(get_current_user)) -> RepairsListResponse:
    """List repairs scoped to the caller's role."""
    svc = _svc()
    if _has_role(user, Role.admin):
        items = svc.list_repairs_for_admin()
    elif _has_role(user, Role.technician):
        items = svc.list_repairs_for_technician(user.user_id)
    else:
        # default to customer scoping
        items = svc.list_repairs_for_customer(user.user_id)
    return RepairsListResponse(items=items)


@router.get(
    "/{repair_id}",
    summary="Get repair detail (role-scoped)",
    description="Customers can view own, technicians assigned, admins all. Includes status history.",
    response_model=RepairDetail,
    operation_id="repairs_detail",
)
# PUBLIC_INTERFACE
async def get_repair_detail(
    repair_id: str, user: CurrentUser = Depends(get_current_user)
) -> RepairDetail:
    """Get repair detail with history, enforcing role-based access."""
    detail = _svc().get_repair_detail(repair_id)
    _assert_can_view_repair(user, RepairRead(**detail.model_dump(exclude={"history"})))
    return detail


@router.patch(
    "/{repair_id}",
    summary="Update repair fields (role-scoped)",
    description=(
        "Customers can update basic fields on their own repairs; "
        "admins can update any repair. Technicians should use status endpoint."
    ),
    response_model=RepairRead,
    operation_id="repairs_patch",
)
# PUBLIC_INTERFACE
async def patch_repair(
    repair_id: str, payload: RepairUpdate, user: CurrentUser = Depends(get_current_user)
) -> RepairRead:
    """Patch repair fields."""
    svc = _svc()
    # fetch current to enforce ownership
    current = svc.get_repair_detail(repair_id)
    base = RepairRead(**current.model_dump(exclude={"history"}))
    if _has_role(user, Role.admin):
        return svc.patch_repair(repair_id, payload)
    if _has_role(user, Role.customer) and base.customer_user_id == user.user_id:
        return svc.patch_repair(repair_id, payload)
    raise http_403("Not allowed to update this repair")


@router.post(
    "/{repair_id}/assign",
    summary="Assign a technician (admin)",
    description="Admin-only: assign technician_user_id to a repair.",
    response_model=RepairRead,
    operation_id="repairs_assign",
)
# PUBLIC_INTERFACE
async def assign_technician(
    repair_id: str,
    payload: RepairAssignRequest,
    user: CurrentUser = Depends(require_role(Role.admin)),
) -> RepairRead:
    """Assign a technician to a repair (admin only)."""
    return _svc().assign_technician(repair_id, payload, changed_by=user.user_id)


@router.post(
    "/{repair_id}/status",
    summary="Change repair status (technician/admin)",
    description=(
        "Technicians can change status for repairs assigned to them. Admins can change any repair."
    ),
    response_model=RepairStatusHistoryItem,
    operation_id="repairs_change_status",
)
# PUBLIC_INTERFACE
async def change_repair_status(
    repair_id: str, payload: RepairStatusChangeRequest, user: CurrentUser = Depends(get_current_user)
) -> RepairStatusHistoryItem:
    """Change status and return the newly-created history record."""
    svc = _svc()
    current = svc.get_repair_detail(repair_id)
    base = RepairRead(**current.model_dump(exclude={"history"}))

    if _has_role(user, Role.admin):
        _, history_item = svc.change_status(repair_id, payload, changed_by=user.user_id)
        return history_item

    if _has_role(user, Role.technician) and base.technician_user_id == user.user_id:
        _, history_item = svc.change_status(repair_id, payload, changed_by=user.user_id)
        return history_item

    raise http_403("Not allowed to change status for this repair")
