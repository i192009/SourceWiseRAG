import json
import uuid
from datetime import datetime
from typing import Any

from backend.app.storage.sqlite_store import insert_audit_log


def _to_json(value: Any):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def log_audit_event(
    *,
    user_id: str,
    username: str,
    action_type: str,
    source_id: str | None = None,
    job_id: str | None = None,
    question: str | None = None,
    answer: str | None = None,
    answer_source: str | None = None,
    citations: list | None = None,
    retrieved_chunk_ids: list | None = None,
    filters: dict | None = None,
    metadata: dict | None = None,
    status: str = "success",
    error_message: str | None = None,
    request_latency_ms: int | None = None,
):
    insert_audit_log({
        "audit_log_id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": username,
        "action_type": action_type,
        "source_id": source_id,
        "job_id": job_id,
        "question": question,
        "answer": answer,
        "answer_source": answer_source,
        "citations_json": _to_json(citations),
        "retrieved_chunk_ids_json": _to_json(retrieved_chunk_ids),
        "filters_json": _to_json(filters),
        "metadata_json": _to_json(metadata),
        "status": status,
        "error_message": error_message,
        "request_latency_ms": request_latency_ms,
        "created_at": datetime.utcnow().isoformat(),
    })
