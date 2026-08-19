import streamlit as st

from services.api_client import (
    ask_chat_fallback,
    ask_chat_fallback_with_files,
    save_web_search_results,
    create_conversation_api,
    list_conversations_api,
    get_conversation_api,
    get_conversation_messages_api,
    restart_conversation_api,
    delete_conversation_api,
)
from components.citations import render_citations
from utils.auth import init_session_defaults, render_auth_status, require_auth, get_current_user_context
from utils.config import ALLOWED_UPLOAD_TYPES

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Chat")
st.caption("Conversation-based grounded chat with persistent history and file attachments.")

st.markdown(
    """
    <style>
    .chat-loading-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 0.98rem;
        padding: 2px 0 6px 0;
    }
    .chat-loading-dots {
        display: inline-flex;
        gap: 3px;
    }
    .chat-loading-dots span {
        animation: chat-bounce 1.2s infinite ease-in-out;
        font-weight: 700;
        font-size: 1.1rem;
        line-height: 1;
        opacity: 0.25;
    }
    .chat-loading-dots span:nth-child(2) {
        animation-delay: 0.2s;
    }
    .chat-loading-dots span:nth-child(3) {
        animation-delay: 0.4s;
    }
    @keyframes chat-bounce {
        0%, 80%, 100% { opacity: 0.25; transform: translateY(0px); }
        40% { opacity: 1; transform: translateY(-2px); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def refresh_conversations():
    response = list_conversations_api(limit=200, offset=0, user_context=user_context)
    st.session_state["chat_conversations"] = response

    items = response.get("items", [])
    active_id = st.session_state.get("active_conversation_id")

    if active_id:
        exists = any(item["conversation_id"] == active_id for item in items)
        if not exists:
            if items:
                st.session_state["active_conversation_id"] = items[0]["conversation_id"]
                st.session_state["active_conversation_title"] = items[0]["title"]
            else:
                st.session_state["active_conversation_id"] = None
                st.session_state["active_conversation_title"] = None
    elif items:
        st.session_state["active_conversation_id"] = items[0]["conversation_id"]
        st.session_state["active_conversation_title"] = items[0]["title"]


def load_active_conversation():
    active_id = st.session_state.get("active_conversation_id")
    if not active_id:
        return None, []

    detail = get_conversation_api(active_id, user_context=user_context)
    messages_response = get_conversation_messages_api(
        active_id,
        limit=500,
        offset=0,
        user_context=user_context,
    )
    return detail, messages_response.get("items", [])


def derive_latest_web_results(messages: list[dict], last_chat_response: dict | None):
    if last_chat_response and last_chat_response.get("web_results"):
        if last_chat_response.get("conversation_id") == st.session_state.get("active_conversation_id"):
            return last_chat_response.get("web_results", [])

    for message in reversed(messages):
        if message.get("role") == "assistant":
            metadata = message.get("metadata") or {}
            web_results = metadata.get("web_results") or []
            if web_results:
                return web_results

    return []


def render_attachment_block(attachments: list[dict]):
    if not attachments:
        return

    st.caption("Attachments")
    for item in attachments:
        filename = item.get("filename") or item.get("name") or "file"
        version = item.get("version")
        status = item.get("status")
        size_bytes = item.get("size_bytes")

        label_parts = [filename]
        if version is not None:
            label_parts.append(f"v{version}")
        if status:
            label_parts.append(status)
        if size_bytes is not None:
            label_parts.append(f"{size_bytes} bytes")

        st.write("• " + " | ".join(label_parts))


def render_message_history(
    placeholder,
    persisted_messages: list[dict],
    pending_user_message: str | None = None,
    pending_attachments: list[dict] | None = None,
    show_generating: bool = False,
    transient_error: str | None = None,
):
    with placeholder.container():
        if not persisted_messages and not pending_user_message and not transient_error:
            st.info("This chat is empty. Ask your first question below.")
            return

        for message in persisted_messages:
            role = message.get("role", "assistant")
            content = message.get("content", "")
            metadata = message.get("metadata") or {}

            with st.chat_message("user" if role == "user" else "assistant"):
                st.write(content)

                if role == "user":
                    attachments = metadata.get("attachments") or []
                    render_attachment_block(attachments)

                if role == "assistant":
                    answer_source = metadata.get("answer_source")
                    if answer_source == "web":
                        st.caption("Answer source: Web fallback")
                    elif answer_source == "internal":
                        st.caption("Answer source: Internal indexed knowledge")

                    citations = metadata.get("citations") or []
                    if citations:
                        with st.expander("Citations"):
                            render_citations(citations, show_scores=False)

                    retrieved_chunk_ids = metadata.get("retrieved_chunk_ids") or []
                    if retrieved_chunk_ids:
                        with st.expander("Retrieved chunk IDs"):
                            st.json(retrieved_chunk_ids)

        if pending_user_message:
            with st.chat_message("user"):
                st.write(pending_user_message)
                render_attachment_block(pending_attachments or [])

        if show_generating:
            with st.chat_message("assistant"):
                st.markdown(
                    """
                    <div class="chat-loading-wrap">
                        <span>Generating answer</span>
                        <span class="chat-loading-dots">
                            <span>.</span><span>.</span><span>.</span>
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if transient_error:
            with st.chat_message("assistant"):
                st.error(transient_error)


def _parse_optional_int(value: str, field_name: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def _convert_uploaded_files(uploaded_files):
    file_items = []

    for uploaded in uploaded_files or []:
        file_items.append({
            "name": uploaded.name,
            "bytes": uploaded.getvalue(),
            "mime_type": getattr(uploaded, "type", None),
        })

    return file_items


def _build_pending_attachment_preview(file_items: list[dict]):
    preview = []
    for item in file_items:
        preview.append({
            "filename": item["name"],
            "size_bytes": len(item["bytes"]),
            "status": "uploading",
        })
    return preview


if st.session_state.get("chat_conversations") is None:
    try:
        refresh_conversations()
    except Exception as e:
        st.exception(e)
        st.stop()

left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("Chats")

    top_left_1, top_left_2 = st.columns(2)

    if top_left_1.button("New Chat", type="primary", use_container_width=True):
        try:
            response = create_conversation_api(user_context=user_context)
            st.session_state["active_conversation_id"] = response["conversation_id"]
            st.session_state["active_conversation_title"] = response["title"]
            st.session_state["last_chat_response"] = None
            st.session_state["last_chat_web_save_response"] = None
            refresh_conversations()
            st.rerun()
        except Exception as e:
            st.exception(e)

    if top_left_2.button("Reload", use_container_width=True):
        try:
            refresh_conversations()
            st.rerun()
        except Exception as e:
            st.exception(e)

    conversations_response = st.session_state.get("chat_conversations", {"items": []})
    conversations = conversations_response.get("items", [])
    active_conversation_id = st.session_state.get("active_conversation_id")

    if not conversations:
        st.info("No chats yet. Create a new chat to start.")
    else:
        for item in conversations:
            convo_id = item["conversation_id"]
            is_active = convo_id == active_conversation_id

            with st.container(border=True):
                if is_active:
                    st.success(f"**{item['title']}**")
                else:
                    st.write(f"**{item['title']}**")

                st.caption(
                    f"Messages: {item.get('message_count', 0)} | "
                    f"Updated: {item.get('updated_at') or item.get('created_at')}"
                )

                last_message = item.get("last_message")
                if last_message:
                    st.write((last_message[:100] + "...") if len(last_message) > 100 else last_message)

                if st.button(
                    "Open",
                    key=f"open_conversation_{convo_id}",
                    use_container_width=True,
                ):
                    st.session_state["active_conversation_id"] = convo_id
                    st.session_state["active_conversation_title"] = item["title"]
                    st.session_state["last_chat_web_save_response"] = None
                    st.rerun()

with right_col:
    st.subheader("Conversation")

    selected_source_id = st.session_state.get("selected_source_id")
    selected_filename = st.session_state.get("selected_filename")
    selected_version = st.session_state.get("selected_version")

    scope_data = {
        "selected_source_id": selected_source_id,
        "selected_filename": selected_filename,
        "selected_version": selected_version,
    }

    if selected_filename or selected_source_id:
        st.info("Selected document scope for retrieval")
        st.json(scope_data)

    conversation_detail = None
    messages = []

    active_conversation_id = st.session_state.get("active_conversation_id")
    if active_conversation_id:
        try:
            conversation_detail, messages = load_active_conversation()
        except Exception as e:
            st.exception(e)

    action_col_1, action_col_2, action_col_3 = st.columns([1, 1, 1])

    if conversation_detail:
        st.write({
            "conversation_id": conversation_detail["conversation_id"],
            "title": conversation_detail["title"],
            "message_count": conversation_detail["message_count"],
            "created_at": conversation_detail["created_at"],
            "updated_at": conversation_detail["updated_at"],
        })

        with action_col_1:
            confirm_restart = st.checkbox(
                "Confirm restart",
                key=f"confirm_restart_{active_conversation_id}",
            )

        with action_col_2:
            if st.button("Restart Chat", use_container_width=True):
                if not confirm_restart:
                    st.error("Please confirm restart first.")
                else:
                    try:
                        restart_conversation_api(active_conversation_id, user_context=user_context)
                        st.session_state["last_chat_response"] = None
                        st.session_state["last_chat_web_save_response"] = None
                        refresh_conversations()
                        st.rerun()
                    except Exception as e:
                        st.exception(e)

        with action_col_3:
            confirm_delete = st.checkbox(
                "Confirm delete",
                key=f"confirm_delete_{active_conversation_id}",
            )

            if st.button("Delete Chat", use_container_width=True):
                if not confirm_delete:
                    st.error("Please confirm delete first.")
                else:
                    try:
                        delete_conversation_api(active_conversation_id, user_context=user_context)
                        st.session_state["last_chat_response"] = None
                        st.session_state["last_chat_web_save_response"] = None
                        st.session_state["active_conversation_id"] = None
                        st.session_state["active_conversation_title"] = None
                        refresh_conversations()
                        st.rerun()
                    except Exception as e:
                        st.exception(e)

    st.divider()

    history_placeholder = st.empty()
    render_message_history(history_placeholder, messages)

    st.divider()

    with st.expander("Advanced filters"):
        override_source_id = st.text_input(
            "Override source_id",
            value=selected_source_id or "",
            placeholder="Optional",
        )
        override_filename = st.text_input(
            "Override filename",
            value=selected_filename or "",
            placeholder="Optional",
        )
        override_version_raw = st.text_input(
            "Override version",
            value=str(selected_version) if selected_version is not None else "",
            placeholder="Optional integer",
        )
        override_sheet_name = st.text_input("Sheet name", placeholder="Optional")
        override_page_no_raw = st.text_input("Page number", placeholder="Optional integer")
        allow_web_fallback = st.checkbox(
            "Allow web fallback when internal answer is insufficient",
            value=True,
        )
        web_result_limit = st.number_input(
            "Web fallback result limit",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
        )

    with st.form("conversation_chat_form", clear_on_submit=True):
        question = st.text_area(
            "Question",
            placeholder="Ask a grounded question in this chat.",
            height=120,
        )
        attached_files = st.file_uploader(
            "Attach files before asking",
            type=ALLOWED_UPLOAD_TYPES,
            accept_multiple_files=True,
        )
        st.caption("Attached files will be uploaded and ingested before answer generation.")
        top_k = st.number_input("Top K", min_value=1, max_value=10, value=3, step=1)
        submitted = st.form_submit_button("Send", use_container_width=True)

    if submitted:
        clean_question = (question or "").strip()

        if not clean_question:
            st.error("Question is required.")
        else:
            try:
                version_value = _parse_optional_int(override_version_raw, "Version")
                page_no_value = _parse_optional_int(override_page_no_raw, "Page number")
            except ValueError as e:
                st.error(str(e))
                st.stop()

            file_items = _convert_uploaded_files(attached_files)
            pending_attachments = _build_pending_attachment_preview(file_items)
            optimistic_messages = list(messages)

            render_message_history(
                history_placeholder,
                optimistic_messages,
                pending_user_message=clean_question,
                pending_attachments=pending_attachments,
                show_generating=True,
            )

            try:
                common_kwargs = {
                    "question": clean_question,
                    "top_k": int(top_k),
                    "source_id": override_source_id.strip() or None,
                    "filename": override_filename.strip() or None,
                    "version": version_value,
                    "sheet_name": override_sheet_name.strip() or None,
                    "page_no": page_no_value,
                    "conversation_id": st.session_state.get("active_conversation_id"),
                    "user_context": user_context,
                }

                if file_items:
                    response = ask_chat_fallback_with_files(
                        file_items=file_items,
                        allow_web_fallback=allow_web_fallback,
                        web_result_limit=int(web_result_limit),
                        **common_kwargs,
                    )
                else:
                    response = ask_chat_fallback(
                        allow_web_fallback=allow_web_fallback,
                        web_result_limit=int(web_result_limit),
                        **common_kwargs,
                    )

                st.session_state["active_conversation_id"] = response["conversation_id"]
                st.session_state["last_chat_response"] = response
                st.session_state["last_chat_web_save_response"] = None

                attached_result_files = response.get("attached_files") or []
                if attached_result_files:
                    latest = attached_result_files[-1]
                    st.session_state["selected_source_id"] = latest.get("source_id")
                    st.session_state["selected_filename"] = latest.get("filename")
                    st.session_state["selected_version"] = latest.get("version")
                    st.session_state["last_job_id"] = latest.get("job_id")

                refresh_conversations()
                st.rerun()

            except Exception as e:
                render_message_history(
                    history_placeholder,
                    optimistic_messages,
                    pending_user_message=clean_question,
                    pending_attachments=pending_attachments,
                    show_generating=False,
                    transient_error="Failed to generate answer.",
                )
                st.exception(e)

    latest_web_results = derive_latest_web_results(
        messages=messages,
        last_chat_response=st.session_state.get("last_chat_response"),
    )

    last_chat_response = st.session_state.get("last_chat_response")
    if last_chat_response and last_chat_response.get("attached_files"):
        st.divider()
        st.subheader("Attached files processed")
        render_attachment_block(last_chat_response.get("attached_files") or [])

    if latest_web_results:
        st.divider()
        st.subheader("Web fallback results")
        st.caption("Select results and save them into the knowledge base.")

        selected_results = []

        for idx, item in enumerate(latest_web_results):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            source_engine = item.get("source_engine", "searxng")

            with st.container(border=True):
                checked = st.checkbox(
                    f"Select result {idx + 1}: {title}",
                    key=f"chat_web_result_{st.session_state.get('active_conversation_id')}_{idx}",
                )
                st.write(f"**Title:** {title}")
                st.write(f"**URL:** {url}")
                st.write(f"**Source Engine:** {source_engine}")
                st.write(f"**Snippet:** {snippet}")

                if checked:
                    selected_results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "source_engine": source_engine,
                    })

        save_mode = st.selectbox(
            "Save mode",
            options=["ingest", "metadata_only"],
            index=0,
            key=f"chat_save_mode_{st.session_state.get('active_conversation_id')}",
        )

        if st.button("Save selected web results", type="primary", use_container_width=True):
            if not selected_results:
                st.error("Please select at least one result to save.")
            else:
                try:
                    query_for_save = None

                    if messages:
                        for msg in reversed(messages):
                            if msg.get("role") == "user":
                                query_for_save = msg.get("content")
                                break

                    save_response = save_web_search_results(
                        query=query_for_save or "chat fallback save",
                        selected_results=selected_results,
                        save_mode=save_mode,
                        user_context=user_context,
                    )

                    st.session_state["last_chat_web_save_response"] = save_response

                    if save_response.get("source_id"):
                        st.session_state["selected_source_id"] = save_response.get("source_id")
                    if save_response.get("filename"):
                        st.session_state["selected_filename"] = save_response.get("filename")
                    if save_response.get("version") is not None:
                        st.session_state["selected_version"] = save_response.get("version")
                    if save_response.get("job_id"):
                        st.session_state["last_job_id"] = save_response.get("job_id")

                    st.success("Selected web results saved successfully.")

                except Exception as e:
                    st.exception(e)

    save_response = st.session_state.get("last_chat_web_save_response")
    if save_response:
        st.divider()
        st.subheader("Saved web results summary")
        st.json(save_response)
