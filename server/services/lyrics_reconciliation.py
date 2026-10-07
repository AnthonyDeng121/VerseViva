import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from server.models.song import SongSentence, WordTiming

WORD_PATTERN = re.compile(
    r"[A-Za-z]+(?:['’][A-Za-z]+)*|[\uac00-\ud7a3]+|[\u3040-\u30ff\u3400-\u9fff]"
)
PARENTHETICAL = re.compile(r"\([^()]*\)")
MIN_FUZZY_SCORE = 0.68
MIN_ASR_COVERAGE = 0.60
LRC_LINE = re.compile(r"^\[(\d{2}):(\d{2}(?:\.\d+)?)\]\s*(.*)$")


@dataclass(frozen=True, slots=True)
class _LyricsToken:
    text: str
    line_index: int


def reconcile_provided_lyrics(
    provided_lyrics: str,
    aligned_sentences: list[SongSentence],
) -> tuple[list[SongSentence], bool]:
    """Use online lyrics as text truth and WhisperX only as timing evidence."""

    lines = [line.strip() for line in provided_lyrics.splitlines() if line.strip()]
    line_tokens = [_tokenize(line) for line in lines]
    if not lines or any(not tokens for tokens in line_tokens):
        return aligned_sentences, False

    aligned_words = _expand_japanese_words(
        [word for sentence in aligned_sentences for word in sentence.words], provided_lyrics
    )
    if not aligned_words:
        return aligned_sentences, False

    lyrics_tokens = [
        _LyricsToken(text=token, line_index=line_index)
        for line_index, tokens in enumerate(line_tokens)
        for token in tokens
    ]
    # Overlapping response/ad-lib text is provider truth, but a single WhisperX
    # transcript often follows only the dominant lead. Ignore parentheses only
    # while locating the excerpt; restore every token from the matched lines.
    matching_tokens = [
        _LyricsToken(text=token, line_index=line_index)
        for line_index, line in enumerate(lines)
        for token in _tokenize(PARENTHETICAL.sub("", line))
    ]
    match = _find_best_window(
        [_normalize(token.text) for token in matching_tokens],
        [_normalize(word.text) for word in aligned_words],
    )
    if match is None:
        return aligned_sentences, False

    match_start, match_end = match
    first_line = matching_tokens[match_start].line_index
    last_line = matching_tokens[match_end - 1].line_index
    selected_tokens = [
        token for token in lyrics_tokens if first_line <= token.line_index <= last_line
    ]
    timed_words = _transfer_timings(selected_tokens, aligned_words)
    reconciled = _build_sentences(lines, line_tokens, selected_tokens, timed_words)
    return (reconciled, True) if reconciled else (aligned_sentences, False)


def reconcile_synced_lyrics_excerpt(
    synced_lyrics: str,
    aligned_sentences: list[SongSentence],
) -> tuple[list[SongSentence], bool]:
    """Recover a short excerpt when ASR is too inaccurate for plain-text matching.

    LRCLIB timestamps are used only to choose a similarly-sized contiguous lyric
    window. WhisperX remains the source of timings in the uploaded excerpt.
    """
    parsed: list[tuple[float, str]] = []
    for raw_line in synced_lyrics.splitlines():
        match = LRC_LINE.match(raw_line.strip())
        if match and match.group(3).strip():
            parsed.append(
                (int(match.group(1)) * 60 + float(match.group(2)), match.group(3).strip())
            )
    aligned_words = _expand_japanese_words(
        [word for sentence in aligned_sentences for word in sentence.words], synced_lyrics
    )
    if len(parsed) < 2 or len(aligned_words) < 3:
        return aligned_sentences, False

    duration = aligned_words[-1].end_seconds - aligned_words[0].start_seconds
    asr_tokens = [_normalize(word.text) for word in aligned_words]
    asr_set = set(asr_tokens)
    best: tuple[float, int, int] | None = None
    for start in range(len(parsed)):
        for end in range(start + 1, len(parsed) + 1):
            window_end = parsed[end][0] if end < len(parsed) else parsed[-1][0] + 4.0
            window_duration = window_end - parsed[start][0]
            if window_duration < max(2.0, duration - 3.0):
                continue
            if window_duration > duration + 3.0:
                break
            text = "\n".join(line for _, line in parsed[start:end])
            candidate = [
                _normalize(token)
                for token in _tokenize(PARENTHETICAL.sub("", text))
            ]
            if not candidate:
                continue
            sequence = SequenceMatcher(None, candidate, asr_tokens, autojunk=False).ratio()
            overlap = len(asr_set.intersection(candidate)) / max(1, len(asr_set))
            duration_score = max(0.0, 1.0 - abs(window_duration - duration) / 3.0)
            score = sequence * 0.45 + overlap * 0.35 + duration_score * 0.20
            if best is None or score > best[0]:
                best = (score, start, end)
    if best is None or best[0] < 0.28:
        return aligned_sentences, False
    excerpt = "\n".join(line for _, line in parsed[best[1] : best[2]])
    return _reconcile_selected_lines(excerpt, aligned_sentences)


