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
) -> list[LanguageCandidate]:
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
