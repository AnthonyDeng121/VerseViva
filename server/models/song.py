from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


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


class PitchPoint(BaseModel):
    time: float = Field(ge=0)
    frequency_hz: float = Field(gt=0)
    midi: float
    confidence: float = Field(ge=0, le=1)


class WordTiming(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> "WordTiming":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class SingingHints(BaseModel):
    linking: list[str] = []
    stress: list[str] = []
    reduction: list[str] = []
    elision: list[str] = []
    tips: list[str] = []


class VocalFeatures(BaseModel):
    vocal_register: str | None = None
    falsetto: bool | None = None
    timbre: str | None = None


class SongSentence(BaseModel):
    id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    lyrics: str
    pitch_contour: list[PitchPoint] = []
    words: list[WordTiming] = []
    singing_hints: SingingHints = SingingHints()
    vocal_features: VocalFeatures = VocalFeatures()


class VocalRange(BaseModel):
    lowest: str
    highest: str


class SongProfile(BaseModel):
    song_id: str
    title: str
    duration: float = Field(gt=0)
    vocal_range: VocalRange | None = None
    sentences: list[SongSentence] = []
