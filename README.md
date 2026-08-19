# SourceWiseRAG

This archive is a best-effort reconstruction of the SourceWiseRAG codebase based only on code and decisions shared in this chat.

What is included:
- FastAPI backend
- Streamlit frontend
- SQLite metadata store
- Milvus vector storage integration
- Ollama generation client
- SearXNG web-search fallback
- Persistent conversations, auth, audit logs, and chat file attachments

What may differ from your local copy:
- Some files were reconstructed where the exact final content was not pasted line-for-line in this chat.
- Dependency versions, environment values, and runtime paths may need adjustment for your machine.
- Local data, secrets, models, and uploaded documents are intentionally not included.

See:
- `requirements.txt`
- `.env.example`
- `frontend/README.md`
- `backend/README.md`
