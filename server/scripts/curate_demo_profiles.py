import copy
import json
from pathlib import Path

from server.models.song import SongProfile

GET_HIM_BACK_ID = "song_00000000000000000000000000000003"
AS_IF_LAST_ID = "song_00000000000000000000000000000004"
JAPANESE_ZOO_ID = "song_00000000000000000000000000000005"


def _read(root: Path, song_id: str) -> dict:
    source = root / "data" / "songs" / song_id / "profile.json"
    return json.loads(source.read_text(encoding="utf-8"))


def _write(root: Path, song_id: str, payload: dict) -> None:
    validated = SongProfile.model_validate(payload)
    destination = root / "data" / "songs" / song_id / "profile.json"
    destination.write_text(
        validated.model_dump_json(by_alias=True, indent=2),
        encoding="utf-8",
    )


def _remove_mark(sentence: dict, index: int, symbol: str = "‿") -> None:
    sentence["languageHints"] = [
        hint
        for hint in sentence["languageHints"]
        if not any(
            mark["symbol"] == symbol and mark["startCharIndex"] == index
            for mark in hint["marks"]
        )
    ]


def _add_next_line_link(sentence: dict, hint_id: str, next_word: str) -> None:
    final_index = len(sentence["lyrics"]) - 1
    final_word_index = max(len(sentence["words"]) - 1, 0)
    sentence["languageHints"].append(
        {
            "id": hint_id,
            "language": "en",
            "phenomenon": "cross_word_linking",
            "transformations": [
                {
                    "operation": "resegment",
                    "inputSegments": [sentence["lyrics"][-1].lower(), next_word[0].lower()],
                    "outputSegments": [sentence["lyrics"][-1].lower(), next_word[0].lower()],
                }
            ],
            "startWordIndex": final_word_index,
            "endWordIndex": final_word_index,
            "startSeconds": sentence["endSeconds"] - 0.2,
            "endSeconds": sentence["endSeconds"],
            "source": "human_curated",
            "confidence": 1.0,
            "marks": [
                {
                    "symbol": "‿",
                    "startCharIndex": final_index,
                    "endCharIndex": final_index,
                    "placement": "below",
                }
            ],
            "details": [
                {
                    "locale": "zh-CN",
                    "explanation": (
                        f"主轨跨句演唱时，词尾与下一句 {next_word} 的起音连续衔接。"
                    ),
                    "action": f"建议：不要在句末停顿，直接进入下一句 {next_word}。",
                }
            ],
            "evidence": {
                "provider": "human",
                "result": "curated_cross_sentence_link",
                "evidenceStrength": "strong",
                "needsHumanReview": False,
            },
        }
    )


def curate_get_him_back(root: Path) -> None:
    payload = _read(root, GET_HIM_BACK_ID)
    by_id = {sentence["id"]: sentence for sentence in payload["sentences"]}
    curated_ids = {"hint_human_up_wanna", "hint_human_sucks_oh", "hint_human_mom_and"}
    for sentence in payload["sentences"]:
        sentence["languageHints"] = [
            hint for hint in sentence["languageHints"] if hint["id"] not in curated_ids
        ]

    _remove_mark(by_id["sentence_001"], 10)
    _remove_mark(by_id["sentence_007"], 11)
    _remove_mark(by_id["sentence_013"], 25)

    _add_next_line_link(by_id["sentence_004"], "hint_human_up_wanna", "Wanna")
    _add_next_line_link(by_id["sentence_008"], "hint_human_sucks_oh", "Oh")
    _add_next_line_link(by_id["sentence_015"], "hint_human_mom_and", "And")

    sentence = by_id["sentence_011"]
    old_lyrics = sentence["lyrics"]
    if old_lyrics.startswith("I wanna"):
        sentence["lyrics"] = old_lyrics.replace("I wanna", "Don't wanna", 1)
        delta = len("Don't") - len("I")
        if sentence.get("words"):
            sentence["words"][0]["text"] = "Don't"
        for hint in sentence["languageHints"]:
            for mark in hint["marks"]:
                mark["startCharIndex"] += delta
                mark["endCharIndex"] += delta
    for part in payload["vocalParts"]:
        if part["id"] == "part_primary_011":
            part["lyrics"] = sentence["lyrics"]

    _write(root, GET_HIM_BACK_ID, payload)


