from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PracticeModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class PracticeStatus(StrEnum):
    analyzed = "analyzed"
    insufficient_data = "insufficient_data"
    failed = "failed"


class LanguageIssueType(StrEnum):
    expected_elision_realized = "expected_elision_realized"
    identical_consonants_separated = "identical_consonants_separated"
    coalescent_assimilation_missing = "coalescent_assimilation_missing"
    target_phoneme_omitted = "target_phoneme_omitted"


class ComparisonResult(StrEnum):
    first_attempt = "first_attempt"
    improved = "improved"
    unchanged = "unchanged"
    regressed = "regressed"
    insufficient_data = "insufficient_data"


class TargetResult(StrEnum):
    issue_detected = "issue_detected"
    reference_matched = "reference_matched"


class TargetEvaluation(PracticeModel):
    """One comparable Gemini judgement for the same curated language target."""

    target_id: str
    issue_type: LanguageIssueType
    result: TargetResult
    confidence: float = Field(ge=0, le=1)


class LanguageIssue(PracticeModel):
    issue_id: str
    type: LanguageIssueType
    hint_id: str
    sentence_id: str
    word_text: str
    target_segments: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    audible_evidence: list[str] = Field(default_factory=list)


class PracticeRecommendation(PracticeModel):
    rank: int = Field(ge=1, le=3)
    issue_id: str
    headline: str
    observation: str
    action: str


class AttemptComparison(PracticeModel):
    previous_attempt_id: str | None = None
    result: ComparisonResult
    resolved_issue_types: list[LanguageIssueType] = Field(default_factory=list)
    new_issue_types: list[LanguageIssueType] = Field(default_factory=list)
    lookback_attempt_count: int = Field(default=0, ge=0, le=5)
    improved_target_ids: list[str] = Field(default_factory=list)
    unchanged_target_ids: list[str] = Field(default_factory=list)
    regressed_target_ids: list[str] = Field(default_factory=list)


class PracticeAttempt(PracticeModel):
    attempt_id: str
    take_id: str
    session_id: str
    song_id: str
    track_slot_id: str
    sentence_ids: list[str]
    status: PracticeStatus
    issues: list[LanguageIssue] = Field(default_factory=list, max_length=3)
    target_evaluations: list[TargetEvaluation] = Field(default_factory=list)
    recommendations: list[PracticeRecommendation] = Field(default_factory=list, max_length=3)
    comparison: AttemptComparison
    sentence_comparisons: dict[str, AttemptComparison] = Field(default_factory=dict)
    insufficient_reason: str | None = None
    acoustic_provider: str
    acoustic_model: str
    coaching_provider: str
    coaching_model: str
    analysis_version: str = "practice-language-v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PhenomenonMemory(PracticeModel):
    issue_type: LanguageIssueType
    reliable_attempt_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    recent_issue_count: int = Field(ge=0)
    trend: str
    last_practiced_at: datetime


class PracticeMemory(PracticeModel):
    session_id: str
    total_attempts: int = Field(ge=0)
    reliable_attempts: int = Field(ge=0)
    phenomena: list[PhenomenonMemory] = Field(default_factory=list)
    updated_at: datetime | None = None

