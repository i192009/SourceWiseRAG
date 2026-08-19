import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.models.conversation import (
    ConversationCreateRequest,
    ConversationSummary,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationMessageItem,
    ConversationMessagesResponse,
    ConversationActionResponse,
)
from backend.app.storage.sqlite_store import (
    insert_conversation,
    get_conversation,
    list_conversations,
    list_conversation_messages,
    restart_conversation,
    delete_conversation,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = logging.getLogger("backend.api")


def _default_title(title: str | None = None) -> str:
    clean = (title or "").strip()
    return clean or "New Chat"


@router.post("", response_model=ConversationSummary)
def create_conversation(request: Request, payload: ConversationCreateRequest):
    user = get_current_user_context(request)
    now = datetime.utcnow().isoformat()
    conversation_id = str(uuid.uuid4())

    record = {
        "conversation_id": conversation_id,
        "user_id": user["user_id"],
        "title": _default_title(payload.title),
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "message_count": 0,
    }
    insert_conversation(record)

    logger.info("conversation created | user_id=%s | conversation_id=%s", user["user_id"], conversation_id)

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="conversation_created",
        status="success",
        metadata={
            "conversation_id": conversation_id,
            "title": record["title"],
            "name": user.get("name"),
        },
    )

    return ConversationSummary(
        conversation_id=record["conversation_id"],
        user_id=record["user_id"],
        title=record["title"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        last_message_at=record["last_message_at"],
        message_count=record["message_count"],
        last_message=None,
    )


@router.get("", response_model=ConversationListResponse)
def read_conversations(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    user = get_current_user_context(request)
    items = list_conversations(user_id=user["user_id"], limit=limit, offset=offset)

    return ConversationListResponse(
        items=[ConversationSummary(**item) for item in items],
        count=len(items),
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def read_conversation(request: Request, conversation_id: str):
    user = get_current_user_context(request)
    convo = get_conversation(conversation_id, user_id=user["user_id"])
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(**convo)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def read_conversation_messages(
    request: Request,
    conversation_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    user = get_current_user_context(request)
    convo = get_conversation(conversation_id, user_id=user["user_id"])
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    items = list_conversation_messages(conversation_id=conversation_id, limit=limit, offset=offset)

    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        items=[ConversationMessageItem(**item) for item in items],
        count=len(items),
        limit=limit,
        offset=offset,
    )


@router.post("/{conversation_id}/restart", response_model=ConversationActionResponse)
def restart_current_conversation(request: Request, conversation_id: str):
    user = get_current_user_context(request)
    convo = restart_conversation(conversation_id, user_id=user["user_id"], reset_title="New Chat")
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info("conversation restarted | user_id=%s | conversation_id=%s", user["user_id"], conversation_id)

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="conversation_restarted",
        status="success",
        metadata={
            "conversation_id": conversation_id,
            "name": user.get("name"),
        },
    )

    return ConversationActionResponse(
        conversation_id=conversation_id,
        title=convo["title"],
        message="Conversation restarted successfully",
    )


@router.delete("/{conversation_id}", response_model=ConversationActionResponse)
def remove_conversation(request: Request, conversation_id: str):
    user = get_current_user_context(request)
    deleted = delete_conversation(conversation_id, user_id=user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info("conversation deleted | user_id=%s | conversation_id=%s", user["user_id"], conversation_id)

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="conversation_deleted",
        status="success",
        metadata={
            "conversation_id": conversation_id,
            "title": deleted["title"],
            "name": user.get("name"),
        },
    )

    return ConversationActionResponse(
        conversation_id=conversation_id,
        title=deleted["title"],
        message="Conversation deleted successfully",
    )
