from pathlib import Path

from server.storage.profile_store import ProfileStore

DAY3_VOCAL_SONG_ID = "song_00000000000000000000000000000003"


def test_day3_profile_builds_traceable_multi_part_hero() -> None:
    project_root = Path(__file__).resolve().parents[1]
    profile = ProfileStore(project_root / "data").get(DAY3_VOCAL_SONG_ID)
    assert profile is not None

    primary = [part for part in profile.vocal_parts if part.lane == "primary"]
    secondary = [part for part in profile.vocal_parts if part.lane == "secondary"]

    assert profile.song_id == DAY3_VOCAL_SONG_ID
    assert profile.audio.vocal_url is not None
    assert profile.audio.accompaniment_url is not None
    assert profile.analysis.vocal_arrangement_mode == "dual_track"
    audio_dir = project_root / "data" / "songs" / DAY3_VOCAL_SONG_ID / "audio"
    assert (audio_dir / "vocals.wav").is_file()
    assert (audio_dir / "accompaniment.wav").is_file()
    assert len(primary) == 13
    assert len(secondary) == 12
    assert all(not part.needs_human_review for part in secondary)
    assert profile.sentences
    assert any(sentence.words for sentence in profile.sentences)
    assert all(part.source.value == "lyrics_provider" for part in secondary)
    assert any(
        left.start_seconds < right.end_seconds and right.start_seconds < left.end_seconds
        for left in primary
        for right in secondary
    )
    sentence_starts = {sentence.id: sentence.start_seconds for sentence in profile.sentences}
    but_then_parts = [part for part in secondary if part.lyrics.startswith("But then")]
    assert all(
        part.start_seconds == sentence_starts[part.sentence_ids[0]]
        for part in but_then_parts
    )
