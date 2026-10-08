"""Apply the product owner's final Hero-song pronunciation curation."""

import json
import re
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SONGS = ROOT / "data" / "songs"


def _profile(suffix: str) -> tuple[Path, dict]:
    path = SONGS / f"song_000000000000000000000000000000{suffix}" / "profile.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _sentence(profile: dict, sentence_id: str) -> dict:
    return next(item for item in profile["sentences"] if item["id"] == sentence_id)


def _remove(sentence: dict, *hint_ids: str) -> None:
    sentence["languageHints"] = [
        hint for hint in sentence["languageHints"] if hint["id"] not in hint_ids
    ]


def _curated_hint(
    template: dict,
    *,
    sentence: dict,
    hint_id: str,
    phenomenon: str,
    start_word: int,
    end_word: int,
    symbol: str,
    start_char: int,
    end_char: int,
    explanation: str,
    action: str,
) -> dict:
    hint = deepcopy(template)
    hint.update(
        {
            "id": hint_id,
            "phenomenon": phenomenon,
            "startWordIndex": start_word,
            "endWordIndex": end_word,
            "source": "human_curated",
            "confidence": 1.0,
            "startSeconds": sentence["startSeconds"],
            "endSeconds": sentence["endSeconds"],
            "marks": [
                {
                    "symbol": symbol,
                    "startCharIndex": start_char,
                    "endCharIndex": end_char,
                    "placement": "below",
                }
            ],
            "details": [
                {"locale": "zh-CN", "explanation": explanation, "action": action}
            ],
            "evidence": {"curation": "product_owner_2026_10_08"},
        }
    )
    if symbol == "×":
        hint["transformations"] = [
            {"operation": "delete", "inputSegments": ["final"], "outputSegments": []}
        ]
    else:
        hint["transformations"] = [
            {
                "operation": "resegment",
                "inputSegments": ["left", "right"],
                "outputSegments": ["linked"],
            }
        ]
    return hint


def curate_english(profile: dict) -> None:
    first = _sentence(profile, "sentence_001")
    template = first["languageHints"][0]
    _remove(first, "hint_human_want_to_secondary")
    first["languageHints"].append(
        _curated_hint(
            template,
            sentence=first,
            hint_id="hint_human_want_to_secondary",
            phenomenon="cross_word_linking",
            start_word=6,
            end_word=7,
            symbol="‿",
            start_char=26,
            end_char=28,
            explanation="次轨的 want to 连成一个连续动作。",
            action="want 收尾后直接进入 to，不在中间停顿。",
        )
    )

    up = _sentence(profile, "sentence_004")
    _remove(up, "hint_candidate_003_007", "hint_human_up_wanna")
    up["languageHints"].append(
        _curated_hint(
            template,
            sentence=up,
            hint_id="hint_human_up_wanna",
            phenomenon="cross_sentence_linking",
            start_word=7,
            end_word=7,
            symbol="‿",
            start_char=30,
            end_char=30,
            explanation="up 的尾音没有吞掉，而是跨句连续进入下一句 Wanna。",
            action="唱完 up 后不要停，直接接下一句 Wanna。",
        )
    )

    sucks = _sentence(profile, "sentence_008")
    _remove(sucks, "hint_human_sucks_oh")
    sucks["languageHints"].append(
        _curated_hint(
            template,
            sentence=sucks,
            hint_id="hint_human_sucks_oh",
            phenomenon="cross_sentence_linking",
            start_word=6,
            end_word=6,
            symbol="‿",
            start_char=29,
            end_char=29,
            explanation="sucks 的 s 连续进入下一句 Oh，没有在句尾断开。",
            action="保持 s 的气流，直接进入下一句 Oh。",
        )
    )

    uppercut = _sentence(profile, "sentence_013")
    _remove(
        uppercut,
        "hint_candidate_012_004",
        "hint_candidate_012_006",
        "hint_human_with_an",
        "hint_human_uppercut_t",
    )
    uppercut["languageHints"].extend(
        [
            _curated_hint(
                template,
                sentence=uppercut,
                hint_id="hint_human_with_an",
                phenomenon="cross_word_linking",
                start_word=5,
                end_word=6,
                symbol="‿",
                start_char=25,
                end_char=27,
                explanation="with 与 an 连续衔接；face 与 with 之间不标连读。",
                action="face 唱清后，再把 with an 连成一个动作。",
            ),
            _curated_hint(
                template,
                sentence=uppercut,
                hint_id="hint_human_uppercut_t",
                phenomenon="consonant_elision",
                start_word=7,
                end_word=7,
                symbol="×",
                start_char=37,
                end_char=37,
                explanation="uppercut 末尾的 t 在这次演唱中没有清楚释放。",
                action="唱到 uppercu- 后收住，不要额外弹出 t。",
            ),
        ]
    )


