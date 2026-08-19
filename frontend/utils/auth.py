import os

import streamlit as st
from utils.config import SESSION_DEFAULTS


def init_session_defaults():
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if os.getenv("PORTFOLIO_SCREENSHOT_MODE") == "1":
        st.session_state["is_authenticated"] = True
        st.session_state["current_user_id"] = "portfolio-user-001"
        st.session_state["current_username"] = "portfolio_demo"
        st.session_state["current_name"] = "Portfolio Demo"
        st.session_state["selected_source_id"] = "portfolio-source-1"
        st.session_state["selected_filename"] = "supplier-agreement-v2.pdf"
        st.session_state["selected_version"] = 2


def get_current_user_context():
    if not st.session_state.get("is_authenticated"):
        return None

    return {
        "user_id": st.session_state.get("current_user_id"),
        "username": st.session_state.get("current_username"),
        "name": st.session_state.get("current_name"),
    }


def clear_auth_state():
    st.session_state["is_authenticated"] = False
    st.session_state["current_user_id"] = None
    st.session_state["current_username"] = None
    st.session_state["current_name"] = None


def logout_current_user():
    clear_auth_state()
    st.session_state["selected_source_id"] = None
    st.session_state["selected_filename"] = None
    st.session_state["selected_version"] = None
    st.session_state["last_chat_response"] = None
    st.session_state["last_upload_response"] = None
    st.session_state["last_job_id"] = None


def require_auth():
    if not st.session_state.get("is_authenticated"):
        st.warning("Please login from the sidebar pages to use this page.")
        st.stop()


def render_auth_status():
    with st.sidebar:
        st.markdown("### Session")

        if st.session_state.get("is_authenticated"):
            st.success(
                f"Logged in as: {st.session_state.get('current_name')} "
                f"(@{st.session_state.get('current_username')})"
            )
            if st.button("Logout", use_container_width=True):
                logout_current_user()
                st.rerun()
        else:
            st.info("Not logged in.")
            st.caption("Use Login or Signup from the sidebar.")