def _reconcile_selected_lines(
    lyrics: str, aligned_sentences: list[SongSentence]
) -> tuple[list[SongSentence], bool]:
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    line_tokens = [_tokenize(line) for line in lines]
    aligned_words = _expand_japanese_words(
        [word for sentence in aligned_sentences for word in sentence.words], lyrics
    )
    if not lines or any(not tokens for tokens in line_tokens) or not aligned_words:
        return aligned_sentences, False
    selected = [_LyricsToken(token, line_index) for line_index, tokens in enumerate(line_tokens)
                for token in tokens]
    timed = _transfer_timings(selected, aligned_words)
    result = _build_sentences(lines, line_tokens, selected, timed)
    return (result, True) if result else (aligned_sentences, False)


def _find_best_window(haystack: list[str], needle: list[str]) -> tuple[int, int] | None:
    if not needle or not haystack:
        return None
    exact_start = _find_contiguous_subsequence(haystack, needle)
    if exact_start is not None:
        return exact_start, exact_start + len(needle)
    if len(needle) < 3:
        return None

    minimum_width = max(2, round(len(needle) * 0.70))
    maximum_width = min(len(haystack), round(len(needle) * 1.30) + 2)
    best_ranking: tuple[float, float, int, int] | None = None
    best_window: tuple[int, int] | None = None
    for width in range(minimum_width, maximum_width + 1):
        for start in range(len(haystack) - width + 1):
            candidate = haystack[start : start + width]
            matcher = SequenceMatcher(None, candidate, needle, autojunk=False)
            score = matcher.ratio()
            matched_count = sum(block.size for block in matcher.get_matching_blocks())
            coverage = matched_count / len(needle)
            ranking = (score, coverage, -abs(width - len(needle)), -start)
            if best_ranking is None or ranking > best_ranking:
                best_ranking = ranking
                best_window = (start, start + width)
    if (
        best_ranking is None
        or best_ranking[0] < MIN_FUZZY_SCORE
        or best_ranking[1] < MIN_ASR_COVERAGE
    ):
        return None
    return best_window


def _transfer_timings(
    lyrics_tokens: list[_LyricsToken], aligned_words: list[WordTiming]
) -> list[WordTiming]:
    matcher = SequenceMatcher(
        None,
        [_normalize(token.text) for token in lyrics_tokens],
        [_normalize(word.text) for word in aligned_words],
        autojunk=False,
    )
    result: list[WordTiming | None] = [None] * len(lyrics_tokens)
    for tag, lyric_start, lyric_end, asr_start, asr_end in matcher.get_opcodes():
        if tag == "equal":
            for lyric_index, asr_index in zip(
                range(lyric_start, lyric_end), range(asr_start, asr_end), strict=True
            ):
                source = aligned_words[asr_index]
                result[lyric_index] = WordTiming(
                    id="pending",
                    text=lyrics_tokens[lyric_index].text,
                    start_seconds=source.start_seconds,
                    end_seconds=source.end_seconds,
                    confidence=source.confidence,
                )
        elif tag == "replace":
            start, end = _asr_span(aligned_words, asr_start, asr_end)
            _fill_evenly(result, lyrics_tokens, lyric_start, lyric_end, start, end)
        elif tag == "delete":
            start, end = _neighbor_span(result, aligned_words, lyric_start, asr_start)
            _fill_evenly(result, lyrics_tokens, lyric_start, lyric_end, start, end)

    fallback_start = aligned_words[0].start_seconds
    fallback_end = aligned_words[-1].end_seconds
    for index, value in enumerate(result):
        if value is None:
            _fill_evenly(result, lyrics_tokens, index, index + 1, fallback_start, fallback_end)
    return [word for word in result if word is not None]


