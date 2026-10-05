from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    CharacterMark,
    LanguageHint,
    LanguageHintSource,
    LocalizedHintDetail,
    LyricsSource,
    MarkPlacement,
    Note,
    PitchPoint,
    SegmentOperation,
    SegmentTransformation,
    SongProfile,
    SongSentence,
    VocalLane,
    VocalPart,
    VocalPartRole,
    VocalPartSource,
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

    assert payload["schemaVersion"] == "1.3"
    assert payload["durationSeconds"] == 60.003
    assert payload["audio"]["vocalUrl"].endswith("vocals.wav")
    assert payload["vocalRange"]["lowestMidi"] == 48
    assert payload["sentences"][0]["startSeconds"] == 0.852
    assert payload["sentences"][0]["words"][0]["text"] == "I"
    assert payload["analysis"]["lyricsSource"] == "asr"


def test_optional_future_features_have_honest_empty_defaults() -> None:
    sentence = make_profile().sentences[0]

    assert sentence.language_hints == []
    assert sentence.vocal_features.vocal_register is None
    assert sentence.vocal_features.falsetto is None
    assert sentence.vocal_features.confidence is None
    assert make_profile().vocal_parts == []


def test_profile_supports_overlapping_primary_and_secondary_vocal_parts() -> None:
    profile = make_profile().model_copy(
        update={
            "vocal_parts": [
                VocalPart(
                    id="part_lead",
                    lane=VocalLane.primary,
                    role=VocalPartRole.lead,
                    start_seconds=0.852,
                    end_seconds=4.2,
                    lyrics="I know you want my touch for life",
                    sentence_ids=["sentence_001"],
                    source=VocalPartSource.human_curated,
                    confidence=1,
                ),
                VocalPart(
                    id="part_harmony",
                    lane=VocalLane.secondary,
                    role=VocalPartRole.harmony,
                    start_seconds=3.7,
                    end_seconds=5.1,
                    lyrics="for life",
                    sentence_ids=["sentence_001"],
                    source=VocalPartSource.audio_model_candidate,
                    confidence=0.72,
                ),
            ]
        }
    )

    payload = profile.model_dump(mode="json", by_alias=True)

    assert payload["vocalParts"][0]["lane"] == "primary"
    assert payload["vocalParts"][1]["lane"] == "secondary"
    assert payload["vocalParts"][1]["role"] == "harmony"
    assert payload["vocalParts"][0]["endSeconds"] > payload["vocalParts"][1]["startSeconds"]


def test_profile_rejects_vocal_part_outside_song_or_unknown_sentence() -> None:
    outside_song = make_profile().model_dump()
    outside_song["vocal_parts"] = [
        {
            "id": "part_too_long",
            "lane": "secondary",
            "role": "ad_lib",
            "start_seconds": 59,
            "end_seconds": 61,
            "lyrics": "oh",
            "source": "human_curated",
            "confidence": 1,
        }
    ]
    with pytest.raises(ValidationError, match="inside the song"):
        SongProfile.model_validate(outside_song)

    invalid = make_profile().model_dump()
    invalid["vocal_parts"] = [
        {
            "id": "part_unknown_sentence",
            "lane": "secondary",
            "role": "response",
            "start_seconds": 2,
            "end_seconds": 3,
            "lyrics": "who knows",
            "sentence_ids": ["sentence_missing"],
            "source": "human_curated",
            "confidence": 1,
        }
    ]
    with pytest.raises(ValidationError, match="sentence ids"):
        SongProfile.model_validate(invalid)


def test_phonetic_hint_separates_lyric_marks_from_chinese_detail() -> None:
    sentence = SongSentence(
        id="sentence_hook",
        start_seconds=10,
        end_seconds=12,
        lyrics="want me",
        words=[
            WordTiming(id="word_want", text="want", start_seconds=10, end_seconds=10.8),
            WordTiming(id="word_me", text="me", start_seconds=10.8, end_seconds=12),
        ],
        language_hints=[
            LanguageHint(
                id="hint_want_t",
                language="en",
                phenomenon="consonant_elision",
                transformations=[
                    SegmentTransformation(
                        operation=SegmentOperation.delete,
                        input_segments=["t"],
                    )
                ],
                start_word_index=0,
                end_word_index=1,
                start_seconds=10.55,
                end_seconds=10.95,
                source=LanguageHintSource.human_curated,
                confidence=0.95,
                marks=[
                    CharacterMark(
                        symbol="×",
                        start_char_index=3,
                        end_char_index=3,
                        placement=MarkPlacement.below,
                    )
                ],
                details=[
                    LocalizedHintDetail(
                        locale="zh-CN",
                        explanation="原唱没有清楚释放 want 末尾的 t。",
                        action="唱完 wan 后直接进入 me，不要额外弹出 t。",
                    )
                ],
                evidence={"reviewedClip": "hero-hook"},
            )
        ],
    )

    payload = sentence.model_dump(mode="json", by_alias=True)
    hint = payload["languageHints"][0]
    assert hint["phenomenon"] == "consonant_elision"
    assert hint["transformations"] == [
        {"operation": "delete", "inputSegments": ["t"], "outputSegments": []}
    ]
    assert hint["marks"] == [
        {"symbol": "×", "startCharIndex": 3, "endCharIndex": 3, "placement": "below"}
    ]
    assert hint["details"][0]["locale"] == "zh-CN"
    assert "explanation" not in hint["marks"][0]


def test_language_hint_rejects_marks_outside_the_lyric() -> None:
    with pytest.raises(ValidationError, match="character marks"):
        SongSentence(
            id="sentence_bad_hint",
            start_seconds=0,
            end_seconds=2,
            lyrics="want me",
            words=[WordTiming(id="word_want", text="want", start_seconds=0, end_seconds=1)],
            language_hints=[
                LanguageHint(
                    id="hint_bad",
                    language="en",
                    phenomenon="consonant_elision",
                    transformations=[
                        SegmentTransformation(
                            operation=SegmentOperation.delete,
                            input_segments=["t"],
                        )
                    ],
                    start_word_index=0,
                    end_word_index=0,
                    start_seconds=0.5,
                    end_seconds=0.8,
                    source=LanguageHintSource.text_rule_candidate,
                    confidence=0.5,
                    marks=[
                        CharacterMark(
                            symbol="×",
                            start_char_index=99,
                            end_char_index=99,
                            placement=MarkPlacement.below,
                        )
                    ],
                )
            ],
        )


@pytest.mark.parametrize(
    "transformation",
    [
        {"operation": "delete", "input_segments": [], "output_segments": []},
        {"operation": "insert", "input_segments": ["ə"], "output_segments": ["ə"]},
        {"operation": "merge", "input_segments": ["d"], "output_segments": ["d"]},
        {"operation": "substitute", "input_segments": ["t"], "output_segments": []},
    ],
)
def test_segment_transformations_reject_impossible_operation_shapes(
    transformation: dict,
) -> None:
    with pytest.raises(ValidationError):
        SegmentTransformation(**transformation)


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
