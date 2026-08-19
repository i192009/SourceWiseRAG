import streamlit as st
from utils.auth import init_session_defaults, render_auth_status

st.set_page_config(
    page_title="RAG MVP Console",
    page_icon="📚",
    layout="wide",
)

init_session_defaults()
render_auth_status()

st.title("RAG MVP Console")
st.caption("Internal console for upload, retrieval, web search, audit logs, and user management.")

if st.session_state.get("is_authenticated"):
    st.success(
        f"Logged in as {st.session_state.get('current_name')} "
        f"(@{st.session_state.get('current_username')})"
    )
else:
    st.warning("Please login from the sidebar pages to use protected pages.")
    st.info("You can sign up first, then login.")
