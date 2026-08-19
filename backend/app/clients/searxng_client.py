import httpx

from backend.app.core.settings import SEARXNG_BASE_URL, SEARXNG_TIMEOUT


class SearXNGClient:
    def __init__(self, base_url: str = SEARXNG_BASE_URL, timeout: float = SEARXNG_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def search(self, query: str, limit: int = 5):
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "language": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", [])[:limit]:
            results.append({
                "title": item.get("title") or "Untitled",
                "url": item.get("url") or "",
                "snippet": item.get("content") or item.get("snippet") or "",
                "source_engine": "searxng",
            })
        return results
