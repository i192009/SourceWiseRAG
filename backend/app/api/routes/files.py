import logging
import time
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status, Request

from backend.app.core.audit_logger import log_audit_event
from backend.app.core.user_context import get_current_user_context
from backend.app.models.api import FileUploadResponse
from backend.app.storage.file_store import save_upload_file
from backend.app.storage.sqlite_store import (
    insert_job,
    insert_source,
    get_latest_version_for_filename,
)
from backend.app.utils.checksum import sha256_file

router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger("backend.api")

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "text/plain",
}


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(description="Document to ingest")],
    source_name: Annotated[str | None, Form()] = None,
):
    user = get_current_user_context(request)
    start = time.perf_counter()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}")

    try:
        source_id, file_path, size_bytes = await save_upload_file(file)
        file_hash = sha256_file(file_path)

        final_filename = source_name or file.filename
        next_version = get_latest_version_for_filename(final_filename) + 1
        now = datetime.utcnow().isoformat()

        source_record = {
            "source_id": source_id,
            "filename": final_filename,
            "file_hash": file_hash,
            "mime_type": file.content_type,
            "stored_path": file_path,
            "size_bytes": size_bytes,
            "version": next_version,
            "status": "uploaded",
            "created_at": now,
        }
        insert_source(source_record)

        job_id = str(uuid.uuid4())
        job_record = {
            "job_id": job_id,
            "source_id": source_id,
            "stage": "ingestion",
            "status": "queued",
            "error_message": None,
            "created_at": now,
        }
        insert_job(job_record)

        from backend.app.workers.ingestion import run_ingestion

        background_tasks.add_task(
            run_ingestion,
            job_id,
            source_id,
            file_path,
            source_record["filename"],
            source_record["version"],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "file uploaded | user_id=%s | source_id=%s | filename=%s | version=%s | job_id=%s",
            user["user_id"],
            source_id,
            final_filename,
            next_version,
            job_id,
        )

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="file_uploaded",
            source_id=source_id,
            job_id=job_id,
            status="success",
            request_latency_ms=latency_ms,
            metadata={
                "filename": final_filename,
                "mime_type": file.content_type,
                "size_bytes": size_bytes,
                "version": next_version,
                "name": user["name"],
            },
        )

        return FileUploadResponse(
            source_id=source_id,
            filename=source_record["filename"],
            content_type=file.content_type,
            size_bytes=size_bytes,
            status="accepted",
            message="File uploaded and ingestion queued",
            job_id=job_id,
            version=source_record["version"],
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("file upload failed | user_id=%s", user["user_id"])

        log_audit_event(
            user_id=user["user_id"],
            username=user["username"],
            action_type="file_uploaded",
            status="failed",
            error_message=str(e),
            request_latency_ms=latency_ms,
            metadata={
                "filename": source_name or file.filename,
                "mime_type": file.content_type,
                "name": user["name"],
            },
        )
        raise
