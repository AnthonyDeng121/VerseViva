import re
from pathlib import Path

from server.services.practice.analyzer import (
    _build_prompt,
    _build_secondary_prompt,
    issue_type_for_hint,
    target_words_for_hint,
)
from server.services.practice.service import _secondary_target_specs
from server.storage.profile_store import ProfileStore

ROOT = Path(__file__).resolve().parents[1]
SONG_PREFIX = "song_000000000000000000000000000000"


def _sentence(suffix: str, sentence_id: str):
    profile = ProfileStore(ROOT / "data").get(f"{SONG_PREFIX}{suffix}")
    assert profile is not None
    return next(sentence for sentence in profile.sentences if sentence.id == sentence_id)


def _hints(sentence):
    return {hint.id: hint for hint in sentence.language_hints}


def test_get_him_back_owner_corrections_are_preserved() -> None:
    opening = _hints(_sentence("03", "sentence_001"))
    assert opening["hint_human_want_to_secondary"].marks[0].symbol == "└─┘"

    stitch = _hints(_sentence("03", "sentence_004"))
    assert "hint_candidate_003_007" not in stitch
    assert stitch["hint_human_up_wanna"].marks[0].symbol == "‿"

    tell = _hints(_sentence("03", "sentence_008"))
    assert tell["hint_human_sucks_oh"].marks[0].start_char_index == 29

    uppercut = _hints(_sentence("03", "sentence_013"))
    assert "hint_candidate_012_004" not in uppercut
    assert uppercut["hint_human_with_an"].marks[0].symbol == "‿"
    assert uppercut["hint_human_uppercut_t"].marks[0].symbol == "×"

    final_response = _sentence("03", "sentence_017")
    assert final_response.start_seconds == 32.815
    assert final_response.end_seconds == 36.183
    assert final_response.lyrics == "(But then I, I want to get him back; get him back)"
    assert next(
        hint for hint in final_response.language_hints
        if hint.id == "hint_human_final_response_008"
    ).marks[0].symbol == "‿"

    profile = ProfileStore(ROOT / "data").get(f"{SONG_PREFIX}03")
    assert profile is not None
    sentences = {item.id: item for item in profile.sentences}
    for part in (item for item in profile.vocal_parts if item.lane.value == "secondary"):
        assert part.start_seconds == sentences[part.sentence_ids[0]].start_seconds


def test_secondary_plan_b_uses_confirmed_marked_targets() -> None:
    profile = ProfileStore(ROOT / "data").get(f"{SONG_PREFIX}03")
    assert profile is not None
    parts = [
        item
        for item in profile.vocal_parts
        if item.id in {"part_secondary_001_01", "part_secondary_002_01"}
    ]
    sentences = [
        item for item in profile.sentences if item.id in {"sentence_001", "sentence_002"}
    ]
    targets = _secondary_target_specs(parts, sentences)

    assert {(item["targetWords"], item["symbol"]) for item in targets} >= {
        ("get him", "‿"),
        ("want to", "└─┘"),
        ("But", "×"),
        ("then I", "‿"),
    }
    prompt = _build_secondary_prompt(parts, targets)
    assert "没有具体 TARGET 的歌词不得自行补充判断" in prompt
    assert "不得据此否定 TARGET" in prompt


def test_korean_owner_corrections_target_romanization() -> None:
    first = _hints(_sentence("04", "sentence_002"))
    assert first["hint_candidate_001_003"].marks[0].start_char_index == 21
    assert first["hint_candidate_001_006"].marks[0].start_char_index == 31
    assert first["hint_candidate_001_006"].canonical_pronunciation == "reom an"
    assert first["hint_human_an_a"].marks[0].start_char_index == 34
    assert first["hint_human_an_a"].canonical_pronunciation == "an a"

    last = _hints(_sentence("04", "sentence_009"))
    assert last["hint_human_eop_neun"].marks[0].symbol == "×"
    assert last["hint_human_geot_cheo"].marks[0].symbol == "×"

    profile = ProfileStore(ROOT / "data").get(f"{SONG_PREFIX}04")
    assert profile is not None
    for sentence in profile.sentences:
        for hint in sentence.language_hints:
            if hint.marks[0].symbol != "×" or not hint.canonical_pronunciation:
                continue
            canonical_left = hint.canonical_pronunciation.split()[0]
            observed_left = (hint.observed_pronunciation or "").split()[0]
            assert observed_left == canonical_left[:-1]


