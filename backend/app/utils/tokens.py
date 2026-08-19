def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))
