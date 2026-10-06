from server.models.song import VocalArrangementMode
from server.services.vocal_parts.arrangement import select_arrangement_mode


def test_parentheses_select_dual_track_pipeline() -> None:
    assert (
        select_arrangement_mode("Lead lyric (backing response)")
        == VocalArrangementMode.dual_track
    )


def test_plain_lyrics_select_single_track_pipeline() -> None:
    assert select_arrangement_mode("Lead lyric only") == VocalArrangementMode.single_track
