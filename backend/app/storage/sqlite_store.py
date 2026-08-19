import json
import sqlite3
from contextlib import contextmanager
from backend.app.core.settings import SQLITE_PATH


def init_sqlite():
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_message_at TEXT,
            message_count INTEGER NOT NULL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            mime_type TEXT,
            stored_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            version INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            section_type TEXT NOT NULL,
            page_no INTEGER,
            sheet_name TEXT,
            raw_text TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            job_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            chat_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            retrieved_chunk_ids TEXT NOT NULL,
            final_answer TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS web_search_sessions (
            session_id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS web_search_results (
            result_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            snippet TEXT NOT NULL,
            source_engine TEXT NOT NULL,
            is_saved INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES web_search_sessions(session_id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            action_type TEXT NOT NULL,
            source_id TEXT,
            job_id TEXT,
            question TEXT,
            answer TEXT,
            answer_source TEXT,
            citations_json TEXT,
            retrieved_chunk_ids_json TEXT,
            filters_json TEXT,
            metadata_json TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            request_latency_ms INTEGER,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id ON conversation_messages(conversation_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at ON conversation_messages(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_file_hash ON sources(file_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_filename_version ON sources(filename, version)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source_id ON ingestion_jobs(source_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON ingestion_jobs(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_web_search_results_session_id ON web_search_results(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action_type ON audit_logs(action_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_answer_source ON audit_logs(answer_source)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")

        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _json_loads_or_none(value):
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _normalize_audit_log_row(row):
    item = dict(row)
    item["citations"] = _json_loads_or_none(item.pop("citations_json", None))
    item["retrieved_chunk_ids"] = _json_loads_or_none(item.pop("retrieved_chunk_ids_json", None))
    item["filters"] = _json_loads_or_none(item.pop("filters_json", None))
    item["metadata"] = _json_loads_or_none(item.pop("metadata_json", None))
    return item


def _normalize_conversation_message_row(row):
    item = dict(row)
    item["metadata"] = _json_loads_or_none(item.pop("metadata_json", None))
    return item


def insert_user(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO users (user_id, name, username, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            record["user_id"],
            record["name"],
            record["username"],
            record["password_hash"],
            record["created_at"],
        ))
        conn.commit()


def get_user_by_username(username: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT user_id, name, username, password_hash, created_at
        FROM users
        WHERE username = ?
        """, (username,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT user_id, name, username, password_hash, created_at
        FROM users
        WHERE user_id = ?
        """, (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users():
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT user_id, name, username, created_at
        FROM users
        ORDER BY created_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def delete_user(user_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


def insert_conversation(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO conversations (
            conversation_id, user_id, title, created_at, updated_at, last_message_at, message_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record["conversation_id"],
            record["user_id"],
            record["title"],
            record["created_at"],
            record["updated_at"],
            record.get("last_message_at"),
            record.get("message_count", 0),
        ))
        conn.commit()


def get_conversation(conversation_id: str, user_id: str | None = None):
    query = """
    SELECT conversation_id, user_id, title, created_at, updated_at, last_message_at, message_count
    FROM conversations
    WHERE conversation_id = ?
    """
    params = [conversation_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    with get_conn() as conn:
        cur = conn.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def list_conversations(user_id: str, limit: int = 100, offset: int = 0):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT
            c.conversation_id,
            c.user_id,
            c.title,
            c.created_at,
            c.updated_at,
            c.last_message_at,
            c.message_count,
            (
                SELECT m.content
                FROM conversation_messages m
                WHERE m.conversation_id = c.conversation_id
                ORDER BY m.created_at DESC
                LIMIT 1
            ) AS last_message
        FROM conversations c
        WHERE c.user_id = ?
        ORDER BY COALESCE(c.last_message_at, c.updated_at) DESC
        LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        return [dict(row) for row in cur.fetchall()]


def update_conversation_title(conversation_id: str, title: str):
    with get_conn() as conn:
        conn.execute("""
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE conversation_id = ?
        """, (title, conversation_id))
        conn.commit()


def insert_conversation_message(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO conversation_messages (
            message_id, conversation_id, role, content, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record["message_id"],
            record["conversation_id"],
            record["role"],
            record["content"],
            json.dumps(record.get("metadata"), ensure_ascii=False) if record.get("metadata") is not None else None,
            record["created_at"],
        ))
        conn.execute("""
        UPDATE conversations
        SET updated_at = ?, last_message_at = ?, message_count = message_count + 1
        WHERE conversation_id = ?
        """, (
            record["created_at"],
            record["created_at"],
            record["conversation_id"],
        ))
        conn.commit()


def list_conversation_messages(conversation_id: str, limit: int = 200, offset: int = 0):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT message_id, conversation_id, role, content, metadata_json, created_at
        FROM conversation_messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
        """, (conversation_id, limit, offset))
        return [_normalize_conversation_message_row(row) for row in cur.fetchall()]


def restart_conversation(conversation_id: str, user_id: str, reset_title: str = "New Chat"):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT conversation_id, user_id, title
        FROM conversations
        WHERE conversation_id = ? AND user_id = ?
        """, (conversation_id, user_id))
        row = cur.fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("""
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP, last_message_at = NULL, message_count = 0
        WHERE conversation_id = ? AND user_id = ?
        """, (reset_title, conversation_id, user_id))
        conn.commit()
        return get_conversation(conversation_id, user_id=user_id)


def delete_conversation(conversation_id: str, user_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT conversation_id, user_id, title
        FROM conversations
        WHERE conversation_id = ? AND user_id = ?
        """, (conversation_id, user_id))
        row = cur.fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM conversations WHERE conversation_id = ? AND user_id = ?", (conversation_id, user_id))
        conn.commit()
        return dict(row)


def insert_source(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO sources (
            source_id, filename, file_hash, mime_type, stored_path,
            size_bytes, version, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["source_id"],
            record["filename"],
            record["file_hash"],
            record.get("mime_type"),
            record["stored_path"],
            record["size_bytes"],
            record["version"],
            record["status"],
            record["created_at"],
        ))
        conn.commit()


def insert_document(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO documents (document_id, source_id, section_type, page_no, sheet_name, raw_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record["document_id"],
            record["source_id"],
            record["section_type"],
            record.get("page_no"),
            record.get("sheet_name"),
            record["raw_text"],
        ))
        conn.commit()


def insert_chunk(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO chunks (chunk_id, source_id, document_id, chunk_index, text, token_count, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record["chunk_id"],
            record["source_id"],
            record["document_id"],
            record["chunk_index"],
            record["text"],
            record["token_count"],
            json.dumps(record["metadata_json"], ensure_ascii=False),
        ))
        conn.commit()


def insert_job(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO ingestion_jobs (job_id, source_id, stage, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record["job_id"],
            record["source_id"],
            record["stage"],
            record["status"],
            record.get("error_message"),
            record["created_at"],
        ))
        conn.commit()


def insert_chat_log(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO chat_logs (query, retrieved_chunk_ids, final_answer, timestamp)
        VALUES (?, ?, ?, ?)
        """, (
            record["query"],
            json.dumps(record["retrieved_chunk_ids"], ensure_ascii=False),
            record["final_answer"],
            record["timestamp"],
        ))
        conn.commit()


def insert_web_search_session(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO web_search_sessions (session_id, query, created_at, status)
        VALUES (?, ?, ?, ?)
        """, (
            record["session_id"],
            record["query"],
            record["created_at"],
            record["status"],
        ))
        conn.commit()


def insert_web_search_result(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO web_search_results (
            result_id, session_id, title, url, snippet,
            source_engine, is_saved, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["result_id"],
            record["session_id"],
            record["title"],
            record["url"],
            record["snippet"],
            record["source_engine"],
            record["is_saved"],
            record["created_at"],
        ))
        conn.commit()


def insert_audit_log(record: dict):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO audit_logs (
            audit_log_id, user_id, username, action_type, source_id, job_id,
            question, answer, answer_source, citations_json, retrieved_chunk_ids_json,
            filters_json, metadata_json, status, error_message, request_latency_ms, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["audit_log_id"],
            record["user_id"],
            record["username"],
            record["action_type"],
            record.get("source_id"),
            record.get("job_id"),
            record.get("question"),
            record.get("answer"),
            record.get("answer_source"),
            record.get("citations_json"),
            record.get("retrieved_chunk_ids_json"),
            record.get("filters_json"),
            record.get("metadata_json"),
            record["status"],
            record.get("error_message"),
            record.get("request_latency_ms"),
            record["created_at"],
        ))
        conn.commit()


def update_source_status(source_id: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE sources SET status = ? WHERE source_id = ?", (status, source_id))
        conn.commit()


def update_job_status(job_id: str, status: str, error_message: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE ingestion_jobs SET status = ?, error_message = ? WHERE job_id = ?",
            (status, error_message, job_id),
        )
        conn.commit()


def get_latest_version_for_filename(filename: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_version FROM sources WHERE filename = ?",
            (filename,),
        )
        row = cur.fetchone()
        return int(row["max_version"]) if row and row["max_version"] is not None else 0


def get_job(job_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT job_id, source_id, stage, status, error_message, created_at
        FROM ingestion_jobs
        WHERE job_id = ?
        """, (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_sources(filename: str | None = None, version: int | None = None, status: str | None = None):
    query = """
    SELECT source_id, filename, file_hash, mime_type, stored_path, size_bytes, version, status, created_at
    FROM sources
    """
    clauses = []
    params = []
    if filename:
        clauses.append("filename = ?")
        params.append(filename)
    if version is not None:
        clauses.append("version = ?")
        params.append(version)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def get_source(source_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT source_id, filename, file_hash, mime_type, stored_path, size_bytes, version, status, created_at
        FROM sources
        WHERE source_id = ?
        """, (source_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_chunks_for_source(source_id: str, limit: int = 50):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT chunk_id, source_id, document_id, chunk_index, text, token_count, metadata_json
        FROM chunks
        WHERE source_id = ?
        ORDER BY chunk_index ASC
        LIMIT ?
        """, (source_id, limit))
        return [dict(row) for row in cur.fetchall()]


def get_chunks_by_source(source_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT chunk_id, metadata_json
        FROM chunks
        WHERE source_id = ?
        """, (source_id,))
        return [dict(row) for row in cur.fetchall()]


def delete_source_tree(source_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
        conn.commit()


def list_audit_logs(
    *,
    user_id: str | None = None,
    action_type: str | None = None,
    status: str | None = None,
    answer_source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
):
    query = """
    SELECT
        audit_log_id,
        user_id,
        username,
        action_type,
        source_id,
        job_id,
        question,
        answer,
        answer_source,
        citations_json,
        retrieved_chunk_ids_json,
        filters_json,
        metadata_json,
        status,
        error_message,
        request_latency_ms,
        created_at
    FROM audit_logs
    """
    clauses = []
    params = []
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if action_type:
        clauses.append("action_type = ?")
        params.append(action_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if answer_source:
        clauses.append("answer_source = ?")
        params.append(answer_source)
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return [_normalize_audit_log_row(row) for row in cur.fetchall()]


def get_audit_log(audit_log_id: str):
    with get_conn() as conn:
        cur = conn.execute("""
        SELECT
            audit_log_id,
            user_id,
            username,
            action_type,
            source_id,
            job_id,
            question,
            answer,
            answer_source,
            citations_json,
            retrieved_chunk_ids_json,
            filters_json,
            metadata_json,
            status,
            error_message,
            request_latency_ms,
            created_at
        FROM audit_logs
        WHERE audit_log_id = ?
        """, (audit_log_id,))
        row = cur.fetchone()
        return _normalize_audit_log_row(row) if row else None
