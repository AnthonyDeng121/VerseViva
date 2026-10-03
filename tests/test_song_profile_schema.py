from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    Note,
    PitchPoint,
    SongProfile,
    SongSentence,
    VocalRange,
    WordTiming,
)


def make_profile() -> SongProfile:
    return SongProfile(
        song_id="song_demo",
        title="Example Song",
        duration_seconds=60.003,
        language="en",
        audio=AudioAssets(
            source_url="/media/songs/song_demo/source.mp3",
            vocal_url="/media/songs/song_demo/vocals.wav",
        ),
        vocal_range=VocalRange(
            lowest_midi=48,
            highest_midi=76,
            lowest_note="C3",
            highest_note="E5",
        ),
        sentences=[
            SongSentence(
                id="sentence_001",
                start_seconds=0.852,
                end_seconds=8.259,
                lyrics="I know you want my touch for life",
                words=[
                    WordTiming(
                        id="word_001",
                        text="I",
                        start_seconds=0.852,
                        end_seconds=1.072,
                        confidence=0.841,
                    )
                ],
                pitch_contour=[
                    PitchPoint(
                        time_seconds=0.9,
                        frequency_hz=261.63,
                        midi=60.0,
                        confidence=0.91,
                    )
                ],
                notes=[
                    Note(
                        id="note_001",
                        start_seconds=0.852,
                        end_seconds=1.12,
                        midi=60,
                        note_name="C4",
                        confidence=0.88,
                    )
                ],
            )
        ],
        analysis=AnalysisMetadata(
            pipeline_version="day2-v1",
            separation_model="htdemucs",
            pitch_model="basic-pitch",
            alignment_model="whisperx",
            lyrics_source=LyricsSource.asr,
            created_at=datetime(2026, 10, 3, 16, 0, tzinfo=UTC),
        ),
    )


def test_song_profile_serializes_to_agreed_camel_case_contract() -> None:
    payload = make_profile().model_dump(mode="json", by_alias=True)

    assert payload["schemaVersion"] == "1.0"
    assert payload["durationSeconds"] == 60.003
    assert payload["audio"]["vocalUrl"].endswith("vocals.wav")
    assert payload["vocalRange"]["lowestMidi"] == 48
    assert payload["sentences"][0]["startSeconds"] == 0.852
    assert payload["sentences"][0]["words"][0]["text"] == "I"
    assert payload["analysis"]["lyricsSource"] == "asr"


def test_optional_future_features_have_honest_empty_defaults() -> None:
    sentence = make_profile().sentences[0]

    assert sentence.singing_hints.linking == []
    assert sentence.vocal_features.vocal_register is None
    assert sentence.vocal_features.falsetto is None
    assert sentence.vocal_features.confidence is None


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (
            WordTiming,
            {"id": "word_bad", "text": "bad", "start_seconds": 2, "end_seconds": 1},
        ),
        (
            Note,
            {
                "id": "note_bad",
                "start_seconds": 2,
                "end_seconds": 1,
                "midi": 60,
                "note_name": "C4",
                "confidence": 0.8,
            },
        ),
        (
            VocalRange,
            {"lowest_midi": 76, "highest_midi": 48, "lowest_note": "E5", "highest_note": "C3"},
        ),
    ],
)
def test_invalid_intervals_and_ranges_are_rejected(model: type, values: dict) -> None:
    with pytest.raises(ValidationError):
        model(**values)
