import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.storage.sqlite_store import (
    list_sources,
    get_source,
    get_chunks_for_source,
    delete_source_tree,
)
from backend.app.storage.vector_store import (
    get_milvus_client,
    delete_chunks_by_source,
)

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger("backend.api")


@router.get("")
def read_sources(
    filename: str | None = None,
    version: int | None = None,
    status: str | None = None,
):
    return {
        "items": list_sources(filename=filename, version=version, status=status)
    }


@router.get("/{source_id}")
def read_source(source_id: str):
    source = get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/{source_id}/chunks")
def read_source_chunks(
    source_id: str,
    limit: int = Query(default=20, ge=1, le=200),
):
    source = get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return {
        "source_id": source_id,
        "items": get_chunks_for_source(source_id, limit=limit),
    }


@router.delete("/{source_id}")
def delete_source(request: Request, source_id: str):
    user = get_current_user_context(request)
    start = time.perf_counter()

    source = get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    client = get_milvus_client()

    vectors_deleted = False
    raw_artifact_deleted = False

    try:
        delete_chunks_by_source(client, source_id)
        vectors_deleted = True

        stored_path = source.get("stored_path")
        if stored_path:
            path_obj = Path(stored_path)
            if path_obj.exists() and path_obj.is_file():
                path_obj.unlink()
                raw_artifact_deleted = True

        delete_source_tree(source_id)

        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "source deleted | user_id=%s | source_id=%s | filename=%s | version=%s",
            user["user_id"],
            source_id,
            source.get("filename"),
            source.get("version"),
        )

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="source_deleted",
            source_id=source_id,
            status="success",
            request_latency_ms=latency_ms,
            metadata={
                "filename": source.get("filename"),
                "version": source.get("version"),
                "vectors_deleted": vectors_deleted,
                "raw_artifact_deleted": raw_artifact_deleted,
                "name": user["name"],
            },
        )

        return {
            "message": "Source deleted successfully",
            "source_id": source_id,
            "filename": source.get("filename"),
            "version": source.get("version"),
            "vectors_deleted": vectors_deleted,
            "raw_artifact_deleted": raw_artifact_deleted,
            "metadata_deleted": True,
        }

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("source delete failed | user_id=%s | source_id=%s", user["user_id"], source_id)

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="source_deleted",
            source_id=source_id,
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
            metadata={
                "filename": source.get("filename"),
                "version": source.get("version"),
                "name": user["name"],
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed deleting source: {e}",
        )
