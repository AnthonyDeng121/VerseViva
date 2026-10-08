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
    stitch = _hints(_sentence("03", "sentence_004"))
    assert "hint_candidate_003_007" not in stitch
    assert stitch["hint_human_up_wanna"].marks[0].symbol == "‿"

    tell = _hints(_sentence("03", "sentence_008"))
    assert tell["hint_human_sucks_oh"].marks[0].start_char_index == 29

    uppercut = _hints(_sentence("03", "sentence_013"))
    assert "hint_candidate_012_004" not in uppercut
    assert uppercut["hint_human_with_an"].marks[0].symbol == "‿"
    assert uppercut["hint_human_uppercut_t"].marks[0].symbol == "×"


def test_korean_owner_corrections_target_romanization() -> None:
    first = _hints(_sentence("04", "sentence_002"))
    assert first["hint_candidate_001_003"].marks[0].start_char_index == 21
    assert first["hint_candidate_001_006"].marks[0].start_char_index == 34

    last = _hints(_sentence("04", "sentence_009"))
    assert last["hint_human_eop_neun"].marks[0].symbol == "×"
    assert last["hint_human_geot_cheo"].marks[0].symbol == "×"


def test_japanese_marks_stay_shifted_and_final_he_n_is_unmarked() -> None:
    last = _hints(_sentence("05", "sentence_006"))
    assert "hint_human_tai_he_2" not in last
    assert all(hint.source.value == "human_curated" for hint in last.values())
    assert all(
        hint.evidence.get("curation") == "product_owner_shifted_one_word_2026_10_08"
        for hint in last.values()
    )
