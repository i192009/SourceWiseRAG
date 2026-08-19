import logging
import time
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from starlette.concurrency import run_in_threadpool

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatWithFilesResponse,
    CitationItem,
    ChatFallbackRequest,
    ChatFallbackResponse,
    ChatFallbackWithFilesResponse,
    ChatAttachmentItem,
)
from backend.app.models.web_search import WebSearchResultItem
from backend.app.services.qa_service import QAService
from backend.app.services.chat_fallback_service import ChatFallbackService
from backend.app.storage.file_store import save_upload_file
from backend.app.storage.sqlite_store import (
    get_conversation,
    insert_conversation,
    insert_conversation_message,
    update_conversation_title,
    insert_source,
    insert_job,
    get_latest_version_for_filename,
    get_source,
    get_job,
)
from backend.app.utils.checksum import sha256_file

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("backend.chat")

ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "text/plain",
}


def _generate_title_from_question(question: str, max_len: int = 60) -> str:
    clean = " ".join((question or "").strip().split())
    if not clean:
        return "New Chat"
    if len(clean) <= max_len:
        return clean
    return clean[:max_len].rstrip() + "..."


def _ensure_conversation(request: Request, conversation_id: str | None, first_question: str) -> str:
    user = get_current_user_context(request)

    if conversation_id:
        convo = get_conversation(conversation_id, user_id=user["user_id"])
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if int(convo.get("message_count", 0)) == 0:
            update_conversation_title(conversation_id, _generate_title_from_question(first_question))

        return conversation_id

    now = datetime.utcnow().isoformat()
    new_conversation_id = str(uuid.uuid4())
    title = _generate_title_from_question(first_question)

    insert_conversation({
        "conversation_id": new_conversation_id,
        "user_id": user["user_id"],
        "title": title,
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "message_count": 0,
    })

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="conversation_created",
        status="success",
        metadata={
            "conversation_id": new_conversation_id,
            "title": title,
            "name": user.get("name"),
            "created_via": "chat",
        },
    )

    return new_conversation_id


def _store_user_message(conversation_id: str, question: str, filters: dict, attachments: list | None = None):
    insert_conversation_message({
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "user",
        "content": question,
        "metadata": {
            "filters": filters,
            "attachments": attachments or [],
        },
        "created_at": datetime.utcnow().isoformat(),
    })


def _store_assistant_message(
    conversation_id: str,
    answer: str,
    answer_source: str,
    citations: list,
    retrieved_chunk_ids: list,
    web_results: list | None = None,
):
    insert_conversation_message({
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": answer,
        "metadata": {
            "answer_source": answer_source,
            "citations": citations,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "web_results": web_results or [],
        },
        "created_at": datetime.utcnow().isoformat(),
    })


async def _store_chat_attachments_and_ingest(files: list[UploadFile] | None):
    if not files:
        return []

    stored_items = []

    for upload in files:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Attachment filename is required")

        if upload.content_type and upload.content_type not in ALLOWED_ATTACHMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment content type: {upload.content_type}",
            )

        source_id, file_path, size_bytes = await save_upload_file(upload)
        file_hash = sha256_file(file_path)
        final_filename = upload.filename
        next_version = get_latest_version_for_filename(final_filename) + 1
        now = datetime.utcnow().isoformat()

        insert_source({
            "source_id": source_id,
            "filename": final_filename,
            "file_hash": file_hash,
            "mime_type": upload.content_type,
            "stored_path": file_path,
            "size_bytes": size_bytes,
            "version": next_version,
            "status": "uploaded",
            "created_at": now,
        })

        job_id = str(uuid.uuid4())
        insert_job({
            "job_id": job_id,
            "source_id": source_id,
            "stage": "ingestion",
            "status": "queued",
            "error_message": None,
            "created_at": now,
        })

        from backend.app.workers.ingestion import run_ingestion

        await run_in_threadpool(
            run_ingestion,
            job_id,
            source_id,
            file_path,
            final_filename,
            next_version,
        )

        source_row = get_source(source_id)
        job_row = get_job(job_id)

        source_status = source_row.get("status") if source_row else None
        job_status = job_row.get("status") if job_row else None
        job_error = job_row.get("error_message") if job_row else None

        if source_status != "ready" or job_status != "completed":
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Attachment ingestion failed for '{final_filename}'. "
                    f"source_status={source_status}, job_status={job_status}, error={job_error}"
                ),
            )

        stored_items.append({
            "source_id": source_id,
            "filename": final_filename,
            "content_type": upload.content_type,
            "size_bytes": size_bytes,
            "job_id": job_id,
            "version": next_version,
            "status": "ready",
        })

    return stored_items


