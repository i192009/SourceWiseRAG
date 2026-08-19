import logging
import time
from fastapi import APIRouter, HTTPException, Request

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.models.auth import AuthUserResponse, UsersListResponse
from backend.app.storage.sqlite_store import list_users, get_user_by_id, delete_user

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("backend.api")


@router.get("", response_model=UsersListResponse)
def read_users():
    items = list_users()
    return UsersListResponse(
        items=[AuthUserResponse(**item) for item in items]
    )


@router.delete("/{user_id}")
def remove_user(request: Request, user_id: str):
    actor = get_current_user_context(request)
    start = time.perf_counter()

    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    delete_user(user_id)

    latency_ms = int((time.perf_counter() - start) * 1000)

    logger.info(
        "user deleted | actor_user_id=%s | deleted_user_id=%s | deleted_username=%s",
        actor["user_id"],
        target["user_id"],
        target["username"],
    )

    log_audit_event(
        user_id=actor["user_id"],
        username=actor["username"],
        action_type="user_deleted",
        status="success",
        request_latency_ms=latency_ms,
        metadata={
            "deleted_user_id": target["user_id"],
            "deleted_username": target["username"],
            "deleted_name": target["name"],
        },
    )

    return {
        "message": "User deleted successfully",
        "user_id": target["user_id"],
        "username": target["username"],
        "name": target["name"],
    }
