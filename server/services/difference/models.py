from enum import StrEnum

from pydantic import BaseModel, Field


class IssueType(StrEnum):
    pitch_high = "pitch_high"
    pitch_low = "pitch_low"
    timing_early = "timing_early"
    timing_late = "timing_late"
    long_note_early_release = "long_note_early_release"


class IssueSeverity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class DifferenceIssue(BaseModel):
    type: IssueType
    sentence_id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    severity: IssueSeverity
    avg_cents: float | None = None
    max_cents: float | None = None
    timing_offset_ms: int | None = None

