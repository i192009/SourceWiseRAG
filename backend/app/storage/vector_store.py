import os
from dotenv import load_dotenv
from pymilvus import MilvusClient, DataType

load_dotenv()

COLLECTION_NAME = "rag_chunks"


def get_milvus_client():
    mode = os.getenv("VECTOR_DB_MODE", "lite").strip().lower()

    if mode == "lite":
        lite_path = os.getenv("MILVUS_LITE_PATH", "./data/milvus_lite.db")
        return MilvusClient(lite_path)

    uri = os.getenv("MILVUS_URI", "http://localhost:19530")
    return MilvusClient(uri=uri)


def ensure_collection(client, dim: int = 384):
    existing = client.list_collections()
    if COLLECTION_NAME in existing:
        return

    schema = MilvusClient.create_schema(
        auto_id=False,
        enable_dynamic_field=False,
    )

    schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(field_name="source_id", datatype=DataType.VARCHAR, max_length=64)
    schema.add_field(field_name="filename", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="page_no", datatype=DataType.INT64)
    schema.add_field(field_name="sheet_name", datatype=DataType.VARCHAR, max_length=256)
    schema.add_field(field_name="section_type", datatype=DataType.VARCHAR, max_length=128)
    schema.add_field(field_name="version", datatype=DataType.INT64)
    schema.add_field(field_name="metadata", datatype=DataType.JSON)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        metric_type="IP",
        index_type="AUTOINDEX",
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )


def upsert_chunks(client, rows: list[dict]):
    if not rows:
        return []
    return client.upsert(collection_name=COLLECTION_NAME, data=rows)


def search_dense(client, query_vector, top_k=5, filter_expr=None):
    return client.search(
        collection_name=COLLECTION_NAME,
        data=[query_vector],
        anns_field="dense_vector",
        limit=top_k,
        filter=filter_expr,
        output_fields=[
            "chunk_id",
            "source_id",
            "filename",
            "page_no",
            "sheet_name",
            "section_type",
            "version",
            "metadata",
        ],
    )


def delete_chunks_by_source(client, source_id: str):
    return client.delete(
        collection_name=COLLECTION_NAME,
        filter=f'source_id == "{source_id}"',
    )
