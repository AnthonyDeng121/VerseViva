import re
from functools import lru_cache
from typing import Protocol

from server.models.song import SongSentence
from server.services.language.models import BoundaryKind, LanguageCandidate

VOWEL_PHONEMES = {
    "AA",
    "AE",
    "AH",
    "AO",
    "AW",
    "AY",
    "EH",
    "ER",
    "EY",
    "IH",
    "IY",
    "OW",
    "OY",
    "UH",
    "UW",
}
GLIDE_PHONEMES = {"W", "Y"}
STOP_PHONEMES = {"P", "B", "T", "D", "K", "G"}
WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


class PronunciationLexicon(Protocol):
    def phonemes(self, word: str) -> list[str]: ...


class CmuPronunciationLexicon:
    def __init__(self) -> None:
        self._entries = _load_cmudict()

    def phonemes(self, word: str) -> list[str]:
        normalized = _normalize_word(word)
        pronunciations = self._entries.get(normalized)
        if pronunciations:
            return [_remove_stress(phoneme) for phoneme in pronunciations[0]]
        return _fallback_phonemes(normalized)


@lru_cache(maxsize=1)
def _load_cmudict() -> dict[str, list[list[str]]]:
    try:
        import cmudict
    except ImportError:
        return {}
    return cmudict.dict()


def generate_language_candidates(
    sentences: list[SongSentence],
    lexicon: PronunciationLexicon | None = None,
    language: str | None = None,
) -> list[LanguageCandidate]:
    normalized_language = (language or "").lower().split("-")[0]
    if normalized_language == "ko":
        return _generate_korean_candidates(sentences)
    if normalized_language == "ja":
        return _generate_japanese_candidates(sentences)
    lexicon = lexicon or CmuPronunciationLexicon()
    candidates: list[LanguageCandidate] = []
    for line_index, sentence in enumerate(sentences):
        spans = _word_character_spans(sentence)
        for word_index, (left, right) in enumerate(
            zip(sentence.words, sentence.words[1:], strict=False)
        ):
            left_phonemes = lexicon.phonemes(left.text)
            right_phonemes = lexicon.phonemes(right.text)
            if not left_phonemes or not right_phonemes:
                continue
            left_segment = left_phonemes[-1]
            right_segment = right_phonemes[0]
            left_span = spans[word_index]
            right_span = spans[word_index + 1]
            if _parenthetical_lane(sentence.lyrics, left_span[0]) != _parenthetical_lane(
                sentence.lyrics, right_span[0]
            ):
                continue
            candidates.append(
                LanguageCandidate(
                    id=f"candidate_{line_index:03d}_{word_index:03d}",
                    sentence_id=sentence.id,
                    line_index=line_index,
                    start_word_index=word_index,
                    end_word_index=word_index + 1,
                    target_span=f"{left.text} {right.text}",
                    left_word=left.text,
                    right_word=right.text,
                    left_segment=left_segment,
                    right_segment=right_segment,
                    boundary_kind=_classify_boundary(left_segment, right_segment),
                    start_seconds=left.start_seconds,
                    end_seconds=right.end_seconds,
                    left_end_char_index=left_span[1],
                    right_start_char_index=right_span[0],
                )
            )
    return candidates


