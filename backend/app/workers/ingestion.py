import uuid

from backend.app.storage.sqlite_store import (
    update_job_status,
    update_source_status,
    insert_document,
    insert_chunk,
)
from backend.app.storage.vector_store import (
    get_milvus_client,
    ensure_collection,
    upsert_chunks,
)
from backend.app.services.parser_service import ParserService
from backend.app.services.normalization_service import NormalizationService
from backend.app.services.chunking_service import ChunkingService
from backend.app.services.embedding_service import EmbeddingService


def run_ingestion(
    job_id: str,
    source_id: str,
    file_path: str,
    original_filename: str,
    source_version: int,
):
    parser = ParserService()
    normalizer = NormalizationService()
    chunker = ChunkingService()
    embedder = EmbeddingService()

    client = get_milvus_client()
    ocr = None

    try:
        update_job_status(job_id, "running")
        update_source_status(source_id, "processing")

        parsed_units = parser.parse(file_path)
        ensure_collection(client, dim=embedder.dim)

        for unit in parsed_units:
            raw_text = unit.get("raw_text", "")
            ocr_confidence = unit.get("ocr_confidence")

            if unit.get("needs_ocr"):
                if ocr is None:
                    from backend.app.services.ocr_service import OCRService
                    ocr = OCRService()

                ocr_result = ocr.extract_text_with_confidence(
                    unit.get("source_meta", {}).get("file_path", file_path)
                )
                raw_text = ocr_result["text"]
                ocr_confidence = ocr_result["average_confidence"]

            normalized_text = normalizer.normalize_text(raw_text)
            if not normalized_text:
                continue

            document_id = str(uuid.uuid4())

            insert_document({
                "document_id": document_id,
                "source_id": source_id,
                "section_type": unit["unit_type"],
                "page_no": unit.get("page_number"),
                "sheet_name": unit.get("sheet_name"),
                "raw_text": raw_text,
            })

            normalized_unit = {
                "unit_type": unit["unit_type"],
                "unit_index": unit["unit_index"],
                "page_number": unit.get("page_number"),
                "sheet_name": unit.get("sheet_name"),
                "heading_path": unit.get("heading_path", []),
                "raw_text": normalized_text,
            }

            structured_chunks = chunker.chunk_units(
                source_id=source_id,
                document_id=document_id,
                units=[normalized_unit],
            )

            if not structured_chunks:
                continue

            chunk_texts = [c["text"] for c in structured_chunks]
            vectors = embedder.embed_documents(chunk_texts)

            milvus_rows = []

            for chunk_obj, vector in zip(structured_chunks, vectors):
                chunk_id = str(uuid.uuid4())

                chunk_metadata = {
                    **chunk_obj["metadata"],
                    "filename": original_filename,
                    "version": source_version,
                    "ocr_confidence": ocr_confidence,
                    "text": chunk_obj["text"],
                }

                insert_chunk({
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "document_id": document_id,
                    "chunk_index": chunk_obj["chunk_index"],
                    "text": chunk_obj["text"],
                    "token_count": chunk_obj["token_count"],
                    "metadata_json": chunk_metadata,
                })

                milvus_rows.append({
                    "chunk_id": chunk_id,
                    "dense_vector": vector,
                    "source_id": source_id,
                    "filename": original_filename,
                    "page_no": int(chunk_metadata.get("page_no") or 0),
                    "sheet_name": chunk_metadata.get("sheet_name") or "",
                    "section_type": chunk_metadata.get("section_type") or unit["unit_type"],
                    "version": int(source_version),
                    "metadata": chunk_metadata,
                })

            if milvus_rows:
                upsert_chunks(client, milvus_rows)

        update_source_status(source_id, "ready")
        update_job_status(job_id, "completed")

    except Exception as e:
        update_source_status(source_id, "failed")
        update_job_status(job_id, "failed", str(e))
        raise
