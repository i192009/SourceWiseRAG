import streamlit as st

from services.api_client import upload_file_to_backend, get_job_status
from utils.config import ALLOWED_UPLOAD_TYPES
from utils.auth import init_session_defaults, render_auth_status, require_auth, get_current_user_context
from components.job_status import render_job_status

st.set_page_config(page_title="Upload", page_icon="📤", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Upload")
st.caption("Upload one document and send it immediately to FastAPI for persistence and ingestion.")

uploaded_file = st.file_uploader(
    "Choose a document",
    type=ALLOWED_UPLOAD_TYPES,
    accept_multiple_files=False,
    key="upload_widget",
)

source_name = st.text_input(
    "Optional source name",
    placeholder="e.g. contract-v1 or employee-handbook",
)

upload_clicked = st.button("Upload", type="primary", use_container_width=True)

if upload_clicked:
    if uploaded_file is None:
        st.error("Please choose a file first.")
    else:
        try:
            file_bytes = uploaded_file.getvalue()

            response = upload_file_to_backend(
                file_name=uploaded_file.name,
                file_bytes=file_bytes,
                mime_type=getattr(uploaded_file, "type", None),
                source_name=source_name.strip() or None,
                user_context=user_context,
            )

            st.session_state["last_upload_response"] = response
            st.session_state["last_job_id"] = response.get("job_id")
            st.session_state["selected_source_id"] = response.get("source_id")
            st.session_state["selected_filename"] = response.get("filename")
            st.session_state["selected_version"] = response.get("version")

            del file_bytes

            st.success("File uploaded. Ingestion job queued.")

        except Exception as e:
            st.exception(e)

st.subheader("Last upload summary")

last_upload = st.session_state.get("last_upload_response")
if last_upload:
    st.json(last_upload)
else:
    st.info("No file uploaded yet.")

st.subheader("Job polling")

job_id = st.session_state.get("last_job_id")

if job_id:
    col1, col2 = st.columns([1, 1])
    refresh_clicked = col1.button("Refresh job status", use_container_width=True)
    auto_refresh = col2.checkbox("Auto-refresh on rerun", value=False)

    if refresh_clicked or auto_refresh:
        try:
            job_data = get_job_status(job_id, user_context=user_context)
            render_job_status(job_data)
        except Exception as e:
            st.exception(e)
    else:
        st.info(f"Current job id: {job_id}")
else:
    st.info("No job id available yet.")