def test_japanese_marks_stay_shifted_and_final_he_n_is_unmarked() -> None:
    last = _hints(_sentence("05", "sentence_006"))
    assert "hint_human_tai_he_2" not in last
    assert "hint_human_hen_da_2" not in last
    assert all(hint.source.value == "human_curated" for hint in last.values())
    assert all(
        hint.evidence.get("curation") == "product_owner_shifted_left_one_sound_v4_2026_10_08"
        for hint in last.values()
    )
    assert all(hint.marks[0].symbol == "‿" for hint in last.values())

    first = _hints(_sentence("05", "sentence_001"))
    assert first["hint_human_en_wa"].marks[0].start_char_index == 22
    assert first["hint_human_en_wa"].marks[0].symbol == "‿"
    assert first["hint_human_en_wa"].canonical_pronunciation == "e n"
    detail = first["hint_human_en_wa"].details[0]
    assert "e n" in detail.action
    assert "n wa" not in detail.action
    assert not detail.action.startswith("建议")


def test_hero_actions_do_not_duplicate_the_ui_label() -> None:
    store = ProfileStore(ROOT / "data")
    for suffix in ("03", "04", "05"):
        profile = store.get(f"{SONG_PREFIX}{suffix}")
        assert profile is not None
        assert all(
            not detail.action.startswith("建议")
            for sentence in profile.sentences
            for hint in sentence.language_hints
            for detail in hint.details
        )


def test_multilingual_card_targets_match_adjacent_romanized_tokens() -> None:
    store = ProfileStore(ROOT / "data")
    for suffix in ("04", "05"):
        profile = store.get(f"{SONG_PREFIX}{suffix}")
        assert profile is not None
        for sentence in profile.sentences:
            if sentence.pronunciation is None:
                continue
            words = list(re.finditer(r"[A-Za-z]+(?:['’][A-Za-z]+)*", sentence.pronunciation.text))
            for hint in sentence.language_hints:
                if not hint.canonical_pronunciation:
                    continue
                position = hint.marks[0].start_char_index
                left = next(word.group() for word in reversed(words) if word.start() <= position)
                right = next(word.group() for word in words if word.start() > position)
                assert hint.canonical_pronunciation == f"{left} {right}"


def test_every_hero_symbol_is_available_to_practice_analysis() -> None:
    store = ProfileStore(ROOT / "data")
    for suffix in ("03", "04", "05"):
        profile = store.get(f"{SONG_PREFIX}{suffix}")
        assert profile is not None
        assert all(
            issue_type_for_hint(hint) is not None
            for sentence in profile.sentences
            for hint in sentence.language_hints
        )


def test_elision_target_does_not_include_the_other_vocal_lane() -> None:
    sentence = _sentence("03", "sentence_003")
    hint = _hints(sentence)["hint_candidate_002_004"]
    assert target_words_for_hint(sentence, hint) == "heart"


def test_practice_prompt_defines_all_three_visible_language_actions() -> None:
    profile = ProfileStore(ROOT / "data").get(f"{SONG_PREFIX}03")
    assert profile is not None
    prompt = _build_prompt(profile.sentences)
    assert "×（吞音/未清楚释放）" in prompt
    assert "‿（改音式连读）" in prompt
    assert "└┘（二合一）" in prompt
    assert '"symbol": "×"' in prompt
    assert '"symbol": "‿"' in prompt
    assert '"symbol": "└┘"' in prompt
    assert '"referenceAction"' in prompt
