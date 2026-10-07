import re
import unicodedata

from server.models.song import PronunciationGuide, SongSentence

HANGUL_BASE = 0xAC00
HANGUL_END = 0xD7A3
INITIALS = (
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j",
    "jj", "ch", "k", "t", "p", "h",
)
VOWELS = (
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae",
    "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
)
FINALS = (
    "", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lk", "lm", "lb", "ls",
    "lt", "lp", "lh", "m", "p", "ps", "t", "t", "ng", "t", "t", "k", "t",
    "p", "h",
)
HANGUL_WORD = re.compile(r"[\uac00-\ud7a3]+")
JAPANESE_TEXT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def add_pronunciation_guides(
    sentences: list[SongSentence], language: str | None
) -> list[SongSentence]:
    normalized = (language or "").lower().split("-")[0]
    if normalized not in {"ko", "ja"}:
        return sentences
    converted: list[SongSentence] = []
    for sentence in sentences:
        text = romanize_korean(sentence.lyrics) if normalized == "ko" else romanize_japanese(
            sentence.lyrics
        )
        if not text.strip():
            converted.append(sentence)
            continue
        converted.append(
            sentence.model_copy(
                update={
                    "pronunciation": PronunciationGuide(
                        text=text,
                        scheme="revised_romanization" if normalized == "ko" else "hepburn",
                        source="generated",
                    )
                }
            )
        )
    return converted


def romanize_korean(text: str) -> str:
    chunks: list[str] = []
    tokens = re.findall(r"[\uac00-\ud7a3]+|[A-Za-z]+(?:['’][A-Za-z]+)*|\s+|.", text)
    for token in tokens:
        if HANGUL_WORD.fullmatch(token):
            chunks.append(" ".join(_romanize_syllable(char) for char in token))
        else:
            chunks.append(token)
    return _normalize_spacing("".join(chunks))


def romanize_japanese(text: str) -> str:
    if not JAPANESE_TEXT.search(text):
        return text
    try:
        from pykakasi import kakasi
    except ImportError:
        return text
    converter = kakasi()
    # Mark explicitly written particles at phrase boundaries before conversion.
    # This affects the learner guide only; the source lyric remains untouched.
    reading_text = re.sub(r"は(?=\s|[、。！？!?]|$)", "ワ", text)
    reading_text = re.sub(r"へ(?=\s|[、。！？!?]|$)", "エ", reading_text)
    reading_text = reading_text.replace("を", "オ")
    hira = "".join(
        item["hira"] if JAPANESE_TEXT.search(item["orig"]) else item["orig"]
        for item in converter.convert(reading_text)
    )
    morae: list[str] = []
    index = 0
    small = "ゃゅょぁぃぅぇぉゎ"
    while index < len(hira):
        char = hira[index]
        if char.isspace():
            index += 1
            continue
        unit = char
        if unit == "ー" and morae:
            vowel = next(
                (letter for letter in reversed(morae[-1]) if letter in "aeiou"),
                "",
            )
            if vowel:
                morae[-1] += vowel
            index += 1
            continue
        if char == "っ" and index + 1 < len(hira):
            index += 1
            unit += hira[index]
        if index + 1 < len(hira) and hira[index + 1] in small:
            index += 1
            unit += hira[index]
        converted = converter.convert(unit)
        morae.append(converted[0]["hepburn"] if converted else unit)
        index += 1
    return _normalize_spacing(" ".join(morae))


def _romanize_syllable(char: str) -> str:
    code = ord(char)
    if not HANGUL_BASE <= code <= HANGUL_END:
        return char
    offset = code - HANGUL_BASE
    initial = offset // 588
    vowel = (offset % 588) // 28
    final = offset % 28
    return f"{INITIALS[initial]}{VOWELS[vowel]}{FINALS[final]}"


def _normalize_spacing(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", value)
