import requests
from utils.config import BACKEND_BASE_URL


def _build_headers(user_context: dict | None = None) -> dict:
    headers = {}

    if user_context:
        if user_context.get("user_id"):
            headers["X-User-Id"] = user_context["user_id"]
        if user_context.get("username"):
            headers["X-Username"] = user_context["username"]
        if user_context.get("name"):
            headers["X-Name"] = user_context["name"]

    return headers


def signup_user(name: str, username: str, password: str):
    response = requests.post(
        f"{BACKEND_BASE_URL}/auth/signup",
        json={"name": name, "username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def login_user(username: str, password: str):
    response = requests.post(
        f"{BACKEND_BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_users_api(user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/users", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def delete_user_api(user_id: str, user_context: dict | None = None):
    response = requests.delete(f"{BACKEND_BASE_URL}/users/{user_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def create_conversation_api(title: str | None = None, user_context: dict | None = None):
    payload = {}
    if title:
        payload["title"] = title
    response = requests.post(f"{BACKEND_BASE_URL}/conversations", json=payload, headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def list_conversations_api(limit: int = 100, offset: int = 0, user_context: dict | None = None):
    response = requests.get(
        f"{BACKEND_BASE_URL}/conversations",
        params={"limit": limit, "offset": offset},
        headers=_build_headers(user_context),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_conversation_api(conversation_id: str, user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/conversations/{conversation_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def get_conversation_messages_api(conversation_id: str, limit: int = 200, offset: int = 0, user_context: dict | None = None):
    response = requests.get(
        f"{BACKEND_BASE_URL}/conversations/{conversation_id}/messages",
        params={"limit": limit, "offset": offset},
        headers=_build_headers(user_context),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def restart_conversation_api(conversation_id: str, user_context: dict | None = None):
    response = requests.post(f"{BACKEND_BASE_URL}/conversations/{conversation_id}/restart", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def delete_conversation_api(conversation_id: str, user_context: dict | None = None):
    response = requests.delete(f"{BACKEND_BASE_URL}/conversations/{conversation_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def get_health(user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/health", headers=_build_headers(user_context), timeout=10)
    response.raise_for_status()
    return response.json()


def get_job_status(job_id: str, user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/jobs/{job_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def upload_file_to_backend(file_name: str, file_bytes: bytes, mime_type: str | None, source_name: str | None, user_context: dict | None = None):
    files = {"file": (file_name, file_bytes, mime_type or "application/octet-stream")}
    data = {}
    if source_name:
        data["source_name"] = source_name
    response = requests.post(
        f"{BACKEND_BASE_URL}/files/upload",
        files=files,
        data=data,
        headers=_build_headers(user_context),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def list_sources(filename: str | None = None, version: int | None = None, status: str | None = None, user_context: dict | None = None):
    params = {}
    if filename:
        params["filename"] = filename
    if version is not None:
        params["version"] = version
    if status:
        params["status"] = status
    response = requests.get(f"{BACKEND_BASE_URL}/sources", params=params, headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def get_source(source_id: str, user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/sources/{source_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def get_source_chunks(source_id: str, limit: int = 20, user_context: dict | None = None):
    response = requests.get(
        f"{BACKEND_BASE_URL}/sources/{source_id}/chunks",
        params={"limit": limit},
        headers=_build_headers(user_context),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def delete_source(source_id: str, user_context: dict | None = None):
    response = requests.delete(f"{BACKEND_BASE_URL}/sources/{source_id}", headers=_build_headers(user_context), timeout=60)
    response.raise_for_status()
    return response.json()


def ask_chat(question: str, top_k: int = 3, source_id: str | None = None, filename: str | None = None, version: int | None = None, sheet_name: str | None = None, page_no: int | None = None, conversation_id: str | None = None, user_context: dict | None = None):
    payload = {"question": question, "top_k": top_k}
    if source_id:
        payload["source_id"] = source_id
    if filename:
        payload["filename"] = filename
    if version is not None:
        payload["version"] = version
    if sheet_name:
        payload["sheet_name"] = sheet_name
    if page_no is not None:
        payload["page_no"] = page_no
    if conversation_id:
        payload["conversation_id"] = conversation_id
    response = requests.post(f"{BACKEND_BASE_URL}/chat", json=payload, headers=_build_headers(user_context), timeout=180)
    response.raise_for_status()
    return response.json()


def ask_chat_fallback(question: str, top_k: int = 3, source_id: str | None = None, filename: str | None = None, version: int | None = None, sheet_name: str | None = None, page_no: int | None = None, conversation_id: str | None = None, allow_web_fallback: bool = True, web_result_limit: int = 5, user_context: dict | None = None):
    payload = {"question": question, "top_k": top_k, "allow_web_fallback": allow_web_fallback, "web_result_limit": web_result_limit}
    if source_id:
        payload["source_id"] = source_id
    if filename:
        payload["filename"] = filename
    if version is not None:
        payload["version"] = version
    if sheet_name:
        payload["sheet_name"] = sheet_name
    if page_no is not None:
        payload["page_no"] = page_no
    if conversation_id:
        payload["conversation_id"] = conversation_id
    response = requests.post(f"{BACKEND_BASE_URL}/chat/fallback", json=payload, headers=_build_headers(user_context), timeout=240)
    response.raise_for_status()
    return response.json()


def _build_chat_multipart_data(*, question: str, top_k: int, source_id: str | None = None, filename: str | None = None, version: int | None = None, sheet_name: str | None = None, page_no: int | None = None, conversation_id: str | None = None, allow_web_fallback: bool | None = None, web_result_limit: int | None = None):
    data = {"question": question, "top_k": str(top_k)}
    if source_id:
        data["source_id"] = source_id
    if filename:
        data["filename"] = filename
    if version is not None:
        data["version"] = str(version)
    if sheet_name:
        data["sheet_name"] = sheet_name
    if page_no is not None:
        data["page_no"] = str(page_no)
    if conversation_id:
        data["conversation_id"] = conversation_id
    if allow_web_fallback is not None:
        data["allow_web_fallback"] = "true" if allow_web_fallback else "false"
    if web_result_limit is not None:
        data["web_result_limit"] = str(web_result_limit)
    return data


def _build_multipart_files(file_items: list[dict]):
    multipart_files = []
    for item in file_items:
        multipart_files.append(("files", (item["name"], item["bytes"], item.get("mime_type") or "application/octet-stream")))
    return multipart_files


def ask_chat_with_files(*, question: str, top_k: int = 3, file_items: list[dict], source_id: str | None = None, filename: str | None = None, version: int | None = None, sheet_name: str | None = None, page_no: int | None = None, conversation_id: str | None = None, user_context: dict | None = None):
    response = requests.post(
        f"{BACKEND_BASE_URL}/chat/with-files",
        data=_build_chat_multipart_data(question=question, top_k=top_k, source_id=source_id, filename=filename, version=version, sheet_name=sheet_name, page_no=page_no, conversation_id=conversation_id),
        files=_build_multipart_files(file_items),
        headers=_build_headers(user_context),
        timeout=900,
    )
    response.raise_for_status()
    return response.json()


def ask_chat_fallback_with_files(*, question: str, top_k: int = 3, file_items: list[dict], source_id: str | None = None, filename: str | None = None, version: int | None = None, sheet_name: str | None = None, page_no: int | None = None, conversation_id: str | None = None, allow_web_fallback: bool = True, web_result_limit: int = 5, user_context: dict | None = None):
    response = requests.post(
        f"{BACKEND_BASE_URL}/chat/fallback-with-files",
        data=_build_chat_multipart_data(question=question, top_k=top_k, source_id=source_id, filename=filename, version=version, sheet_name=sheet_name, page_no=page_no, conversation_id=conversation_id, allow_web_fallback=allow_web_fallback, web_result_limit=web_result_limit),
        files=_build_multipart_files(file_items),
        headers=_build_headers(user_context),
        timeout=1200,
    )
    response.raise_for_status()
    return response.json()


def web_search(query: str, limit: int = 5, user_context: dict | None = None):
    payload = {"query": query, "limit": limit}
    response = requests.post(f"{BACKEND_BASE_URL}/web-search", json=payload, headers=_build_headers(user_context), timeout=60)
    response.raise_for_status()
    return response.json()


def save_web_search_results(query: str, selected_results: list[dict], save_mode: str = "ingest", user_context: dict | None = None):
    payload = {"query": query, "selected_results": selected_results, "save_mode": save_mode}
    response = requests.post(f"{BACKEND_BASE_URL}/web-search/save", json=payload, headers=_build_headers(user_context), timeout=120)
    response.raise_for_status()
    return response.json()


def list_audit_logs(user_id: str | None = None, action_type: str | None = None, status: str | None = None, answer_source: str | None = None, date_from: str | None = None, date_to: str | None = None, limit: int = 100, user_context: dict | None = None):
    params = {"limit": limit}
    if user_id:
        params["user_id"] = user_id
    if action_type:
        params["action_type"] = action_type
    if status:
        params["status"] = status
    if answer_source:
        params["answer_source"] = answer_source
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    response = requests.get(f"{BACKEND_BASE_URL}/admin/audit-logs", params=params, headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()


def get_audit_log(audit_log_id: str, user_context: dict | None = None):
    response = requests.get(f"{BACKEND_BASE_URL}/admin/audit-logs/{audit_log_id}", headers=_build_headers(user_context), timeout=30)
    response.raise_for_status()
    return response.json()
