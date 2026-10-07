from copy import deepcopy

from server.models.song import (
    CharacterMark,
    LanguageHint,
    LanguageHintSource,
    LocalizedHintDetail,
    MarkPlacement,
    SegmentOperation,
    SegmentTransformation,
    SongSentence,
)
from server.services.language.models import (
    EvidenceStrength,
    LanguageCandidate,
    LanguageObservation,
    ObservationResult,
)

ACCEPTED_RESULTS = {
    ObservationResult.not_audibly_released,
    ObservationResult.linked_or_resegmented,
    ObservationResult.merged_or_assimilated,
}
CONFIDENCE_BY_STRENGTH = {
    EvidenceStrength.strong: 0.8,
    EvidenceStrength.moderate: 0.6,
    EvidenceStrength.weak: 0.35,
}


def apply_language_observations(
    sentences: list[SongSentence],
    candidates: list[LanguageCandidate],
    observations: list[LanguageObservation],
    *,
    provider: str,
    model: str,
) -> list[SongSentence]:
    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    hints_by_sentence: dict[str, list[LanguageHint]] = {}
    for observation in observations:
        candidate = candidates_by_id.get(observation.candidate_id)
        if candidate is None or observation.result not in ACCEPTED_RESULTS:
            continue
        if observation.evidence_strength == EvidenceStrength.weak:
            continue
        hint = _build_hint(candidate, observation, provider=provider, model=model)
        hints_by_sentence.setdefault(candidate.sentence_id, []).append(hint)

    updated: list[SongSentence] = []
    for sentence in sentences:
        hints = deepcopy(sentence.language_hints)
        hints.extend(hints_by_sentence.get(sentence.id, []))
        updated.append(sentence.model_copy(update={"language_hints": hints}))
    return updated


def _build_hint(
    candidate: LanguageCandidate,
    observation: LanguageObservation,
    *,
    provider: str,
    model: str,
) -> LanguageHint:
    operation, default_phenomenon, symbol, placement, action = _presentation(observation.result)
    candidate_matches_result = (
        candidate.phenomenon == "final_stop_unreleased"
        and observation.result == ObservationResult.not_audibly_released
    ) or (
        candidate.phenomenon == "liaison"
        and observation.result == ObservationResult.linked_or_resegmented
    ) or (
        candidate.phenomenon == "moraic_nasal_assimilation"
        and observation.result == ObservationResult.merged_or_assimilated
    )
    phenomenon = (
        candidate.phenomenon if candidate_matches_result else default_phenomenon
    )
    input_segments = [candidate.left_segment]
    output_segments = [candidate.left_segment]
    if observation.result == ObservationResult.linked_or_resegmented:
        input_segments.append(candidate.right_segment)
        output_segments.append(candidate.right_segment)
    elif observation.result == ObservationResult.merged_or_assimilated:
        input_segments.append(candidate.right_segment)
        output_segments = [f"{candidate.left_segment}+{candidate.right_segment}"]

    mark_start = candidate.left_end_char_index
    mark_end = (
        candidate.left_end_char_index
        if observation.result == ObservationResult.not_audibly_released
        else candidate.right_start_char_index
    )
    explanation = "；".join(observation.audible_evidence) or "模型未提供可听证据。"
    return LanguageHint(
        id=f"hint_{candidate.id}",
        language=candidate.language,
        phenomenon=phenomenon,
        transformations=[
            SegmentTransformation(
                operation=operation,
                input_segments=input_segments,
                output_segments=output_segments,
            )
        ],
        start_word_index=candidate.start_word_index,
        end_word_index=candidate.end_word_index,
        start_seconds=candidate.start_seconds,
        end_seconds=candidate.end_seconds,
        source=LanguageHintSource.llm_suggestion,
        confidence=CONFIDENCE_BY_STRENGTH[observation.evidence_strength],
        marks=[
            CharacterMark(
                symbol=symbol,
                start_char_index=mark_start,
                end_char_index=mark_end,
                placement=placement,
            )
        ],
        details=[
            LocalizedHintDetail(
                locale="zh-CN",
                explanation=explanation,
                action=(
                    candidate.learner_action
                    if candidate_matches_result and candidate.learner_action
                    else action.format(span=candidate.target_span)
                ),
            )
        ],
        canonical_pronunciation=candidate.canonical_pronunciation,
        observed_pronunciation=(
            candidate.observed_pronunciation if candidate_matches_result else None
        ),
        evidence={
            "provider": provider,
            "model": model,
            "candidateId": candidate.id,
            "boundaryKind": candidate.boundary_kind.value,
            "result": observation.result.value,
            "evidenceStrength": observation.evidence_strength.value,
            "needsHumanReview": observation.needs_human_review,
            "rejectedAlternatives": [
                alternative.model_dump(mode="json", by_alias=True)
                for alternative in observation.rejected_alternatives
            ],
        },
    )


def _presentation(
    result: ObservationResult,
) -> tuple[SegmentOperation, str, str, MarkPlacement, str]:
    if result == ObservationResult.not_audibly_released:
        return (
            SegmentOperation.unreleased,
            "not_audibly_released",
            "×",
            MarkPlacement.below,
            "练习 {span} 时不要额外弹出前一个词的词尾辅音，直接进入后词。",
        )
    if result == ObservationResult.linked_or_resegmented:
        return (
            SegmentOperation.resegment,
            "cross_word_linking",
            "‿",
            MarkPlacement.below,
            "把 {span} 放在同一口气里，让前词尾音直接承接后词起音。",
        )
    return (
        SegmentOperation.merge,
        "segment_merger_or_assimilation",
        "└─┘",
        MarkPlacement.below,
        "练习 {span} 时只做一次共享或融合后的发音动作，不要拆成两个独立动作。",
    )
