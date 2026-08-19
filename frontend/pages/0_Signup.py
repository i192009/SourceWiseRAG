import streamlit as st

from services.api_client import signup_user
from utils.auth import init_session_defaults, render_auth_status

st.set_page_config(page_title="Signup", page_icon="📝", layout="wide")
init_session_defaults()
render_auth_status()

st.title("Signup")

if st.session_state.get("is_authenticated"):
    st.warning(
        f"You are already logged in as {st.session_state.get('current_name')} "
        f"(@{st.session_state.get('current_username')}). Logout first if you want to create another account."
    )
    st.stop()

with st.form("signup_form"):
    name = st.text_input("Name")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Signup", use_container_width=True)

if submitted:
    if not name.strip() or not username.strip() or not password:
        st.error("Name, username, and password are required.")
    else:
        try:
            response = signup_user(
                name=name.strip(),
                username=username.strip(),
                password=password,
            )

            st.success(
                f"Signup successful for {response['name']} (@{response['username']}). "
                f"Redirecting to Login..."
            )

            st.session_state["prefill_login_username"] = response["username"]
            st.switch_page("pages/0_Login.py")

        except Exception as e:
            st.exception(e)
