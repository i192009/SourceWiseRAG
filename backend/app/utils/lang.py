def detect_language_hint(text: str) -> str:
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return "zh"
    return "en"
