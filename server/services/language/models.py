from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class LanguageAnalysisModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class BoundaryKind(StrEnum):
    identical_consonants = "identical_consonants"
    stop_to_glide = "stop_to_glide"
    consonant_to_vowel = "consonant_to_vowel"
    rhotic_to_vowel = "rhotic_to_vowel"
    consonant_to_glide = "consonant_to_glide"
    vowel_to_vowel = "vowel_to_vowel"
    stop_before_consonant = "stop_before_consonant"
    other_boundary = "other_boundary"


class LanguageCandidate(LanguageAnalysisModel):
    id: str
    sentence_id: str
    line_index: int = Field(ge=0)
    start_word_index: int = Field(ge=0)
    end_word_index: int = Field(ge=0)
    target_span: str
    left_word: str
    right_word: str
    left_segment: str
    right_segment: str
    boundary_kind: BoundaryKind
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    left_end_char_index: int = Field(ge=0)
    right_start_char_index: int = Field(ge=0)


class ObservationResult(StrEnum):
    clearly_released = "clearly_released"
    not_audibly_released = "not_audibly_released"
    linked_or_resegmented = "linked_or_resegmented"
    merged_or_assimilated = "merged_or_assimilated"
    continuous_without_change = "continuous_without_change"
    uncertain = "uncertain"


class EvidenceStrength(StrEnum):
    strong = "strong"
    moderate = "moderate"
    weak = "weak"


class RejectedAlternative(LanguageAnalysisModel):
    result: ObservationResult
    reason: str = Field(min_length=1)


class LanguageObservation(LanguageAnalysisModel):
    candidate_id: str
    result: ObservationResult
    evidence_strength: EvidenceStrength
    audible_evidence: list[str] = Field(default_factory=list)
    rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
    needs_human_review: bool


class LanguageObservationBatch(LanguageAnalysisModel):
    lyrics_match: str
    observations: list[LanguageObservation] = Field(default_factory=list)
