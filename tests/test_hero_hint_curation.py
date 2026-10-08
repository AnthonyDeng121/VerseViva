from pathlib import Path

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


def test_korean_owner_corrections_target_romanization() -> None:
    first = _hints(_sentence("04", "sentence_002"))
    assert first["hint_candidate_001_003"].marks[0].start_char_index == 21
    assert first["hint_candidate_001_006"].marks[0].start_char_index == 31
    assert first["hint_candidate_001_006"].canonical_pronunciation == "reom a"

    last = _hints(_sentence("04", "sentence_009"))
    assert last["hint_human_eop_neun"].marks[0].symbol == "×"
    assert last["hint_human_geot_cheo"].marks[0].symbol == "×"


def test_japanese_marks_stay_shifted_and_final_he_n_is_unmarked() -> None:
    last = _hints(_sentence("05", "sentence_006"))
    assert "hint_human_tai_he_2" not in last
    assert "hint_human_hen_da_2" not in last
    assert all(hint.source.value == "human_curated" for hint in last.values())
    assert all(
        hint.evidence.get("curation") == "product_owner_shifted_left_one_sound_v2_2026_10_08"
        for hint in last.values()
    )
    assert all(hint.marks[0].symbol == "└─┘" for hint in last.values())

    first = _hints(_sentence("05", "sentence_001"))
    assert first["hint_human_en_wa"].marks[0].start_char_index == 22
    assert first["hint_human_en_wa"].marks[0].symbol == "└─┘"
    assert first["hint_human_en_wa"].canonical_pronunciation == "e n"