def _asr_span(words: list[WordTiming], start: int, end: int) -> tuple[float, float]:
    if start < end:
        return words[start].start_seconds, words[end - 1].end_seconds
    point = words[min(start, len(words) - 1)].start_seconds
    return point, point


def _neighbor_span(
    result: list[WordTiming | None],
    aligned_words: list[WordTiming],
    lyric_start: int,
    asr_index: int,
) -> tuple[float, float]:
    previous = next((word for word in reversed(result[:lyric_start]) if word), None)
    start = previous.end_seconds if previous else aligned_words[0].start_seconds
    end = (
        aligned_words[asr_index].start_seconds
        if asr_index < len(aligned_words)
        else aligned_words[-1].end_seconds
    )
    return start, max(start, end)


def _fill_evenly(
    result: list[WordTiming | None],
    tokens: list[_LyricsToken],
    start_index: int,
    end_index: int,
    start_seconds: float,
    end_seconds: float,
) -> None:
    count = end_index - start_index
    if count <= 0:
        return
    step = max(0.0, end_seconds - start_seconds) / count
    for offset, index in enumerate(range(start_index, end_index)):
        result[index] = WordTiming(
            id="pending",
            text=tokens[index].text,
            start_seconds=start_seconds + step * offset,
            end_seconds=start_seconds + step * (offset + 1),
            confidence=None,
        )


def _build_sentences(
    lines: list[str],
    line_tokens: list[list[str]],
    selected_tokens: list[_LyricsToken],
    timed_words: list[WordTiming],
) -> list[SongSentence]:
    sentences: list[SongSentence] = []
    line_indexes = dict.fromkeys(token.line_index for token in selected_tokens)
    for output_index, line_index in enumerate(line_indexes, start=1):
        indexes = [
            index for index, token in enumerate(selected_tokens) if token.line_index == line_index
        ]
        words = [
            timed_words[index].model_copy(
                update={"id": f"word_{output_index:03d}_{word_index:03d}"}
            )
            for word_index, index in enumerate(indexes, start=1)
        ]
        selected_text = [selected_tokens[index].text for index in indexes]
        whole_line = len(selected_text) == len(line_tokens[line_index])
        sentences.append(
            SongSentence(
                id=f"sentence_{output_index:03d}",
                start_seconds=words[0].start_seconds,
                end_seconds=words[-1].end_seconds,
                lyrics=lines[line_index] if whole_line else " ".join(selected_text),
                words=words,
            )
        )
    return sentences


def _normalize(word: str) -> str:
    return word.lower().replace("’", "").replace("'", "")


def _tokenize(value: str) -> list[str]:
    return WORD_PATTERN.findall(value)


def _expand_japanese_words(words: list[WordTiming], lyrics: str) -> list[WordTiming]:
    if not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", lyrics):
        return words
    expanded: list[WordTiming] = []
    for word in words:
        units = re.findall(r"[\u3040-\u30ff\u3400-\u9fff]|[A-Za-z]+", word.text)
        if len(units) <= 1:
            expanded.append(word)
            continue
        width = (word.end_seconds - word.start_seconds) / len(units)
        for index, unit in enumerate(units):
            expanded.append(
                word.model_copy(
                    update={
                        "id": f"{word.id}_{index}",
                        "text": unit,
                        "start_seconds": word.start_seconds + width * index,
                        "end_seconds": word.start_seconds + width * (index + 1),
                    }
                )
            )
    return expanded


def _find_contiguous_subsequence(haystack: list[str], needle: list[str]) -> int | None:
    if not needle or len(needle) > len(haystack):
        return None
    width = len(needle)
    for start in range(len(haystack) - width + 1):
        if haystack[start : start + width] == needle:
            return start
    return None
