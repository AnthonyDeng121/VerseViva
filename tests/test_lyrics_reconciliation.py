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


def test_parenthetical_vocal_is_restored_but_not_required_for_excerpt_match() -> None:
    asr_words = "I wanna key his car I wanna make him lunch I wanna break his heart".split()
    asr = SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=4,
        lyrics=" ".join(asr_words),
        words=[
            WordTiming(
                id=f"w{index}",
                text=word,
                start_seconds=index * 0.25,
                end_seconds=(index + 1) * 0.25,
            )
            for index, word in enumerate(asr_words)
        ],
    )

    sentences, matched = reconcile_provided_lyrics(
        "Unrelated intro line\n"
        "I wanna key his car (I want to get him back)\n"
        "I wanna make him lunch (But then I, I want to get him back)\n"
        "I wanna break his heart (But then I, I want to get him back)\n"
        "Unrelated outro line",
        [asr],
    )

    assert matched is True
    assert len(sentences) == 3
    assert sentences[0].lyrics.endswith("(I want to get him back)")
    assert "(But then I, I want to get him back)" in sentences[-1].lyrics


def test_online_lyrics_win_when_whisperx_has_wrong_words() -> None:
    asr = SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=4,
        lyrics="I know you want my touch four life if you love me right and who knows",
        words=[
            WordTiming(
                id=f"w{index}",
                text=word,
                start_seconds=index * 0.25,
                end_seconds=(index + 1) * 0.25,
            )
            for index, word in enumerate(
                "I know you want my touch four life if you love me right and who knows".split()
            )
        ],
    )

    sentences, matched = reconcile_provided_lyrics(
        "Intro line\nI know you want my touch for life\n"
        "If you love me right then who knows\nOutro line",
        [asr],
    )

    assert matched is True
    assert [sentence.lyrics for sentence in sentences] == [
        "I know you want my touch for life",
        "If you love me right then who knows",
    ]
    assert [word.text for sentence in sentences for word in sentence.words][6] == "for"
    assert [word.text for sentence in sentences for word in sentence.words][13] == "then"


def test_online_lyrics_missing_from_asr_receive_interpolated_times() -> None:
    asr = SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=2,
        lyrics="I know want touch life",
        words=[
            WordTiming(
                id=f"w{index}",
                text=word,
                start_seconds=index * 0.4,
                end_seconds=(index + 1) * 0.4,
            )
            for index, word in enumerate("I know want touch life".split())
        ],
    )

    sentences, matched = reconcile_provided_lyrics(
        "I know you want my touch for life",
        [asr],
    )

    assert matched is True
    words = sentences[0].words
    assert [word.text for word in words] == "I know you want my touch for life".split()
    assert all(
        left.start_seconds <= right.start_seconds
        for left, right in zip(words, words[1:], strict=False)
    )


def test_reconciliation_keeps_complete_online_lyrics_boundary_line() -> None:
    asr = SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=2,
        lyrics="Tell me I'm the only",
        words=[
            WordTiming(
                id=f"w{index}",
                text=word,
                start_seconds=index * 0.4,
                end_seconds=(index + 1) * 0.4,
            )
            for index, word in enumerate("Tell me I'm the only".split())
        ],
    )

    sentences, matched = reconcile_provided_lyrics(
        "Previous line\nTell me I'm the only, only, only, only one",
        [asr],
    )

    assert matched is True
    assert sentences[-1].lyrics == "Tell me I'm the only, only, only, only one"
    assert [word.text for word in sentences[-1].words][-4:] == ["only", "only", "only", "one"]


def test_fuzzy_match_still_rejects_unrelated_song() -> None:
    original = [aligned_sentence()]

    sentences, matched = reconcile_provided_lyrics(
        "Dancing underneath a completely different moon tonight",
        original,
    )

    assert matched is False
    assert sentences == original
