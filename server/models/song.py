from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class AnalysisStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisJob(BaseModel):
    job_id: str
    status: AnalysisStatus
    title: str
    has_lyrics: bool


class SongProfileModel(BaseModel):
    """Base model for the versioned JSON contract consumed by the frontend."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AudioAssets(SongProfileModel):
    source_url: str
    vocal_url: str


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


class SingingHints(SongProfileModel):
    linking: list[str] = Field(default_factory=list)
    stress: list[str] = Field(default_factory=list)
    reduction: list[str] = Field(default_factory=list)
    elision: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)


class VocalFeatures(SongProfileModel):
    vocal_register: str | None = Field(default=None, alias="register")
    falsetto: bool | None = None
    timbre: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class SongSentence(SongProfileModel):
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    lyrics: str
    words: list[WordTiming] = Field(default_factory=list)
    pitch_contour: list[PitchPoint] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    singing_hints: SingingHints = Field(default_factory=SingingHints)
    vocal_features: VocalFeatures = Field(default_factory=VocalFeatures)

    @model_validator(mode="after")
    def validate_interval(self) -> "SongSentence":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
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
    lrc = "lrc"
    asr = "asr"
    corrected = "corrected"


class AnalysisMetadata(SongProfileModel):
    pipeline_version: str
    separation_model: str
    pitch_model: str
    alignment_model: str
    lyrics_source: LyricsSource
    created_at: datetime


class SongProfile(SongProfileModel):
    schema_version: str = "1.0"
    song_id: str
    title: str
    duration_seconds: float = Field(gt=0)
    language: str | None = None
    audio: AudioAssets
    vocal_range: VocalRange | None = None
    sentences: list[SongSentence] = Field(default_factory=list)
    analysis: AnalysisMetadata
