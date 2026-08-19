# Backend

FastAPI backend for:
- document ingestion
- retrieval
- grounded QA
- web fallback
- conversations
- auth
- audit logging

Run:
```bash
export PYTHONPATH=.
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
