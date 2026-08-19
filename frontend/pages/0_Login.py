import streamlit as st

from services.api_client import login_user
from utils.auth import init_session_defaults, render_auth_status

st.set_page_config(page_title="Login", page_icon="🔐", layout="wide")
init_session_defaults()
render_auth_status()

st.title("Login")

if st.session_state.get("is_authenticated"):
    st.warning(
        f"You are already logged in as {st.session_state.get('current_name')} "
        f"(@{st.session_state.get('current_username')}). Logout first if you want to login with another account."
    )
    st.stop()

default_username = st.session_state.get("prefill_login_username", "")

with st.form("login_form"):
    username = st.text_input("Username", value=default_username)
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Login", use_container_width=True)

if submitted:
    if not username.strip() or not password:
        st.error("Username and password are required.")
    else:
        try:
            response = login_user(
                username=username.strip(),
                password=password,
            )

            st.session_state["current_user_id"] = response["user_id"]
            st.session_state["current_username"] = response["username"]
            st.session_state["current_name"] = response["name"]
            st.session_state["is_authenticated"] = True

            if "prefill_login_username" in st.session_state:
                del st.session_state["prefill_login_username"]

            st.success("Login successful.")
            st.rerun()

        except Exception as e:
            st.exception(e)
