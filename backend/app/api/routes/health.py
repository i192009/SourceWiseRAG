import httpx
from fastapi import APIRouter

from backend.app.core.settings import OLLAMA_BASE_URL, OLLAMA_MODEL

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health():
    return {"status": "ok"}


@router.get("/ollama")
def health_ollama():
    with httpx.Client(timeout=10.0) as client:
        version_resp = client.get(f"{OLLAMA_BASE_URL}/api/version")
        version_resp.raise_for_status()

        tags_resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
        tags_resp.raise_for_status()

    return {
        "status": "ok",
        "ollama_base_url": OLLAMA_BASE_URL,
        "configured_model": OLLAMA_MODEL,
        "version": version_resp.json(),
        "models": tags_resp.json(),
    }
