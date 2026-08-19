import pandas as pd
import streamlit as st

from services.api_client import list_users_api, delete_user_api
from utils.auth import (
    init_session_defaults,
    render_auth_status,
    require_auth,
    get_current_user_context,
    logout_current_user,
)

st.set_page_config(page_title="Users", page_icon="👤", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Users")
st.caption("List all users and delete any user. This is intentionally open for the current MVP.")

try:
    users_response = list_users_api(user_context=user_context)
    users = users_response.get("items", [])
except Exception as e:
    st.exception(e)
    users = []

if not users:
    st.info("No users found.")
else:
    df = pd.DataFrame(users)
    st.dataframe(df, use_container_width=True, hide_index=True)

    options = []
    label_to_user = {}

    for user in users:
        label = f"{user['name']} (@{user['username']}) | {user['user_id'][:8]}"
        options.append(label)
        label_to_user[label] = user

    selected_label = st.selectbox("Select a user", options=options)
    selected_user = label_to_user[selected_label]

    st.subheader("Selected user")
    st.json(selected_user)

    is_self_delete = selected_user["user_id"] == st.session_state.get("current_user_id")
    if is_self_delete:
        st.warning("You are selecting your own account. Deleting it will log you out immediately.")

    confirm_delete = st.checkbox(
        "I understand this will permanently delete the selected user.",
        key=f"confirm_delete_user_{selected_user['user_id']}",
    )

    if st.button("Delete selected user", type="primary", use_container_width=True):
        if not confirm_delete:
            st.error("Please confirm deletion first.")
        else:
            try:
                response = delete_user_api(selected_user["user_id"], user_context=user_context)
                st.success("User deleted successfully.")
                st.json(response)

                if is_self_delete:
                    logout_current_user()

                st.rerun()

            except Exception as e:
                st.exception(e)
