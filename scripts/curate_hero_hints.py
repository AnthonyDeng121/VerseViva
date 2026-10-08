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
            symbol="└─┘",
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

    # The final call-and-response section was originally serialized as short,
    # primary-only fragments after each lead line. Keep those lyric sentences
    # as the evidence source, but put them on the secondary lane at the same
    # time as the lead they answer.
    late_pairs = (
        ("sentence_009", "sentence_010", 23.7929, 26.921),
        ("sentence_011", "sentence_012", 27.041, 29.727),
        ("sentence_013", "sentence_014", 29.868, 32.574),
    )
    for _, response_id, start, end in late_pairs:
        response = _sentence(profile, response_id)
        response["startSeconds"] = start
        response["endSeconds"] = end
        for hint in response["languageHints"]:
            hint["startSeconds"] = start
            hint["endSeconds"] = end
        if response_id == "sentence_012":
            back_boundary = next(
                hint for hint in response["languageHints"] if hint["id"] == "hint_candidate_011_008"
            )
            back_boundary["marks"][0]["symbol"] = "‿"
            back_boundary["phenomenon"] = "cross_word_linking"

    final_response_id = "sentence_017"
    profile["sentences"] = [
        sentence for sentence in profile["sentences"] if sentence["id"] != final_response_id
    ]
    final_response = deepcopy(_sentence(profile, "sentence_012"))
    final_response.update(
        {
            "id": final_response_id,
            "startSeconds": 32.815,
            "endSeconds": 36.183,
        }
    )
    word_duration = (
        final_response["endSeconds"] - final_response["startSeconds"]
    ) / len(final_response["words"])
    for index, word in enumerate(final_response["words"]):
        word["id"] = f"word_017_{index + 1:03d}"
        word["startSeconds"] = final_response["startSeconds"] + index * word_duration
        word["endSeconds"] = final_response["startSeconds"] + (index + 1) * word_duration
    for hint in final_response["languageHints"]:
        hint["id"] = hint["id"].replace("hint_candidate_011", "hint_human_final_response")
        hint["source"] = "human_curated"
        hint["confidence"] = 1.0
        hint["startSeconds"] = final_response["startSeconds"]
        hint["endSeconds"] = final_response["endSeconds"]
        hint["evidence"] = {"curation": "product_owner_final_response_2026_10_08"}
    profile["sentences"].append(final_response)
    profile["sentences"].sort(key=lambda sentence: (sentence["startSeconds"], sentence["id"]))

    response_ids = {response_id for _, response_id, _, _ in late_pairs}
    profile["vocalParts"] = [
        part
        for part in profile["vocalParts"]
        if not (part["lane"] == "primary" and part["sentenceIds"][0] in response_ids)
        and part["id"] != "part_secondary_final_response"
    ]
    for _, response_id, start, end in late_pairs:
        part = next(
            item
            for item in profile["vocalParts"]
            if item["lane"] == "secondary" and item["sentenceIds"] == [response_id]
        )
        part["startSeconds"] = start
        part["endSeconds"] = end
    final_part = deepcopy(
        next(
            item
            for item in profile["vocalParts"]
            if item["lane"] == "secondary" and item["sentenceIds"] == ["sentence_012"]
        )
    )
    final_part.update(
        {
            "id": "part_secondary_final_response",
            "startSeconds": 32.815,
            "endSeconds": 36.183,
            "sentenceIds": [final_response_id],
        }
    )
    profile["vocalParts"].append(final_part)


