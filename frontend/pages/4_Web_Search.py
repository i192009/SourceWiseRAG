import streamlit as st

from services.api_client import web_search, save_web_search_results, get_job_status
from components.job_status import render_job_status
from utils.auth import init_session_defaults, render_auth_status, require_auth, get_current_user_context

st.set_page_config(page_title="Web Search", page_icon="🌐", layout="wide")
init_session_defaults()
render_auth_status()
require_auth()
user_context = get_current_user_context()

st.title("Web Search")
st.caption("Search updated information from the internet through the backend, then choose whether to save selected results into the knowledge base.")

if "last_web_search_response" not in st.session_state:
    st.session_state["last_web_search_response"] = None

if "last_web_search_save_response" not in st.session_state:
    st.session_state["last_web_search_save_response"] = None

with st.form("web_search_form"):
    query = st.text_area("Search query", placeholder="e.g. latest contract law updates in UK", height=100)
    limit = st.number_input("Result limit", min_value=1, max_value=10, value=5, step=1)
    search_clicked = st.form_submit_button("Search", use_container_width=True)

if search_clicked:
    clean_query = (query or "").strip()
    if not clean_query:
        st.error("Search query is required.")
    else:
        try:
            with st.spinner("Searching updated information..."):
                response = web_search(clean_query, int(limit), user_context=user_context)
            st.session_state["last_web_search_response"] = response
            st.session_state["last_web_search_save_response"] = None
            st.success("Search completed.")
        except Exception as e:
            st.exception(e)

search_response = st.session_state.get("last_web_search_response")

if search_response:
    st.subheader("Search results")
    st.json({"query": search_response.get("query"), "count": len(search_response.get("results", []))})

    results = search_response.get("results", [])

    if not results:
        st.info("No results returned.")
    else:
        selected_results = []

        for idx, item in enumerate(results):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            source_engine = item.get("source_engine", "searxng")

            with st.container(border=True):
                checked = st.checkbox(f"Select result {idx + 1}: {title}", key=f"web_result_select_{idx}")

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

        st.subheader("Save selected results")

        save_mode = st.selectbox("Save mode", options=["ingest", "metadata_only"], index=0)

        save_clicked = st.button("Save selected results", type="primary", use_container_width=True)

        if save_clicked:
            if not selected_results:
                st.error("Please select at least one result to save.")
            else:
                try:
                    with st.spinner("Saving selected results..."):
                        save_response = save_web_search_results(
                            query=search_response.get("query", ""),
                            selected_results=selected_results,
                            save_mode=save_mode,
                            user_context=user_context,
                        )

                    st.session_state["last_web_search_save_response"] = save_response

                    if save_response.get("source_id"):
                        st.session_state["selected_source_id"] = save_response.get("source_id")
                    if save_response.get("filename"):
                        st.session_state["selected_filename"] = save_response.get("filename")
                    if save_response.get("version") is not None:
                        st.session_state["selected_version"] = save_response.get("version")
                    if save_response.get("job_id"):
                        st.session_state["last_job_id"] = save_response.get("job_id")

                    st.success("Selected results saved.")

                except Exception as e:
                    st.exception(e)

save_response = st.session_state.get("last_web_search_save_response")

if save_response:
    st.subheader("Save result summary")
    st.json(save_response)

    source_id = save_response.get("source_id")
    job_id = save_response.get("job_id")

    if source_id:
        st.session_state["selected_source_id"] = source_id

    if job_id:
        st.session_state["last_job_id"] = job_id
        st.subheader("Ingestion job status")

        col1, col2 = st.columns(2)
        refresh_clicked = col1.button("Refresh job status", use_container_width=True, key="refresh_web_job")
        auto_refresh = col2.checkbox("Auto-refresh on rerun", value=False, key="auto_refresh_web_job")

        if refresh_clicked or auto_refresh:
            try:
                job_data = get_job_status(job_id, user_context=user_context)
                render_job_status(job_data)
            except Exception as e:
                st.exception(e)
        else:
            st.info(f"Current ingestion job id: {job_id}")
