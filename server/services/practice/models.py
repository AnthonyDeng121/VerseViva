from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from server.models.practice import LanguageIssueType


class PracticeServiceModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class FindingResult(StrEnum):
    issue_detected = "issue_detected"
    reference_matched = "reference_matched"
    uncertain = "uncertain"


class AcousticFinding(PracticeServiceModel):
    hint_id: str
    result: FindingResult
    issue_type: LanguageIssueType | None = None
    confidence: float = Field(ge=0, le=1)
    audible_evidence: list[str] = Field(default_factory=list, max_length=3)


class AcousticFindingBatch(PracticeServiceModel):
    recording_usable: bool
    insufficient_reason: str | None = None
    findings: list[AcousticFinding] = Field(default_factory=list)


class CoachingDraft(PracticeServiceModel):
    issue_id: str
    headline: str = Field(min_length=1, max_length=40)
    observation: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=120)


class CoachingDraftBatch(PracticeServiceModel):
    recommendations: list[CoachingDraft] = Field(min_length=1, max_length=3)
