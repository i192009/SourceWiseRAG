import streamlit as st


def render_citations(citations: list[dict], show_scores: bool = False):
    st.subheader("Citations")
    if not citations:
        st.info("No citations returned.")
        return

    for idx, item in enumerate(citations, start=1):
        parts = [str(item.get("filename") or "unknown")]
        if item.get("page_no") is not None and item.get("page_no") != "":
            parts.append(f"page {item['page_no']}")
        elif item.get("sheet_name"):
            parts.append(f"sheet {item['sheet_name']}")
        if item.get("version") is not None:
            parts.append(f"v{item['version']}")

        with st.container(border=True):
            st.write(f"{idx}. " + " | ".join(parts))
            if item.get("chunk_id"):
                st.caption(f"Chunk ID: {item['chunk_id']}")
            if item.get("section_type"):
                st.caption(f"Section Type: {item['section_type']}")
            if show_scores and item.get("score") is not None:
                st.caption(f"Score: {item['score']}")
