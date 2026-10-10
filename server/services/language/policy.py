def supports_language_coaching(language: str | None) -> bool:
    """Return whether a song should enter language and practice coaching."""
    return (language or "").lower().split("-")[0] != "zh"
