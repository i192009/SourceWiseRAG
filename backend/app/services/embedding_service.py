import os
from typing import List

from dotenv import load_dotenv
from pymilvus import model

load_dotenv()


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class EmbeddingService:
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        self.device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "1"))
        self.normalize = _to_bool(os.getenv("EMBEDDING_NORMALIZE", "true"), True)

        query_prefix = os.getenv("EMBEDDING_QUERY_PREFIX", "query:").strip()
        doc_prefix = os.getenv("EMBEDDING_DOC_PREFIX", "passage:").strip()

        self.ef = model.dense.SentenceTransformerEmbeddingFunction(
            model_name=self.model_name,
            batch_size=self.batch_size,
            query_instruction=f"{query_prefix} ",
            doc_instruction=f"{doc_prefix} ",
            device=self.device,
            normalize_embeddings=self.normalize,
        )

    def embed_documents(self, texts: List[str]):
        if not texts:
            return []
        return self.ef.encode_documents(texts)

    def embed_queries(self, texts: List[str]):
        if not texts:
            return []
        return self.ef.encode_queries(texts)

    @property
    def dim(self) -> int:
        return self.ef.dim