def _generate_korean_candidates(sentences: list[SongSentence]) -> list[LanguageCandidate]:
    candidates: list[LanguageCandidate] = []
    for line_index, sentence in enumerate(sentences):
        if not sentence.pronunciation or not sentence.words:
            continue
        original_words = re.findall(r"[\uac00-\ud7a3]", sentence.lyrics)
        roman_words = [_romanize_hangul_unit(char) for char in original_words]
        count = len(original_words)
        if count < 2:
            continue
        roman_cursor = 0
        spans: list[tuple[int, int]] = []
        for word in roman_words:
            start = sentence.pronunciation.text.find(word, roman_cursor)
            spans.append((start, start + len(word) - 1))
            roman_cursor = start + len(word)
        for index in range(count - 1):
            left_char = original_words[index][-1]
            right_char = original_words[index + 1][0]
            left_final = (ord(left_char) - 0xAC00) % 28
            right_initial = (ord(right_char) - 0xAC00) // 588
            if left_final == 0:
                continue
            left_roman = roman_words[index]
            right_roman = roman_words[index + 1]
            if right_initial == 11:  # silent ㅇ before a vowel: 받침 carries over
                phenomenon = "liaison"
                boundary = BoundaryKind.consonant_to_vowel
                output = _korean_liaison_display(left_roman, right_roman)
                action = "不要在前一个词后停顿，把词尾辅音直接带到后一个元音。"
            elif left_final in {1, 2, 3, 7, 19, 20, 22, 23, 24, 25, 27}:
                phenomenon = "final_stop_unreleased"
                boundary = BoundaryKind.stop_before_consonant
                output = f"{left_roman} {right_roman}"
                action = "完成前一个词的收尾位置，但不要把尾音单独弹出来，直接进入后词。"
            else:
                continue
            start_seconds, end_seconds = _candidate_time(sentence, index, count)
            candidates.append(
                LanguageCandidate(
                    id=f"candidate_{line_index:03d}_{index:03d}",
                    sentence_id=sentence.id,
                    line_index=line_index,
                    start_word_index=min(index, len(sentence.words) - 1),
                    end_word_index=min(index + 1, len(sentence.words) - 1),
                    target_span=f"{left_roman} {right_roman}",
                    left_word=left_roman,
                    right_word=right_roman,
                    left_segment=left_roman[-1],
                    right_segment=right_roman[0],
                    boundary_kind=boundary,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    left_end_char_index=spans[index][1],
                    right_start_char_index=spans[index + 1][0],
                    language="ko",
                    phenomenon=phenomenon,
                    canonical_pronunciation=f"{left_roman} {right_roman}",
                    observed_pronunciation=output,
                    learner_action=action,
                )
            )
    return candidates


def _generate_japanese_candidates(sentences: list[SongSentence]) -> list[LanguageCandidate]:
    candidates: list[LanguageCandidate] = []
    for line_index, sentence in enumerate(sentences):
        if not sentence.pronunciation or not sentence.words:
            continue
        roman = sentence.pronunciation.text
        words = roman.split()
        cursor = 0
        spans: list[tuple[int, int]] = []
        for word in words:
            start = roman.find(word, cursor)
            spans.append((start, start + len(word) - 1))
            cursor = start + len(word)
        for index, (left, right) in enumerate(zip(words, words[1:], strict=False)):
            if not left.endswith("n") or not right:
                continue
            first = right[0].lower()
            if first in "bmp":
                heard = f"{left[:-1]}m {right}"
                action = "不要单独读一个“恩”；闭住嘴唇保持鼻音，再进入后面的辅音。"
            elif first in "kg":
                heard = f"{left[:-1]}ng {right}"
                action = "不要单独读一个“恩”；把鼻音位置放到口腔后部，再进入后面的辅音。"
            else:
                continue
            start_seconds, end_seconds = _candidate_time(sentence, index, len(words))
            candidates.append(
                LanguageCandidate(
                    id=f"candidate_{line_index:03d}_{index:03d}",
                    sentence_id=sentence.id,
                    line_index=line_index,
                    start_word_index=min(index, len(sentence.words) - 1),
                    end_word_index=min(index + 1, len(sentence.words) - 1),
                    target_span=f"{left} {right}",
                    left_word=left,
                    right_word=right,
                    left_segment="n",
                    right_segment=first,
                    boundary_kind=BoundaryKind.other_boundary,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    left_end_char_index=spans[index][1],
                    right_start_char_index=spans[index + 1][0],
                    language="ja",
                    phenomenon="moraic_nasal_assimilation",
                    canonical_pronunciation=f"{left} {right}",
                    observed_pronunciation=heard,
                    learner_action=action,
                )
            )
    return candidates


