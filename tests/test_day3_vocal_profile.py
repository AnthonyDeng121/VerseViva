from pathlib import Path

from server.scripts.build_day3_vocal_profile import (
    DAY3_VOCAL_SONG_ID,
    build_day3_vocal_profile,
)


def test_day3_profile_builds_traceable_multi_part_hero() -> None:
    project_root = Path(__file__).resolve().parents[1]
    profile, fixture_path = build_day3_vocal_profile(project_root, persist_profile=False)

    primary = [part for part in profile.vocal_parts if part.lane == "primary"]
    secondary = [part for part in profile.vocal_parts if part.lane == "secondary"]

    assert profile.song_id == DAY3_VOCAL_SONG_ID
    assert profile.audio.vocal_url is not None
    assert profile.audio.accompaniment_url is not None
    assert profile.analysis.vocal_arrangement_mode == "dual_track"
    audio_dir = project_root / "data" / "songs" / DAY3_VOCAL_SONG_ID / "audio"
    assert (audio_dir / "vocals.wav").is_file()
    assert (audio_dir / "accompaniment.wav").is_file()
    assert fixture_path.is_file()
    assert len(primary) == 12
    assert len(secondary) == 12
    assert all(part.needs_human_review for part in primary)
    assert all(not part.needs_human_review for part in secondary)
    assert profile.sentences
    assert any(sentence.words for sentence in profile.sentences)
    assert all(part.evidence["audioRef"].endswith("vocals.wav") for part in profile.vocal_parts)
    assert any(
        left.start_seconds < right.end_seconds and right.start_seconds < left.end_seconds
        for left in primary
        for right in secondary
    )
