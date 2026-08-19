import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    def generate_answer(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 250,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Ollama generate failed: status={response.status_code}, body={response.text}"
                )

            data = response.json()

        answer = (data.get("response") or "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty response.")
        return answer