@router.post("", response_model=ChatResponse)
def chat(request: Request, payload: ChatRequest):
    service = QAService()
    user = get_current_user_context(request)

    filters = {
        "source_id": payload.source_id,
        "filename": payload.filename,
        "version": payload.version,
        "sheet_name": payload.sheet_name,
        "page_no": payload.page_no,
        "top_k": payload.top_k,
    }

    start = time.perf_counter()
    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="chat_asked",
        question=payload.question,
        filters=filters,
        status="success",
    )

    conversation_id = _ensure_conversation(request, payload.conversation_id, payload.question)
    _store_user_message(conversation_id, payload.question, filters)

    try:
        result = service.answer_question(
            question=payload.question,
            top_k=payload.top_k,
            source_id=payload.source_id,
            filename=payload.filename,
            version=payload.version,
            sheet_name=payload.sheet_name,
            page_no=payload.page_no,
        )

        _store_assistant_message(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source="internal",
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "chat answered | user_id=%s | conversation_id=%s | filename=%s | version=%s | latency_ms=%s",
            user["user_id"],
            conversation_id,
            payload.filename,
            payload.version,
            latency_ms,
        )

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            source_id=payload.source_id,
            question=payload.question,
            answer=result["answer"],
            answer_source="internal",
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            filters={**filters, "conversation_id": conversation_id},
            status="success",
            request_latency_ms=latency_ms,
        )

        citations = [CitationItem(**item) for item in result["citations"]]

        return ChatResponse(
            conversation_id=conversation_id,
            answer=result["answer"],
            citations=citations,
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("chat failed | user_id=%s | conversation_id=%s", user["user_id"], conversation_id)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            question=payload.question,
            filters={**filters, "conversation_id": conversation_id},
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
        )
        raise


@router.post("/with-files", response_model=ChatWithFilesResponse)
async def chat_with_files(
    request: Request,
    question: Annotated[str, Form()],
    top_k: Annotated[int, Form()] = 5,
    source_id: Annotated[str | None, Form()] = None,
    filename: Annotated[str | None, Form()] = None,
    version: Annotated[int | None, Form()] = None,
    sheet_name: Annotated[str | None, Form()] = None,
    page_no: Annotated[int | None, Form()] = None,
    conversation_id: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    service = QAService()
    user = get_current_user_context(request)

    filters = {
        "source_id": source_id,
        "filename": filename,
        "version": version,
        "sheet_name": sheet_name,
        "page_no": page_no,
        "top_k": top_k,
    }

    start = time.perf_counter()
    attached_files = await _store_chat_attachments_and_ingest(files=files)

    if attached_files:
        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_files_attached",
            status="success",
            metadata={
                "conversation_id": conversation_id,
                "question": question,
                "attached_files": attached_files,
                "ingestion_mode": "synchronous",
            },
        )

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="chat_asked",
        question=question,
        filters={**filters, "attached_file_count": len(attached_files)},
        status="success",
    )

    conversation_id = _ensure_conversation(request, conversation_id, question)
    _store_user_message(conversation_id, question, filters, attachments=attached_files)

    try:
        result = service.answer_question(
            question=question,
            top_k=top_k,
            source_id=source_id,
            filename=filename,
            version=version,
            sheet_name=sheet_name,
            page_no=page_no,
        )

        _store_assistant_message(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source="internal",
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            source_id=source_id,
            question=question,
            answer=result["answer"],
            answer_source="internal",
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            filters={**filters, "conversation_id": conversation_id},
            metadata={"attached_files": attached_files},
            status="success",
            request_latency_ms=latency_ms,
        )

        return ChatWithFilesResponse(
            conversation_id=conversation_id,
            answer=result["answer"],
            citations=[CitationItem(**item) for item in result["citations"]],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            attached_files=[ChatAttachmentItem(**item) for item in attached_files],
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            question=question,
            filters={**filters, "conversation_id": conversation_id},
            metadata={"attached_files": attached_files},
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
        )
        raise