def curate_korean(profile: dict) -> None:
    first = _sentence(profile, "sentence_002")
    first["languageHints"][0].update({"startWordIndex": 4, "endWordIndex": 5})
    first["languageHints"][1].update({"startWordIndex": 7, "endWordIndex": 8})

    last = _sentence(profile, "sentence_009")
    template = first["languageHints"][0]
    last["languageHints"] = [
        _curated_hint(
            template,
            sentence=last,
            hint_id="hint_human_eop_neun",
            phenomenon="final_stop_unreleased",
            start_word=4,
            end_word=5,
            symbol="×",
            start_char=17,
            end_char=17,
            explanation="eop 的收尾在 neun 前没有独立释放。",
            action="eop 收住后直接进入 neun，不额外弹出尾音。",
        ),
        _curated_hint(
            template,
            sentence=last,
            hint_id="hint_human_geot_cheo",
            phenomenon="final_stop_unreleased",
            start_word=6,
            end_word=7,
            symbol="×",
            start_char=27,
            end_char=27,
            explanation="geot 的词尾在 cheo 前没有独立释放。",
            action="geot 收住后直接进入 cheo。",
        ),
    ]
    for sentence in (first, last):
        maximum = len(sentence["words"]) - 1
        for hint in sentence["languageHints"]:
            hint["startWordIndex"] = min(hint["startWordIndex"], maximum)
            hint["endWordIndex"] = min(hint["endWordIndex"], maximum)


def curate_japanese(profile: dict) -> None:
    for sentence in profile["sentences"]:
        pronunciation = sentence.get("pronunciation")
        if not pronunciation:
            continue
        tokens = list(re.finditer(r"[A-Za-z]+", pronunciation["text"]))
        if sentence["languageHints"] and all(
            hint.get("evidence", {}).get("curation")
            == "product_owner_shifted_one_word_2026_10_08"
            for hint in sentence["languageHints"]
        ):
            continue
        shifted = []
        for hint in sentence["languageHints"]:
            if sentence["id"] == "sentence_006" and hint["id"] == "hint_human_tai_he_2":
                continue
            hint["startWordIndex"] = min(hint["startWordIndex"] + 1, len(sentence["words"]) - 1)
            hint["endWordIndex"] = min(hint["endWordIndex"] + 1, len(sentence["words"]) - 1)
            for mark in hint["marks"]:
                current = max(
                    (
                        index
                        for index, token in enumerate(tokens)
                        if token.start() <= mark["startCharIndex"]
                    ),
                    default=0,
                )
                target = tokens[min(current + 1, len(tokens) - 1)]
                mark["startCharIndex"] = target.end() - 1
                mark["endCharIndex"] = target.end() - 1
            hint["source"] = "human_curated"
            hint["confidence"] = 1.0
            hint["evidence"] = {"curation": "product_owner_shifted_one_word_2026_10_08"}
            shifted.append(hint)
        sentence["languageHints"] = shifted


def main() -> None:
    for suffix, curator in (("03", curate_english), ("04", curate_korean), ("05", curate_japanese)):
        path, profile = _profile(suffix)
        curator(profile)
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Curated {path}")


if __name__ == "__main__":
    main()
