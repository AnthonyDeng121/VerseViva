from server.models.song import SongSentence, VocalLane, VocalPartSource
from server.services.vocal_parts.structure import derive_structural_vocal_parts


def test_parenthetical_lyrics_create_provider_backed_dual_lanes() -> None:
    sentence = SongSentence(
        id="sentence_001",
        start_seconds=2.0,
        end_seconds=5.0,
        lyrics="Tell me (Ah-ah) I'm the only",
    )

    parts = derive_structural_vocal_parts([sentence])

    assert [part.lane for part in parts] == [VocalLane.primary, VocalLane.secondary]
    assert parts[0].lyrics == "Tell me  I'm the only"
    assert parts[1].lyrics == "Ah-ah"
    assert parts[1].source == VocalPartSource.lyrics_structure_candidate
    assert parts[0].needs_human_review is True
    assert parts[1].needs_human_review is True


def test_plain_lyrics_do_not_pretend_to_have_multiple_vocal_parts() -> None:
    sentence = SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=2,
        lyrics="I know you want my touch for life",
    )

    assert derive_structural_vocal_parts([sentence]) == []
