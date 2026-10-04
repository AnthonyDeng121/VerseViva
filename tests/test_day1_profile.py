from pathlib import Path

from server.models.song import SongProfile
from server.scripts.build_day1_profile import DAY1_SONG_ID, build_day1_profile


def test_day1_artifacts_generate_a_valid_real_profile() -> None:
    project_root = Path(__file__).resolve().parents[1]
    profile, _ = build_day1_profile(project_root)

    assert profile.song_id == DAY1_SONG_ID
    assert profile.duration_seconds > 59
    assert profile.language == "en"
    assert len(profile.sentences) == 4
    assert sum(len(sentence.words) for sentence in profile.sentences) == 96
    assert sum(len(sentence.notes) for sentence in profile.sentences) > 0
    assert profile.vocal_range is not None

    saved = project_root / "data" / "songs" / DAY1_SONG_ID / "profile.json"
    restored = SongProfile.model_validate_json(saved.read_text(encoding="utf-8"))
    assert restored == profile
