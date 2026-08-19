import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from backend.app.clients.searxng_client import SearXNGClient
from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.models.web_search import (
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResultItem,
    WebSearchSaveRequest,
    WebSearchSaveResponse,
)
from backend.app.core.settings import WEB_SEARCH_RESULTS_DIR
from backend.app.storage.sqlite_store import (
    insert_web_search_session,
    insert_web_search_result,
    insert_source,
    insert_job,
    get_latest_version_for_filename,
)
from backend.app.utils.checksum import sha256_file

router = APIRouter(prefix="/web-search", tags=["web-search"])
logger = logging.getLogger("backend.web_search")


@router.post("", response_model=WebSearchResponse)
def web_search(request: Request, payload: WebSearchRequest):
    client = SearXNGClient()
    user = get_current_user_context(request)
    start = time.perf_counter()

    try:
        results = client.search(payload.query, payload.limit)
        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "web search run | user_id=%s | query=%s | result_count=%s",
            user["user_id"],
            payload.query,
            len(results),
        )

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="web_search_run",
            question=payload.query,
            status="success",
            request_latency_ms=latency_ms,
            metadata={
                "limit": payload.limit,
                "result_count": len(results),
                "results": results,
                "name": user["name"],
            },
        )

        return WebSearchResponse(
            query=payload.query,
            results=[WebSearchResultItem(**r) for r in results],
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("web search failed | user_id=%s", user["user_id"])

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="web_search_run",
            question=payload.query,
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
            metadata={"limit": payload.limit, "name": user["name"]},
        )
        raise HTTPException(status_code=502, detail=f"Web search failed: {e}")


@router.post("/save", response_model=WebSearchSaveResponse)
def save_web_search(request: Request, payload: WebSearchSaveRequest, background_tasks: BackgroundTasks):
    user = get_current_user_context(request)
    start = time.perf_counter()

    if not payload.selected_results:
        raise HTTPException(status_code=400, detail="selected_results is required")

    now = datetime.utcnow().isoformat()
    session_id = str(uuid.uuid4())

    try:
        insert_web_search_session({
            "session_id": session_id,
            "query": payload.query,
            "created_at": now,
            "status": "created",
        })

        for item in payload.selected_results:
            insert_web_search_result({
                "result_id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source_engine": item.source_engine,
                "is_saved": 1,
                "created_at": now,
            })

        if payload.save_mode == "metadata_only":
            latency_ms = int((time.perf_counter() - start) * 1000)

            logger.info(
                "web search saved metadata only | user_id=%s | session_id=%s | saved_count=%s",
                user["user_id"],
                session_id,
                len(payload.selected_results),
            )

            log_audit_event(
                user_id=user["user_id"],
                username=user["username"],
                action_type="web_search_saved",
                status="success",
                request_latency_ms=latency_ms,
                metadata={
                    "session_id": session_id,
                    "query": payload.query,
                    "save_mode": payload.save_mode,
                    "saved_count": len(payload.selected_results),
                    "selected_results": [item.model_dump() for item in payload.selected_results],
                    "name": user["name"],
                },
            )

            return WebSearchSaveResponse(
                session_id=session_id,
                saved_count=len(payload.selected_results),
                save_mode=payload.save_mode,
                source_id=None,
                job_id=None,
                filename=None,
                version=None,
                message="Search results saved as metadata only",
            )

        synthetic_filename = f"web-search-{session_id}.txt"
        synthetic_path = Path(WEB_SEARCH_RESULTS_DIR) / synthetic_filename

        blocks = [f"Search Query: {payload.query}", ""]

        for idx, item in enumerate(payload.selected_results, start=1):
            blocks.extend([
                f"Result {idx}",
                f"Title: {item.title}",
                f"URL: {item.url}",
                f"Snippet: {item.snippet}",
                "",
            ])

        synthetic_path.write_text("\n".join(blocks), encoding="utf-8")

        source_id = str(uuid.uuid4())
        file_hash = sha256_file(synthetic_path)
        version = get_latest_version_for_filename(synthetic_filename) + 1

        insert_source({
            "source_id": source_id,
            "filename": synthetic_filename,
            "file_hash": file_hash,
            "mime_type": "text/plain",
            "stored_path": str(synthetic_path),
            "size_bytes": synthetic_path.stat().st_size,
            "version": version,
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

        background_tasks.add_task(
            run_ingestion,
            job_id,
            source_id,
            str(synthetic_path),
            synthetic_filename,
            version,
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "web search saved and queued for ingestion | user_id=%s | source_id=%s | job_id=%s",
            user["user_id"],
            source_id,
            job_id,
        )

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="web_search_saved",
            source_id=source_id,
            job_id=job_id,
            status="success",
            request_latency_ms=latency_ms,
            metadata={
                "session_id": session_id,
                "query": payload.query,
                "save_mode": payload.save_mode,
                "saved_count": len(payload.selected_results),
                "filename": synthetic_filename,
                "version": version,
                "selected_results": [item.model_dump() for item in payload.selected_results],
                "name": user["name"],
            },
        )

        return WebSearchSaveResponse(
            session_id=session_id,
            saved_count=len(payload.selected_results),
            save_mode=payload.save_mode,
            source_id=source_id,
            job_id=job_id,
            filename=synthetic_filename,
            version=version,
            message="Search results saved and queued for ingestion",
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("web search save failed | user_id=%s", user["user_id"])

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="web_search_saved",
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
            metadata={
                "query": payload.query,
                "save_mode": payload.save_mode,
                "name": user["name"],
            },
        )
        raise
