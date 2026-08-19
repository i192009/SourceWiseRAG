import streamlit as st

from services.api_client import list_sources, get_source, get_source_chunks, delete_source
from utils.auth import init_session_defaults, render_auth_status, require_auth, get_current_user_context

st.set_page_config(page_title="Documents", page_icon="📚", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Documents")
st.caption("Browse indexed sources, choose what Chat should use, or delete a source.")

with st.expander("Filters", expanded=True):
    col1, col2, col3 = st.columns(3)

    filter_filename = col1.text_input("Filename")
    filter_version_raw = col2.text_input("Version")
    filter_status = col3.selectbox("Status", options=["", "uploaded", "processing", "ready", "failed"], index=0)

version_value = None
if filter_version_raw.strip():
    try:
        version_value = int(filter_version_raw.strip())
    except ValueError:
        st.warning("Version must be an integer.")

try:
    sources_response = list_sources(
        filename=filter_filename.strip() or None,
        version=version_value,
        status=filter_status or None,
        user_context=user_context,
    )
    sources = sources_response.get("items", [])
except Exception as e:
    st.exception(e)
    sources = []

st.subheader("Source list")

if not sources:
    st.info("No sources found.")
else:
    options = []
    label_to_source = {}

    for src in sources:
        label = f"{src['filename']} | v{src['version']} | {src['status']} | {src['source_id'][:8]}"
        options.append(label)
        label_to_source[label] = src

    selected_label = st.selectbox("Choose a source", options=options)
    selected_source = label_to_source[selected_label]
    selected_source_id = selected_source["source_id"]

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("### Source details")
        st.json(selected_source)

    with col2:
        st.write("### Use in Chat")
        if st.button("Select this document", type="primary", use_container_width=True):
            st.session_state["selected_source_id"] = selected_source["source_id"]
            st.session_state["selected_filename"] = selected_source["filename"]
            st.session_state["selected_version"] = selected_source["version"]
            st.success("Document selection saved for Chat page.")

    st.write("### Current chat selection")
    st.write({
        "selected_source_id": st.session_state.get("selected_source_id"),
        "selected_filename": st.session_state.get("selected_filename"),
        "selected_version": st.session_state.get("selected_version"),
    })

    with st.expander("More details"):
        try:
            source_details = get_source(selected_source_id, user_context=user_context)
            st.write("#### Full source record")
            st.json(source_details)
        except Exception as e:
            st.exception(e)

        try:
            chunk_data = get_source_chunks(selected_source_id, limit=10, user_context=user_context)
            st.write("#### Sample chunks")
            st.json(chunk_data)
        except Exception as e:
            st.exception(e)

    st.write("### Delete source")
    st.warning("Deleting a source removes its vectors, metadata, and raw file artifact.")

    confirm_delete = st.checkbox(
        "I understand this action cannot be undone for this source.",
        key=f"confirm_delete_{selected_source_id}",
    )

    if st.button("Delete this source", type="secondary", use_container_width=True):
        if not confirm_delete:
            st.error("Please confirm deletion first.")
        else:
            try:
                delete_response = delete_source(selected_source_id, user_context=user_context)

                if st.session_state.get("selected_source_id") == selected_source_id:
                    st.session_state["selected_source_id"] = None
                    st.session_state["selected_filename"] = None
                    st.session_state["selected_version"] = None

                st.success("Source deleted successfully.")
                st.json(delete_response)
                st.rerun()

            except Exception as e:
                st.exception(e)
