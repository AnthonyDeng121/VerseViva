from server.models.song import SongSentence, WordTiming
from server.services.lyrics_reconciliation import reconcile_provided_lyrics


def aligned_sentence() -> SongSentence:
    return SongSentence(
        id="sentence_001",
        start_seconds=1,
        end_seconds=3,
        lyrics="were old up in",
        words=[
            WordTiming(id="w1", text="were", start_seconds=1, end_seconds=1.4),
            WordTiming(id="w2", text="old", start_seconds=1.4, end_seconds=1.8),
            WordTiming(id="w3", text="up", start_seconds=2, end_seconds=2.3),
            WordTiming(id="w4", text="in", start_seconds=2.3, end_seconds=2.7),
        ],
    )


def test_provided_lyrics_keep_spelling_and_reuse_alignment_times() -> None:
    sentences, matched = reconcile_provided_lyrics("We're old\nup in", [aligned_sentence()])

    assert matched is True
    assert [sentence.lyrics for sentence in sentences] == ["We're old", "up in"]
    assert sentences[0].words[0].start_seconds == 1
    assert sentences[1].words[-1].end_seconds == 2.7


def test_mismatched_lyrics_fall_back_to_whisperx_sentences() -> None:
    original = [aligned_sentence()]
    sentences, matched = reconcile_provided_lyrics("completely different", original)

    assert matched is False
    assert sentences == original


def test_full_song_lyrics_can_be_reconciled_to_uploaded_excerpt() -> None:
    sentences, matched = reconcile_provided_lyrics(
        "Intro words\nWe're old\nup in\nOutro words",
        [aligned_sentence()],
    )

    assert matched is True
    assert [sentence.lyrics for sentence in sentences] == ["We're old", "up in"]
    assert sentences[0].words[0].start_seconds == 1.0
    assert sentences[-1].words[-1].end_seconds == 2.7
