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
    if [_normalize(word) for word in provided_words] != [
        _normalize(word.text) for word in aligned_words
    ]:
        return aligned_sentences, False

    reconciled: list[SongSentence] = []
    cursor = 0
    for line_index, (line, tokens) in enumerate(zip(lines, line_tokens, strict=True), start=1):
        timed_words = aligned_words[cursor : cursor + len(tokens)]
        cursor += len(tokens)
        words = [
            WordTiming(
                id=f"word_{line_index:03d}_{word_index:03d}",
                text=token,
                start_seconds=timed.start_seconds,
                end_seconds=timed.end_seconds,
                confidence=timed.confidence,
            )
            for word_index, (token, timed) in enumerate(
                zip(tokens, timed_words, strict=True), start=1
            )
        ]
        reconciled.append(
            SongSentence(
                id=f"sentence_{line_index:03d}",
                start_seconds=words[0].start_seconds,
                end_seconds=words[-1].end_seconds,
                lyrics=line,
                words=words,
            )
        )
    return reconciled, True


def _normalize(word: str) -> str:
    return word.lower().replace("’", "").replace("'", "")