def _candidate_time(sentence: SongSentence, index: int, unit_count: int) -> tuple[float, float]:
    if len(sentence.words) >= unit_count:
        left = sentence.words[min(index, len(sentence.words) - 1)]
        right = sentence.words[min(index + 1, len(sentence.words) - 1)]
        return left.start_seconds, right.end_seconds
    width = (sentence.end_seconds - sentence.start_seconds) / max(1, unit_count)
    return sentence.start_seconds + width * index, sentence.start_seconds + width * (index + 2)


def _korean_liaison_display(left: str, right: str) -> str:
    endings = ("ng", "ch", "kk", "ks", "nj", "nh", "lk", "lm", "lb", "ls", "lt", "lp", "lh", "ps")
    final = next((ending for ending in endings if left.endswith(ending)), left[-1:])
    return f"{left[:-len(final)]} {final}{right}"


def _romanize_hangul_unit(char: str) -> str:
    from server.services.language.pronunciation import romanize_korean

    return romanize_korean(char)


def _parenthetical_lane(lyrics: str, char_index: int) -> str:
    for match in re.finditer(r"\([^)]*\)", lyrics):
        if match.start() <= char_index < match.end():
            return "secondary"
    return "primary"


def _word_character_spans(sentence: SongSentence) -> list[tuple[int, int]]:
    matches = list(WORD_PATTERN.finditer(sentence.lyrics))
    spans: list[tuple[int, int]] = []
    cursor = 0
    for index, word in enumerate(sentence.words):
        normalized_word = _normalize_word(word.text)
        matched = next(
            (
                match
                for match in matches[cursor:]
                if _normalize_word(match.group()) == normalized_word
            ),
            None,
        )
        if matched is None:
            fallback_start = min(
                len(sentence.lyrics) - 1,
                spans[-1][1] + 1 if spans else 0,
            )
            fallback_end = min(
                len(sentence.lyrics) - 1,
                fallback_start + max(len(word.text.strip()) - 1, 0),
            )
            spans.append((fallback_start, fallback_end))
            continue
        match_index = matches.index(matched)
        cursor = match_index + 1
        spans.append((matched.start(), matched.end() - 1))
        if index + 1 == len(sentence.words):
            break
    return spans


def _classify_boundary(left: str, right: str) -> BoundaryKind:
    if left == right and left not in VOWEL_PHONEMES:
        return BoundaryKind.identical_consonants
    if left in {"T", "D"} and right == "Y":
        return BoundaryKind.stop_to_glide
    if left == "ER" and right in VOWEL_PHONEMES:
        return BoundaryKind.rhotic_to_vowel
    if left not in VOWEL_PHONEMES and right in VOWEL_PHONEMES:
        return BoundaryKind.consonant_to_vowel
    if left not in VOWEL_PHONEMES and right in GLIDE_PHONEMES:
        return BoundaryKind.consonant_to_glide
    if left in VOWEL_PHONEMES and right in VOWEL_PHONEMES:
        return BoundaryKind.vowel_to_vowel
    if left in STOP_PHONEMES and right not in VOWEL_PHONEMES:
        return BoundaryKind.stop_before_consonant
    return BoundaryKind.other_boundary


def _normalize_word(word: str) -> str:
    normalized = word.strip().lower().replace("’", "'")
    match = WORD_PATTERN.search(normalized)
    return match.group() if match else normalized


def _remove_stress(phoneme: str) -> str:
    return phoneme.rstrip("012")


def _fallback_phonemes(word: str) -> list[str]:
    contraction_endings = {
        "'re": "R",
        "'ll": "L",
        "'ve": "V",
        "'d": "D",
        "'m": "M",
    }
    final = next(
        (phoneme for suffix, phoneme in contraction_endings.items() if word.endswith(suffix)),
        _letter_to_phoneme(word[-1:] or "?"),
    )
    initial = _letter_to_phoneme(word[:1] or "?")
    return [initial, final] if initial != final else [initial]


def _letter_to_phoneme(letter: str) -> str:
    upper = letter.upper()
    if upper in {"A", "E", "I", "O", "U"}:
        return "AH"
    if upper == "Y":
        return "Y"
    return upper or "?"
