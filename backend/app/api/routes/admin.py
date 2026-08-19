from fastapi import APIRouter, Query

from backend.app.storage.sqlite_store import list_audit_logs, get_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
def read_audit_logs(
    user_id: str | None = None,
    action_type: str | None = None,
    status: str | None = None,
    answer_source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    items = list_audit_logs(
        user_id=user_id,
        action_type=action_type,
        status=status,
        answer_source=answer_source,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return {"items": items, "count": len(items)}


@router.get("/audit-logs/{audit_log_id}")
def read_audit_log_detail(audit_log_id: str):
    item = get_audit_log(audit_log_id)
    if not item:
        return {"detail": "Audit log not found"}
    return item