def curate_as_if_last(root: Path) -> None:
    payload = _read(root, AS_IF_LAST_ID)
    payload["sentences"] = [
        sentence
        for sentence in payload["sentences"]
        if sentence["id"] not in {"sentence_001", "sentence_009"}
    ]
    last = payload["sentences"][-1]
    missing = copy.deepcopy(last)
    missing.update(
        {
            "id": "sentence_009",
            "startSeconds": last["endSeconds"],
            "endSeconds": payload["durationSeconds"],
            "lyrics": "내일 따윈 없는 것처럼, love",
            "pronunciation": {
                "text": "nae il tta win eop neun geot cheo reom, love",
                "scheme": "revised_romanization",
                "source": "human_curated",
            },
            "languageHints": [],
        }
    )
    missing["words"] = [
        {
            "id": f"word_009_{index:03d}",
            "text": word,
            "startSeconds": missing["startSeconds"],
            "endSeconds": missing["endSeconds"],
            "confidence": None,
        }
        for index, word in enumerate(["내일", "따윈", "없는", "것처럼", "love"], start=1)
    ]
    payload["sentences"].append(missing)
    payload["vocalParts"] = []
    payload["analysis"]["vocalArrangementMode"] = "single_track"
    payload["analysis"]["lyricsSource"] = "corrected"
    payload["analysis"]["lyricsProvider"] = "human-curated-demo"
    _write(root, AS_IF_LAST_ID, payload)


def _add_pronunciation_link(sentence: dict, hint_id: str, boundary: str) -> None:
    pronunciation = sentence["pronunciation"]["text"]
    start = pronunciation.index(boundary)
    left_index = start + boundary.index(" ") - 1
    words = pronunciation[: left_index + 1].split()
    word_index = max(len(words) - 1, 0)
    sentence["languageHints"].append(
        {
            "id": hint_id,
            "language": "ja",
            "phenomenon": "mora_linking",
            "transformations": [
                {
                    "operation": "resegment",
                    "inputSegments": boundary.split(),
                    "outputSegments": boundary.split(),
                }
            ],
            "startWordIndex": min(word_index, len(sentence["words"]) - 1),
            "endWordIndex": min(word_index + 1, len(sentence["words"]) - 1),
            "startSeconds": sentence["startSeconds"],
            "endSeconds": sentence["endSeconds"],
            "source": "human_curated",
            "confidence": 1.0,
            "marks": [
                {
                    "symbol": "‿",
                    "startCharIndex": left_index,
                    "endCharIndex": left_index,
                    "placement": "below",
                }
            ],
            "details": [
                {
                    "locale": "zh-CN",
                    "explanation": f"原唱在 {boundary} 处保持连续语流，没有单独停顿。",
                    "action": f"建议：把 {boundary} 放在同一口气中自然衔接。",
                }
            ],
            "canonicalPronunciation": boundary,
            "observedPronunciation": boundary.replace(" ", ""),
            "evidence": {
                "provider": "human",
                "result": "curated_link",
                "evidenceStrength": "strong",
                "needsHumanReview": False,
            },
        }
    )


def curate_japanese_zoo(root: Path) -> None:
    payload = _read(root, JAPANESE_ZOO_ID)
    by_id = {sentence["id"]: sentence for sentence in payload["sentences"]}
    for sentence in payload["sentences"]:
        sentence["languageHints"] = [
            hint
            for hint in sentence["languageHints"]
            if not hint["id"].startswith("hint_human_")
        ]
    _add_pronunciation_link(by_id["sentence_001"], "hint_human_en_wa", "n wa")
    _add_pronunciation_link(by_id["sentence_004"], "hint_human_san_tetsu", "n te")
    final = by_id["sentence_006"]
    _add_pronunciation_link(final, "hint_human_tai_he_1", "i he")
    _add_pronunciation_link(final, "hint_human_hen_da_1", "n da")
    second_half = final["pronunciation"]["text"].index("ta i he n da", 8)
    for hint_id, boundary, relative in (
        ("hint_human_tai_he_2", "i he", 3),
        ("hint_human_hen_da_2", "n da", 8),
    ):
        _add_pronunciation_link(final, hint_id, boundary)
        hint = final["languageHints"][-1]
        hint["marks"][0]["startCharIndex"] = second_half + relative
        hint["marks"][0]["endCharIndex"] = second_half + relative
    _write(root, JAPANESE_ZOO_ID, payload)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    curate_get_him_back(root)
    curate_as_if_last(root)
    curate_japanese_zoo(root)
    print("Curated English, Korean, and Japanese demo profiles")


if __name__ == "__main__":
    main()
