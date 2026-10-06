from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class AnalysisStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisStage(StrEnum):
    queued = "queued"
    probing_audio = "probing_audio"
    separating_vocals = "separating_vocals"
    extracting_pitch = "extracting_pitch"
    fetching_lyrics = "fetching_lyrics"
    aligning_lyrics = "aligning_lyrics"
    analyzing_vocal_parts = "analyzing_vocal_parts"
    analyzing_language = "analyzing_language"
    building_profile = "building_profile"
    completed = "completed"
    failed = "failed"


class AnalysisError(BaseModel):
    code: str
    stage: AnalysisStage
    message: str
    detail: str | None = None


class AnalysisWarning(BaseModel):
    stage: AnalysisStage
    message: str
    detail: str | None = None


class AnalysisJob(BaseModel):
    job_id: str
    song_id: str
    status: AnalysisStatus
    stage: AnalysisStage = AnalysisStage.queued
    progress: int = Field(default=0, ge=0, le=100)
    title: str
    artist: str | None = None
    has_lyrics: bool
    attempt_count: int = Field(default=0, ge=0)
    error: AnalysisError | None = None
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SongProfileModel(BaseModel):
    """Base model for the versioned JSON contract consumed by the frontend."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AudioAssets(SongProfileModel):
    source_url: str
    vocal_url: str | None = None
    accompaniment_url: str | None = None


class PitchPoint(SongProfileModel):
    time_seconds: float = Field(ge=0)
    frequency_hz: float = Field(gt=0)
    midi: float
    confidence: float = Field(ge=0, le=1)


class WordTiming(SongProfileModel):
    id: str
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_interval(self) -> "WordTiming":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class Note(SongProfileModel):
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    note_name: str
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_interval(self) -> "Note":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class SegmentOperation(StrEnum):
    delete = "delete"
    unreleased = "unreleased"
    merge = "merge"
    substitute = "substitute"
    insert = "insert"
    resegment = "resegment"
    lengthen = "lengthen"
    shorten = "shorten"


class LanguageHintSource(StrEnum):
    acoustic_observed = "acoustic_observed"
    text_rule_candidate = "text_rule_candidate"
    llm_suggestion = "llm_suggestion"
    human_curated = "human_curated"


class MarkPlacement(StrEnum):
    above = "above"
    below = "below"
    inline = "inline"
    bridge = "bridge"


class CharacterMark(SongProfileModel):
    """A language-independent symbol anchored to characters in the displayed lyrics."""

    symbol: str = Field(min_length=1, max_length=4)
    start_char_index: int = Field(ge=0)
    end_char_index: int = Field(ge=0)
    placement: MarkPlacement

    @model_validator(mode="after")
    def validate_range(self) -> "CharacterMark":
        if self.end_char_index < self.start_char_index:
            raise ValueError("end_char_index must be greater than or equal to start_char_index")
        return self


class LocalizedHintDetail(SongProfileModel):
    locale: str = Field(min_length=2)
    explanation: str = Field(min_length=1)
    action: str = Field(min_length=1)


class SegmentTransformation(SongProfileModel):
    """A language-independent change from expected to observed sound segments."""

    operation: SegmentOperation
    input_segments: list[str] = Field(default_factory=list)
    output_segments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "SegmentTransformation":
        if self.operation == SegmentOperation.delete:
            if not self.input_segments or self.output_segments:
                raise ValueError("delete requires input segments and no output segments")
        elif self.operation == SegmentOperation.insert:
            if self.input_segments or not self.output_segments:
                raise ValueError("insert requires output segments and no input segments")
        elif not self.input_segments or not self.output_segments:
            raise ValueError(f"{self.operation} requires both input and output segments")
        if self.operation == SegmentOperation.merge and len(self.input_segments) < 2:
            raise ValueError("merge requires at least two input segments")
        return self


class LanguageHint(SongProfileModel):
    """A reference-performance phonetic change with compact marks and expandable details."""

    id: str
    language: str = Field(min_length=2)
    phenomenon: str = Field(min_length=1)
    transformations: list[SegmentTransformation] = Field(min_length=1)
    start_word_index: int = Field(ge=0)
    end_word_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    source: LanguageHintSource
    confidence: float = Field(ge=0, le=1)
    marks: list[CharacterMark] = Field(min_length=1)
    details: list[LocalizedHintDetail] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ranges(self) -> "LanguageHint":
        if self.end_word_index < self.start_word_index:
            raise ValueError("end_word_index must be greater than or equal to start_word_index")
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class VocalFeatures(SongProfileModel):
    vocal_register: str | None = Field(default=None, alias="register")
    falsetto: bool | None = None
    timbre: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class VocalLane(StrEnum):
    primary = "primary"
    secondary = "secondary"


class VocalPartRole(StrEnum):
    lead = "lead"
    harmony = "harmony"
    backing_vocal = "backing_vocal"
    response = "response"
    ad_lib = "ad_lib"
    double = "double"
    overlap = "overlap"


class VocalPartSource(StrEnum):
    acoustic_candidate = "acoustic_candidate"
    audio_model_candidate = "audio_model_candidate"
    lyrics_structure_candidate = "lyrics_structure_candidate"
    lyrics_provider = "lyrics_provider"
    human_curated = "human_curated"


class VocalPartIdentityStatus(StrEnum):
    confirmed = "confirmed"
    candidate = "candidate"


class VocalPartTimingStatus(StrEnum):
    aligned_sentence_fallback = "aligned_sentence_fallback"
    audio_model_observed = "audio_model_observed"
    human_curated = "human_curated"


class VocalPart(SongProfileModel):
    """One reference vocal layer; the two-lane UI may contain many such parts."""

    id: str
    lane: VocalLane
    role: VocalPartRole
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    lyrics: str = Field(min_length=1)
    sentence_ids: list[str] = Field(default_factory=list)
    source: VocalPartSource
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool = False
    identity_status: VocalPartIdentityStatus = VocalPartIdentityStatus.candidate
    timing_status: VocalPartTimingStatus = VocalPartTimingStatus.aligned_sentence_fallback
    timing_confidence: float | None = Field(default=None, ge=0, le=1)
    timing_needs_human_review: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_interval(self) -> "VocalPart":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        if self.source not in {
            VocalPartSource.human_curated,
            VocalPartSource.lyrics_provider,
        } and not self.needs_human_review:
            raise ValueError("candidate vocal parts must require human review")
        if self.source == VocalPartSource.lyrics_provider:
            if self.identity_status != VocalPartIdentityStatus.confirmed:
                raise ValueError("provider-backed vocal part identity must be confirmed")
            if self.needs_human_review:
                raise ValueError("provider-backed vocal part identity must not require review")
        return self


class SongSentence(SongProfileModel):
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    lyrics: str
    words: list[WordTiming] = Field(default_factory=list)
    pitch_contour: list[PitchPoint] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    language_hints: list[LanguageHint] = Field(default_factory=list)
    vocal_features: VocalFeatures = Field(default_factory=VocalFeatures)

    @model_validator(mode="after")
    def validate_interval(self) -> "SongSentence":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        for hint in self.language_hints:
            if hint.end_word_index >= len(self.words):
                raise ValueError("language hint word indexes must point to sentence words")
            if any(mark.end_char_index >= len(self.lyrics) for mark in hint.marks):
                raise ValueError("language hint character marks must point to sentence lyrics")
            if hint.start_seconds < self.start_seconds or hint.end_seconds > self.end_seconds:
                raise ValueError("language hint timestamps must stay inside the sentence")
        return self


class VocalRange(SongProfileModel):
    lowest_midi: int = Field(ge=0, le=127)
    highest_midi: int = Field(ge=0, le=127)
    lowest_note: str
    highest_note: str

    @model_validator(mode="after")
    def validate_range(self) -> "VocalRange":
        if self.highest_midi < self.lowest_midi:
            raise ValueError("highest_midi must be greater than or equal to lowest_midi")
        return self


class LyricsSource(StrEnum):
    provided = "provided"
    lrclib = "lrclib"
    lrc = "lrc"
    asr = "asr"
    corrected = "corrected"


class VocalArrangementMode(StrEnum):
    single_track = "single_track"
    dual_track = "dual_track"


class PitchProcessingSummary(SongProfileModel):
    source: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    raw_note_count: int = Field(ge=0)
    accepted_note_count: int = Field(ge=0)
    rejected_note_count: int = Field(ge=0)
    raw_pitch_point_count: int = Field(ge=0)
    output_pitch_point_count: int = Field(ge=0)
    confidence_threshold: float = Field(ge=0, le=1)
    minimum_note_duration_seconds: float = Field(ge=0)
    octave_corrections: int = Field(ge=0)


class AnalysisMetadata(SongProfileModel):
    pipeline_version: str
    separation_model: str
    pitch_model: str
    alignment_model: str
    lyrics_source: LyricsSource
    lyrics_provider: str | None = None
    lyrics_provider_track_id: int | None = None
    lyrics_match_confidence: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime
    pitch_processing: PitchProcessingSummary | None = None
    language_analysis_provider: str | None = None
    language_analysis_model: str | None = None
    vocal_arrangement_mode: VocalArrangementMode = VocalArrangementMode.single_track


class SongProfile(SongProfileModel):
    schema_version: str = "1.5"
    song_id: str
    title: str
    duration_seconds: float = Field(gt=0)
    language: str | None = None
    audio: AudioAssets
    vocal_range: VocalRange | None = None
    sentences: list[SongSentence] = Field(default_factory=list)
    vocal_parts: list[VocalPart] = Field(default_factory=list)
    analysis: AnalysisMetadata

    @model_validator(mode="after")
    def validate_vocal_parts(self) -> "SongProfile":
        sentence_ids = {sentence.id for sentence in self.sentences}
        for part in self.vocal_parts:
            if part.end_seconds > self.duration_seconds:
                raise ValueError("vocal part timestamps must stay inside the song")
            if not set(part.sentence_ids).issubset(sentence_ids):
                raise ValueError("vocal part sentence ids must point to profile sentences")
        return self