@router.post("/fallback", response_model=ChatFallbackResponse)
def chat_fallback(request: Request, payload: ChatFallbackRequest):
    service = ChatFallbackService()
    user = get_current_user_context(request)

    filters = {
        "source_id": payload.source_id,
        "filename": payload.filename,
        "version": payload.version,
        "sheet_name": payload.sheet_name,
        "page_no": payload.page_no,
        "top_k": payload.top_k,
        "allow_web_fallback": payload.allow_web_fallback,
        "web_result_limit": payload.web_result_limit,
    }

    start = time.perf_counter()
    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="chat_asked",
        question=payload.question,
        filters=filters,
        status="success",
    )

    conversation_id = _ensure_conversation(request, payload.conversation_id, payload.question)
    _store_user_message(conversation_id, payload.question, filters)

    try:
        result = service.answer_question(
            question=payload.question,
            top_k=payload.top_k,
            source_id=payload.source_id,
            filename=payload.filename,
            version=payload.version,
            sheet_name=payload.sheet_name,
            page_no=payload.page_no,
            allow_web_fallback=payload.allow_web_fallback,
            web_result_limit=payload.web_result_limit,
        )

        _store_assistant_message(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source=result["answer_source"],
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            web_results=result["web_results"],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "chat fallback answered | user_id=%s | conversation_id=%s | answer_source=%s | used_web_fallback=%s | latency_ms=%s",
            user["user_id"],
            conversation_id,
            result["answer_source"],
            result["used_web_fallback"],
            latency_ms,
        )

        action_type = "chat_fallback_used" if result["used_web_fallback"] else "chat_answered"

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type=action_type,
            source_id=payload.source_id,
            question=payload.question,
            answer=result["answer"],
            answer_source=result["answer_source"],
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            filters={**filters, "conversation_id": conversation_id},
            metadata={"web_results": result["web_results"]},
            status="success",
            request_latency_ms=latency_ms,
        )

        citations = [CitationItem(**item) for item in result["citations"]]
        web_results = [WebSearchResultItem(**item) for item in result["web_results"]]

        return ChatFallbackResponse(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source=result["answer_source"],
            used_web_fallback=result["used_web_fallback"],
            citations=citations,
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            web_results=web_results,
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("chat fallback failed | user_id=%s | conversation_id=%s", user["user_id"], conversation_id)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            question=payload.question,
            filters={**filters, "conversation_id": conversation_id},
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
        )
        raise


@router.post("/fallback-with-files", response_model=ChatFallbackWithFilesResponse)
async def chat_fallback_with_files(
    request: Request,
    question: Annotated[str, Form()],
    top_k: Annotated[int, Form()] = 5,
    source_id: Annotated[str | None, Form()] = None,
    filename: Annotated[str | None, Form()] = None,
    version: Annotated[int | None, Form()] = None,
    sheet_name: Annotated[str | None, Form()] = None,
    page_no: Annotated[int | None, Form()] = None,
    conversation_id: Annotated[str | None, Form()] = None,
    allow_web_fallback: Annotated[bool, Form()] = True,
    web_result_limit: Annotated[int, Form()] = 5,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    service = ChatFallbackService()
    user = get_current_user_context(request)

    filters = {
        "source_id": source_id,
        "filename": filename,
        "version": version,
        "sheet_name": sheet_name,
        "page_no": page_no,
        "top_k": top_k,
        "allow_web_fallback": allow_web_fallback,
        "web_result_limit": web_result_limit,
    }

    start = time.perf_counter()

    attached_files = await _store_chat_attachments_and_ingest(files=files)

    if attached_files:
        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_files_attached",
            status="success",
            metadata={
                "conversation_id": conversation_id,
                "question": question,
                "attached_files": attached_files,
                "ingestion_mode": "synchronous",
            },
        )

    log_audit_event(
        user_id=user["user_id"],
        username=user["username"],
        action_type="chat_asked",
        question=question,
        filters={**filters, "attached_file_count": len(attached_files)},
        status="success",
    )

    conversation_id = _ensure_conversation(request, conversation_id, question)
    _store_user_message(conversation_id, question, filters, attachments=attached_files)

    try:
        result = service.answer_question(
            question=question,
            top_k=top_k,
            source_id=source_id,
            filename=filename,
            version=version,
            sheet_name=sheet_name,
            page_no=page_no,
            allow_web_fallback=allow_web_fallback,
            web_result_limit=web_result_limit,
        )

        _store_assistant_message(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source=result["answer_source"],
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            web_results=result["web_results"],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        action_type = "chat_fallback_used" if result["used_web_fallback"] else "chat_answered"

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type=action_type,
            source_id=source_id,
            question=question,
            answer=result["answer"],
            answer_source=result["answer_source"],
            citations=result["citations"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            filters={**filters, "conversation_id": conversation_id},
            metadata={
                "web_results": result["web_results"],
                "attached_files": attached_files,
            },
            status="success",
            request_latency_ms=latency_ms,
        )

        return ChatFallbackWithFilesResponse(
            conversation_id=conversation_id,
            answer=result["answer"],
            answer_source=result["answer_source"],
            used_web_fallback=result["used_web_fallback"],
            citations=[CitationItem(**item) for item in result["citations"]],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            web_results=[WebSearchResultItem(**item) for item in result["web_results"]],
            attached_files=[ChatAttachmentItem(**item) for item in attached_files],
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="chat_answered",
            question=question,
            filters={**filters, "conversation_id": conversation_id},
            metadata={"attached_files": attached_files},
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
        )
        raise