def curate_korean(profile: dict) -> None:
    first = _sentence(profile, "sentence_002")
    _remove(first, "hint_human_an_a")
    first["languageHints"][0].update({"startWordIndex": 4, "endWordIndex": 5})
    first["languageHints"][1].update({"startWordIndex": 6, "endWordIndex": 7})
    first["languageHints"][1]["marks"] = [
        {"symbol": "‿", "startCharIndex": 31, "endCharIndex": 33, "placement": "below"}
    ]
    first["languageHints"][1]["canonicalPronunciation"] = "reom an"
    first["languageHints"][1]["observedPronunciation"] = "reo man"
    first["languageHints"][1]["details"] = [
        {
            "locale": "zh-CN",
            "explanation": "reom 和 an 在这次演唱中连续衔接。",
            "action": "唱完 reom 后保持气流，直接进入 an。",
        }
    ]
    first["languageHints"].append(
        _curated_hint(
            first["languageHints"][0],
            sentence=first,
            hint_id="hint_human_an_a",
            phenomenon="cross_word_linking",
            start_word=7,
            end_word=8,
            symbol="‿",
            start_char=34,
            end_char=36,
            explanation="an 和 a 在这次演唱中连续衔接。",
            action="唱完 an 后保持气流，直接进入 a。",
        )
    )
    first["languageHints"][-1]["canonicalPronunciation"] = "an a"
    first["languageHints"][-1]["observedPronunciation"] = "a na"

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
    last["languageHints"][0]["canonicalPronunciation"] = "eop neun"
    last["languageHints"][0]["observedPronunciation"] = "eo neun"
    last["languageHints"][1]["canonicalPronunciation"] = "geot cheo"
    last["languageHints"][1]["observedPronunciation"] = "geo cheo"
    for sentence in profile["sentences"]:
        maximum = len(sentence["words"]) - 1
        for hint in sentence["languageHints"]:
            hint["startWordIndex"] = min(hint["startWordIndex"], maximum)
            hint["endWordIndex"] = min(hint["endWordIndex"], maximum)
            if hint["marks"][0]["symbol"] == "×" and hint.get("canonicalPronunciation"):
                left, *right = hint["canonicalPronunciation"].split()
                hint["observedPronunciation"] = " ".join([left[:-1], *right]).strip()


def curate_japanese(profile: dict) -> None:
    for sentence in profile["sentences"]:
        pronunciation = sentence.get("pronunciation")
        if not pronunciation:
            continue
        tokens = list(re.finditer(r"[A-Za-z]+", pronunciation["text"]))
        if sentence["languageHints"] and all(
            hint.get("evidence", {}).get("curation")
            == "product_owner_shifted_left_one_sound_v4_2026_10_08"
            for hint in sentence["languageHints"]
        ):
            continue
        shifted = []
        for hint in sentence["languageHints"]:
            if sentence["id"] == "sentence_006" and hint["id"] in {
                "hint_human_tai_he_2",
                "hint_human_hen_da_2",
            }:
                continue
            previous_version = hint.get("evidence", {}).get("curation") \
                == "product_owner_shifted_one_word_2026_10_08"
            already_shifted_left = hint.get("evidence", {}).get("curation") \
                in {
                    "product_owner_shifted_left_one_sound_2026_10_08",
                    "product_owner_shifted_left_one_sound_v2_2026_10_08",
                    "product_owner_shifted_left_one_sound_v3_2026_10_08",
                }
            word_shift = 0 if already_shifted_left else (-2 if previous_version else -1)
            hint["startWordIndex"] = max(0, hint["startWordIndex"] + word_shift)
            hint["endWordIndex"] = max(0, hint["endWordIndex"] + word_shift)
            for mark in hint["marks"]:
                current = max(
                    (
                        index
                        for index, token in enumerate(tokens)
                        if token.start() <= mark["startCharIndex"]
                    ),
                    default=0,
                )
                shift = 0 if already_shifted_left else (-2 if previous_version else -1)
                target = tokens[max(0, current + shift)]
                mark["startCharIndex"] = target.end() - 1
                mark["endCharIndex"] = target.end() - 1
                mark["symbol"] = "‿"
                left = tokens[max(0, current + shift)]
                right = tokens[min(max(0, current + shift) + 1, len(tokens) - 1)]
                hint["canonicalPronunciation"] = f"{left.group()} {right.group()}"
                hint["observedPronunciation"] = f"{left.group()}{right.group()}"
                target = f"{left.group()} {right.group()}"
                hint["details"] = [
                    {
                        "locale": "zh-CN",
                        "explanation": f"原唱在 {target} 处保持连续语流，没有单独停顿。",
                        "action": f"把 {target} 放在同一口气中自然衔接。",
                    }
                ]
            hint["source"] = "human_curated"
            hint["confidence"] = 1.0
            hint["evidence"] = {
                "curation": "product_owner_shifted_left_one_sound_v4_2026_10_08"
            }
            shifted.append(hint)
        sentence["languageHints"] = shifted


def main() -> None:
    for suffix, curator in (("03", curate_english), ("04", curate_korean), ("05", curate_japanese)):
        path, profile = _profile(suffix)
        curator(profile)
        for sentence in profile["sentences"]:
            for hint in sentence["languageHints"]:
                for detail in hint["details"]:
                    detail["action"] = re.sub(r"^建议[：:]\s*", "", detail["action"])
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Curated {path}")


if __name__ == "__main__":
    main()
