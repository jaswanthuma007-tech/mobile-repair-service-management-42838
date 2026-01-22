from __future__ import annotations

from typing import Any, Dict, List, Tuple

from supabase import Client  # type: ignore

from src.api.errors import http_400, http_404
from src.schemas.repairs import (
    RepairAssignRequest,
    RepairCreate,
    RepairDetail,
    RepairRead,
    RepairStatusChangeRequest,
    RepairStatusHistoryItem,
    RepairUpdate,
)

VALID_STATUSES = {"requested", "diagnosed", "in_progress", "ready", "completed", "cancelled"}


def _as_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "model_dump"):
        return row.model_dump()
    return dict(row)


def _row_to_repair(row: Any) -> RepairRead:
    return RepairRead(**_as_dict(row))


def _row_to_history(row: Any) -> RepairStatusHistoryItem:
    return RepairStatusHistoryItem(**_as_dict(row))


class RepairService:
    """Service layer for repair workflows backed by Supabase PostgREST."""

    def __init__(self, sb: Client):
        self._sb = sb

    def _get_repair_row(self, repair_id: str) -> Dict[str, Any]:
        res = self._sb.table("repairs").select("*").eq("id", repair_id).limit(1).execute()
        data = getattr(res, "data", None)
        if not data:
            raise http_404("Repair not found")
        return _as_dict(data[0])

    # PUBLIC_INTERFACE
    def create_repair(self, customer_user_id: str, payload: RepairCreate) -> RepairRead:
        """Create a new repair owned by the given customer."""
        row = {
            "customer_user_id": customer_user_id,
            "device_type": payload.device_type,
            "issue_description": payload.issue_description,
            "preferred_contact": payload.preferred_contact,
            "status": "requested",
        }
        res = self._sb.table("repairs").insert(row).select("*").limit(1).execute()
        data = getattr(res, "data", None)
        if not data:
            raise http_400("Unable to create repair")
        repair = _row_to_repair(data[0])

        # create initial history row (optional but useful for UI)
        self._sb.table("repair_status_history").insert(
            {
                "repair_id": repair.id,
                "from_status": None,
                "to_status": repair.status,
                "note": "Created",
                "changed_by": customer_user_id,
            }
        ).execute()

        return repair

    # PUBLIC_INTERFACE
    def list_repairs_for_customer(self, customer_user_id: str) -> List[RepairRead]:
        """List repairs owned by the customer."""
        res = (
            self._sb.table("repairs")
            .select("*")
            .eq("customer_user_id", customer_user_id)
            .order("created_at", desc=True)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return [_row_to_repair(r) for r in data]

    # PUBLIC_INTERFACE
    def list_repairs_for_technician(self, technician_user_id: str) -> List[RepairRead]:
        """List repairs assigned to technician."""
        res = (
            self._sb.table("repairs")
            .select("*")
            .eq("technician_user_id", technician_user_id)
            .order("created_at", desc=True)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return [_row_to_repair(r) for r in data]

    # PUBLIC_INTERFACE
    def list_repairs_for_admin(self) -> List[RepairRead]:
        """List all repairs (admin)."""
        res = self._sb.table("repairs").select("*").order("created_at", desc=True).execute()
        data = getattr(res, "data", None) or []
        return [_row_to_repair(r) for r in data]

    # PUBLIC_INTERFACE
    def get_repair_detail(self, repair_id: str) -> RepairDetail:
        """Get repair detail with history."""
        repair_row = self._get_repair_row(repair_id)
        history_res = (
            self._sb.table("repair_status_history")
            .select("*")
            .eq("repair_id", repair_id)
            .order("created_at", desc=True)
            .execute()
        )
        history_data = getattr(history_res, "data", None) or []
        return RepairDetail(**repair_row, history=[_row_to_history(x) for x in history_data])

    def _update_repair(self, repair_id: str, patch: Dict[str, Any]) -> RepairRead:
        res = self._sb.table("repairs").update(patch).eq("id", repair_id).select("*").limit(1).execute()
        data = getattr(res, "data", None)
        if not data:
            raise http_400("Unable to update repair")
        return _row_to_repair(data[0])

    # PUBLIC_INTERFACE
    def patch_repair(self, repair_id: str, payload: RepairUpdate) -> RepairRead:
        """Update basic repair fields (not status/assignment)."""
        patch: Dict[str, Any] = {}
        if payload.device_type is not None:
            patch["device_type"] = payload.device_type
        if payload.issue_description is not None:
            patch["issue_description"] = payload.issue_description
        if payload.preferred_contact is not None:
            patch["preferred_contact"] = payload.preferred_contact
        if not patch:
            # no-op
            row = self._get_repair_row(repair_id)
            return RepairRead(**row)
        return self._update_repair(repair_id, patch)

    # PUBLIC_INTERFACE
    def assign_technician(
        self, repair_id: str, req: RepairAssignRequest, changed_by: str
    ) -> RepairRead:
        """Assign technician to repair (admin)."""
        # ensure exists
        repair = self._get_repair_row(repair_id)
        patch = {"technician_user_id": req.technician_user_id}
        updated = self._update_repair(repair_id, patch)

        # record history entry
        self._sb.table("repair_status_history").insert(
            {
                "repair_id": repair_id,
                "from_status": repair.get("status"),
                "to_status": updated.status,
                "note": f"Assigned technician: {req.technician_user_id}",
                "changed_by": changed_by,
            }
        ).execute()
        return updated

    def _validate_status(self, status_value: str) -> None:
        if status_value not in VALID_STATUSES:
            raise http_400(f"Invalid status '{status_value}'. Allowed: {sorted(VALID_STATUSES)}")

    # PUBLIC_INTERFACE
    def change_status(
        self, repair_id: str, req: RepairStatusChangeRequest, changed_by: str
    ) -> Tuple[RepairRead, RepairStatusHistoryItem]:
        """Transition repair status and append history row."""
        self._validate_status(req.new_status)

        current = self._get_repair_row(repair_id)
        from_status = current.get("status")
        if isinstance(from_status, str) and from_status == req.new_status:
            raise http_409("Status is already set to requested value")  # type: ignore[name-defined]

        updated = self._update_repair(repair_id, {"status": req.new_status})

        hist_res = (
            self._sb.table("repair_status_history")
            .insert(
                {
                    "repair_id": repair_id,
                    "from_status": from_status if isinstance(from_status, str) else None,
                    "to_status": req.new_status,
                    "note": req.note,
                    "changed_by": changed_by,
                }
            )
            .select("*")
            .limit(1)
            .execute()
        )
        hist_data = getattr(hist_res, "data", None)
        if not hist_data:
            # history insert may not return representation; fetch last
            hist_fetch = (
                self._sb.table("repair_status_history")
                .select("*")
                .eq("repair_id", repair_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            hist_data = getattr(hist_fetch, "data", None) or []
        history_item = _row_to_history(hist_data[0])
        return updated, history_item


# local import fix: http_409 used above
from src.api.errors import http_409  # noqa: E402
