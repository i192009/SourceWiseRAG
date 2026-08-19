import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Request

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.security import hash_password, verify_password
from backend.app.core.user_context import get_current_user_context
from backend.app.models.auth import SignupRequest, LoginRequest, AuthUserResponse
from backend.app.storage.sqlite_store import insert_user, get_user_by_username

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("backend.api")


@router.post("/signup", response_model=AuthUserResponse, status_code=status.HTTP_201_CREATED)
def signup(request: Request, payload: SignupRequest):
    user_ctx = get_current_user_context(request)
    start = time.perf_counter()

    name = payload.name.strip()
    username = payload.username.strip().lower()
    password = payload.password

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    insert_user({
        "user_id": user_id,
        "name": name,
        "username": username,
        "password_hash": hash_password(password),
        "created_at": now,
    })

    latency_ms = int((time.perf_counter() - start) * 1000)

    logger.info("user signed up | username=%s", username)

    log_audit_event(
        user_id=user_ctx["user_id"],
        username=user_ctx["username"],
        action_type="user_signed_up",
        status="success",
        request_latency_ms=latency_ms,
        metadata={
            "created_user_id": user_id,
            "created_username": username,
            "created_name": name,
        },
    )

    return AuthUserResponse(
        user_id=user_id,
        name=name,
        username=username,
        created_at=now,
    )


@router.post("/login", response_model=AuthUserResponse)
def login(request: Request, payload: LoginRequest):
    user_ctx = get_current_user_context(request)
    start = time.perf_counter()

    username = payload.username.strip().lower()
    password = payload.password

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        latency_ms = int((time.perf_counter() - start) * 1000)

        log_audit_event(
            user_id=user_ctx["user_id"],
            username=user_ctx["username"],
            action_type="user_logged_in",
            status="failed",
            error_message="Invalid username or password",
            request_latency_ms=latency_ms,
            metadata={"attempted_username": username},
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    latency_ms = int((time.perf_counter() - start) * 1000)

    logger.info("user logged in | username=%s", username)

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="user_logged_in",
        status="success",
        request_latency_ms=latency_ms,
        metadata={"name": user["name"]},
    )

    return AuthUserResponse(
        user_id=user["user_id"],
        name=user["name"],
        username=user["username"],
        created_at=user["created_at"],
    )
