import os

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")

ALLOWED_UPLOAD_TYPES = ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "txt"]

DEFAULT_TOP_K = 3

SESSION_DEFAULTS = {
    "is_authenticated": False,
    "current_user_id": None,
    "current_username": None,
    "current_name": None,
    "selected_source_id": None,
    "selected_filename": None,
    "selected_version": None,
    "last_job_id": None,
    "last_upload_response": None,
    "last_chat_response": None,
    "last_web_search_response": None,
    "last_web_search_save_response": None,
    "last_chat_web_save_response": None,
    "admin_health_response": None,
    "admin_audit_logs_response": None,
    "active_conversation_id": None,
    "active_conversation_title": None,
    "chat_conversations": None,
}
