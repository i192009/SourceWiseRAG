from backend.app.services.embedding_service import EmbeddingService
from backend.app.storage.vector_store import get_milvus_client, search_dense


class RetrievalService:
    def __init__(self):
        self.embedder = EmbeddingService()
        self.client = get_milvus_client()

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_id: str | None = None,
        filename: str | None = None,
        version: int | None = None,
        sheet_name: str | None = None,
        page_no: int | None = None,
    ):
        query_vector = self.embedder.embed_queries([query])[0]

        filters = []
        if source_id:
            filters.append(f'source_id == "{source_id}"')
        if filename:
            filters.append(f'filename == "{filename}"')
        if version is not None:
            filters.append(f"version == {version}")
        if sheet_name:
            filters.append(f'sheet_name == "{sheet_name}"')
        if page_no is not None:
            filters.append(f"page_no == {page_no}")

        filter_expr = " and ".join(filters) if filters else None

        results = search_dense(
            client=self.client,
            query_vector=query_vector,
            top_k=top_k,
            filter_expr=filter_expr,
        )

        return results[0] if results else []
