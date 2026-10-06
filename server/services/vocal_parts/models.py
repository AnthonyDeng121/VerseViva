from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from server.models.song import VocalLane, VocalPartRole


class VocalPartCandidateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class VocalPartCandidate(VocalPartCandidateModel):
    id: str = Field(min_length=1)
    lane: VocalLane
    role: VocalPartRole
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    lyrics: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    audible_evidence: list[str] = Field(default_factory=list)
    matched_cue_ids: list[str] = Field(default_factory=list)
    needs_human_review: bool = True

    @model_validator(mode="after")
    def validate_interval(self) -> "VocalPartCandidate":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self


class VocalPartCandidateBatch(VocalPartCandidateModel):
    audio_duration_seconds: float = Field(ge=0)
    candidates: list[VocalPartCandidate] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_duration(self) -> "VocalPartCandidateBatch":
        if self.audio_duration_seconds <= 0:
            raise ValueError("audio_duration_seconds must be greater than zero")
        return self


class VocalCueTiming(VocalPartCandidateModel):
    cue_id: str = Field(min_length=1)
    detected: bool
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    audible_evidence: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_detected_interval(self) -> "VocalCueTiming":
        if self.detected and self.end_seconds <= self.start_seconds:
            raise ValueError("detected cue must have a positive interval")
        if not self.detected and (self.start_seconds != 0 or self.end_seconds != 0):
            raise ValueError("undetected cue must use zero timestamps")
        return self


class VocalCueTimingBatch(VocalPartCandidateModel):
    audio_duration_seconds: float = Field(ge=0)
    timings: list[VocalCueTiming] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> "VocalCueTimingBatch":
        if self.audio_duration_seconds <= 0:
            raise ValueError("audio_duration_seconds must be greater than zero")
        cue_ids = [timing.cue_id for timing in self.timings]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("cue timing IDs must be unique")
        return self
