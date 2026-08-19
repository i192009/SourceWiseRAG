from fastapi import APIRouter, HTTPException
from backend.app.storage.sqlite_store import get_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def read_job(job_id: str):
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return row
