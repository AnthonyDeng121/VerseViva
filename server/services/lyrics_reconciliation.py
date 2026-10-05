import re

from server.models.song import SongSentence, WordTiming

WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


def reconcile_provided_lyrics(
    provided_lyrics: str,
    aligned_sentences: list[SongSentence],
) -> tuple[list[SongSentence], bool]:
    """Reuse WhisperX timings when provided lyric words match after punctuation cleanup."""

    lines = [line.strip() for line in provided_lyrics.splitlines() if line.strip()]
    line_tokens = [WORD_PATTERN.findall(line) for line in lines]
    if not lines or any(not tokens for tokens in line_tokens):
        return aligned_sentences, False

    aligned_words = [word for sentence in aligned_sentences for word in sentence.words]
    provided_words = [token for tokens in line_tokens for token in tokens]
    provided_normalized = [_normalize(word) for word in provided_words]
    aligned_normalized = [_normalize(word.text) for word in aligned_words]
    match_start = _find_contiguous_subsequence(provided_normalized, aligned_normalized)
    if match_start is None:
        return aligned_sentences, False

    matched_indexes = set(range(match_start, match_start + len(aligned_words)))
    reconciled: list[SongSentence] = []
    provided_cursor = 0
    aligned_cursor = 0
    for line_index, (line, tokens) in enumerate(zip(lines, line_tokens, strict=True), start=1):
        selected = [
            (token, provided_index)
            for token_offset, token in enumerate(tokens)
            if (provided_index := provided_cursor + token_offset) in matched_indexes
        ]
        provided_cursor += len(tokens)
        if not selected:
            continue
        timed_words = aligned_words[aligned_cursor : aligned_cursor + len(selected)]
        aligned_cursor += len(selected)
        selected_tokens = [token for token, _ in selected]
        words = [
            WordTiming(
                id=f"word_{line_index:03d}_{word_index:03d}",
                text=token,
                start_seconds=timed.start_seconds,
                end_seconds=timed.end_seconds,
                confidence=timed.confidence,
            )
            for word_index, (token, timed) in enumerate(
                zip(selected_tokens, timed_words, strict=True), start=1
            )
        ]
        whole_line_selected = len(selected_tokens) == len(tokens)
        reconciled.append(
            SongSentence(
                id=f"sentence_{line_index:03d}",
                start_seconds=words[0].start_seconds,
                end_seconds=words[-1].end_seconds,
                lyrics=line if whole_line_selected else " ".join(selected_tokens),
                words=words,
            )
        )
    return reconciled, True


def _normalize(word: str) -> str:
    return word.lower().replace("’", "").replace("'", "")


def _find_contiguous_subsequence(haystack: list[str], needle: list[str]) -> int | None:
    if not needle or len(needle) > len(haystack):
        return None
    width = len(needle)
    for start in range(len(haystack) - width + 1):
        if haystack[start : start + width] == needle:
            return start
    return None
