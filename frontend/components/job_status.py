import streamlit as st


def render_job_status(job_data: dict):
    status = job_data.get("status")
    if status == "completed":
        st.success("Ingestion completed.")
    elif status == "failed":
        st.error("Ingestion failed.")
    else:
        st.info(f"Ingestion status: {status}")

    st.json(job_data)
