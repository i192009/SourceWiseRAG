from backend.app.clients.ollama_client import OllamaClient
from backend.app.clients.searxng_client import SearXNGClient
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.qa_service import QAService


class ChatFallbackService:
    def __init__(self):
        self.qa = QAService()
        self.search_client = SearXNGClient()
        self.prompt_builder = PromptBuilder()
        self.llm = OllamaClient()

    def _should_use_web_fallback(self, qa_result: dict) -> bool:
        answer = (qa_result.get("answer") or "").lower()
        citations = qa_result.get("citations") or []

        if not citations:
            return True

        weak_markers = [
            "i do not have enough grounded context",
            "the provided context does not contain information",
            "there is no information",
            "insufficient",
        ]
        return any(marker in answer for marker in weak_markers)

    def _build_web_prompt(self, question: str, web_results: list[dict]) -> str:
        context_lines = []
        for idx, item in enumerate(web_results, start=1):
            context_lines.append(
                f"[Web Source {idx}] {item['title']}\nURL: {item['url']}\nSnippet: {item['snippet']}"
            )

        return f"""
You are answering using only the provided web search snippets.

Rules:
1. Use only the given snippets.
2. If they are insufficient, say that clearly.
3. Do not invent facts.
4. Keep the answer concise.

Question:
{question}

Web results:
{"\n\n".join(context_lines)}

Return format:
Answer:
<your answer>
""".strip()

    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        source_id: str | None = None,
        filename: str | None = None,
        version: int | None = None,
        sheet_name: str | None = None,
        page_no: int | None = None,
        allow_web_fallback: bool = True,
        web_result_limit: int = 5,
    ):
        qa_result = self.qa.answer_question(
            question=question,
            top_k=top_k,
            source_id=source_id,
            filename=filename,
            version=version,
            sheet_name=sheet_name,
            page_no=page_no,
        )

        if not allow_web_fallback or not self._should_use_web_fallback(qa_result):
            return {
                "answer": qa_result["answer"],
                "answer_source": "internal",
                "used_web_fallback": False,
                "citations": qa_result["citations"],
                "retrieved_chunk_ids": qa_result["retrieved_chunk_ids"],
                "web_results": [],
            }

        web_results = self.search_client.search(question, web_result_limit)

        if not web_results:
            return {
                "answer": qa_result["answer"],
                "answer_source": "internal",
                "used_web_fallback": False,
                "citations": qa_result["citations"],
                "retrieved_chunk_ids": qa_result["retrieved_chunk_ids"],
                "web_results": [],
            }

        web_prompt = self._build_web_prompt(question, web_results)
        web_answer = self.llm.generate_answer(
            prompt=web_prompt,
            system_prompt="Answer only from the provided web snippets.",
            temperature=0.1,
            max_tokens=250,
        )

        return {
            "answer": web_answer,
            "answer_source": "web",
            "used_web_fallback": True,
            "citations": [],
            "retrieved_chunk_ids": [],
            "web_results": web_results,
        }
