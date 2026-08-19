from typing import List


class PromptBuilder:
    def build_grounded_prompt(self, question: str, contexts: List[dict]) -> str:
        formatted_contexts = []

        for idx, item in enumerate(contexts, start=1):
            meta = item["metadata"]
            citation = self._format_citation(meta)
            text = item["text"][:1800]

            formatted_contexts.append(
                f"[Source {idx}] {citation}\n{text}"
            )

        context_block = "\n\n".join(formatted_contexts)

        return f"""
You are answering a question using only the provided context.

Rules:
1. Answer only from the retrieved context.
2. Cite supporting evidence using filename + page number or sheet name.
3. If the retrieved context contains conflicting evidence, say that clearly.
4. If the retrieved context is insufficient, say exactly: "I do not have enough grounded context."
5. Never invent sources or facts not present in the context.
6. Keep the answer concise.

User question:
{question}

Retrieved context:
{context_block}

Return format:
Answer:
<your answer>

Sources:
<filename + page/sheet citations only>
""".strip()

    def _format_citation(self, meta: dict) -> str:
        filename = meta.get("filename", "unknown")
        page_no = meta.get("page_no")
        sheet_name = meta.get("sheet_name")

        if page_no:
            return f"{filename}, page {page_no}"
        if sheet_name:
            return f"{filename}, sheet {sheet_name}"
        return filename
