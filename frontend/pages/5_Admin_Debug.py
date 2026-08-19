import pandas as pd
import streamlit as st

from services.api_client import get_health, list_audit_logs, get_audit_log
from utils.auth import init_session_defaults, render_auth_status, require_auth, get_current_user_context

st.set_page_config(page_title="Admin / Debug", page_icon="🛠️", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Admin / Debug")
st.caption("Inspect structured audit logs for uploads, chat, web fallback, save actions, deletions, and user actions.")

st.subheader("System overview")

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("Check backend health", use_container_width=True):
        try:
            st.session_state["admin_health_response"] = get_health(user_context=user_context)
        except Exception as e:
            st.session_state["admin_health_response"] = {"error": str(e)}

with col2:
    health_payload = st.session_state.get("admin_health_response")
    if health_payload:
        st.json(health_payload)
    else:
        st.info("Health has not been checked yet.")

st.divider()

st.header("Audit Logs")
st.caption("Product/business trace logs. System logs remain file-based for now.")

with st.expander("Filters", expanded=True):
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    filter_user_id = col1.text_input("User ID")
    filter_action_type = col2.selectbox(
        "Action Type",
        options=[
            "",
            "chat_asked",
            "chat_answered",
            "chat_fallback_used",
            "file_uploaded",
            "source_deleted",
            "web_search_run",
            "web_search_saved",
            "user_signed_up",
            "user_logged_in",
            "user_deleted",
            "conversation_created",
            "conversation_deleted",
            "conversation_restarted",
            "chat_files_attached",
        ],
        index=0,
    )
    filter_status = col3.selectbox("Status", options=["", "success", "failed"], index=0)
    filter_answer_source = col4.selectbox("Answer Source", options=["", "internal", "web"], index=0)
    filter_date_from = col5.text_input("Date From (ISO, optional)", placeholder="2026-04-01T00:00:00")
    filter_date_to = col6.text_input("Date To (ISO, optional)", placeholder="2026-04-30T23:59:59")

    limit = st.number_input("Limit", min_value=1, max_value=1000, value=100, step=10)

    refresh_logs = st.button("Load audit logs", type="primary", use_container_width=True)

if refresh_logs or not st.session_state.get("admin_audit_logs_response"):
    try:
        st.session_state["admin_audit_logs_response"] = list_audit_logs(
            user_id=filter_user_id.strip() or None,
            action_type=filter_action_type or None,
            status=filter_status or None,
            answer_source=filter_answer_source or None,
            date_from=filter_date_from.strip() or None,
            date_to=filter_date_to.strip() or None,
            limit=int(limit),
            user_context=user_context,
        )
    except Exception as e:
        st.session_state["admin_audit_logs_response"] = {"error": str(e), "items": []}

audit_response = st.session_state.get("admin_audit_logs_response") or {}
if "error" in audit_response:
    st.error(audit_response["error"])

audit_items = audit_response.get("items", [])

st.subheader("Recent audit log table")

if not audit_items:
    st.info("No audit logs found for the current filters.")
else:
    table_rows = []
    for item in audit_items:
        table_rows.append({
            "audit_log_id": item.get("audit_log_id"),
            "user_id": item.get("user_id"),
            "username": item.get("username"),
            "action_type": item.get("action_type"),
            "answer_source": item.get("answer_source"),
            "status": item.get("status"),
            "source_id": item.get("source_id"),
            "job_id": item.get("job_id"),
            "request_latency_ms": item.get("request_latency_ms"),
            "created_at": item.get("created_at"),
            "question_preview": (item.get("question") or "")[:80],
            "answer_preview": (item.get("answer") or "")[:120],
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    selected_audit_log_id = st.selectbox(
        "Select an audit log to inspect",
        options=[item["audit_log_id"] for item in table_rows],
        index=0,
    )

    try:
        selected_log = get_audit_log(selected_audit_log_id, user_context=user_context)
    except Exception as e:
        selected_log = {"error": str(e)}

    st.subheader("Selected audit log details")

    if "error" in selected_log:
        st.error(selected_log["error"])
    else:
        with st.expander("Summary", expanded=True):
            st.write({
                "audit_log_id": selected_log.get("audit_log_id"),
                "user_id": selected_log.get("user_id"),
                "username": selected_log.get("username"),
                "action_type": selected_log.get("action_type"),
                "answer_source": selected_log.get("answer_source"),
                "status": selected_log.get("status"),
                "request_latency_ms": selected_log.get("request_latency_ms"),
                "created_at": selected_log.get("created_at"),
                "source_id": selected_log.get("source_id"),
                "job_id": selected_log.get("job_id"),
            })

        with st.expander("Question / Answer", expanded=True):
            st.write("### Question")
            st.write(selected_log.get("question") or "—")
            st.write("### Answer")
            st.write(selected_log.get("answer") or "—")

        with st.expander("Citations"):
            st.json(selected_log.get("citations") or [])

        with st.expander("Retrieved Chunk IDs"):
            st.json(selected_log.get("retrieved_chunk_ids") or [])

        with st.expander("Applied Filters"):
            st.json(selected_log.get("filters") or {})

        with st.expander("Metadata"):
            st.json(selected_log.get("metadata") or {})

        with st.expander("Raw JSON"):
            st.json(selected_log)

st.divider()

st.header("System Logs")
st.info("System logs are currently file-based only. They remain separate from audit logs and are not yet rendered in the Admin page.")
