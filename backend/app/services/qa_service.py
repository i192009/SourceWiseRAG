from datetime import datetime
import logging

from backend.app.clients.ollama_client import OllamaClient
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.storage.sqlite_store import insert_chat_log

logger = logging.getLogger("backend.chat")


class QAService:
    def __init__(self):
        from backend.app.services.retrieval_service import RetrievalService

        self.retrieval = RetrievalService()
        self.prompt_builder = PromptBuilder()
        self.llm = OllamaClient()

    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        source_id: str | None = None,
        filename: str | None = None,
        version: int | None = None,
        sheet_name: str | None = None,
        page_no: int | None = None,
    ):
        hits = self.retrieval.search(
            query=question,
            top_k=top_k,
            source_id=source_id,
            filename=filename,
            version=version,
            sheet_name=sheet_name,
            page_no=page_no,
        )

        if not hits:
            answer = "I do not have enough grounded context."
            insert_chat_log({
                "query": question,
                "retrieved_chunk_ids": [],
                "final_answer": answer,
                "timestamp": datetime.utcnow().isoformat(),
            })
            return {
                "answer": answer,
                "citations": [],
                "retrieved_chunk_ids": [],
            }

        contexts = []
        citation_items = []
        retrieved_chunk_ids = []

        for hit in hits[:3]:
            entity = hit["entity"]
            metadata = entity.get("metadata", {})
            chunk_id = entity.get("chunk_id")
            score = float(hit["distance"])

            retrieved_chunk_ids.append(chunk_id)

            chunk_text = metadata.get("text", "") or entity.get("text", "")
            chunk_text = chunk_text[:1800]

            contexts.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "filename": entity.get("filename"),
                    "page_no": entity.get("page_no"),
                    "sheet_name": entity.get("sheet_name"),
                    "section_type": entity.get("section_type"),
                    "version": entity.get("version"),
                },
                "score": score,
            })

            citation_items.append({
                "chunk_id": chunk_id,
                "filename": entity.get("filename"),
                "page_no": entity.get("page_no"),
                "sheet_name": entity.get("sheet_name"),
                "section_type": entity.get("section_type"),
                "version": entity.get("version"),
                "score": score,
            })

        prompt = self.prompt_builder.build_grounded_prompt(question, contexts)

        answer = self.llm.generate_answer(
            prompt=prompt,
            system_prompt="Answer only from the provided context.",
            temperature=0.1,
            max_tokens=250,
        )

        insert_chat_log({
            "query": question,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "final_answer": answer,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            "answer": answer,
            "citations": citation_items,
            "retrieved_chunk_ids": retrieved_chunk_ids,
        }
