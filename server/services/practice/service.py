import re
from pathlib import Path
from uuid import uuid4

from server.config import Settings
from server.models.practice import (
    AttemptComparison,
    ComparisonResult,
    LanguageIssue,
    LanguageIssueType,
    PracticeAttempt,
    PracticeStatus,
    TargetEvaluation,
    TargetResult,
)
from server.models.recording import RecordingTake
from server.models.song import SongProfile, SongSentence, VocalPart
from server.services.practice.analyzer import (
    GeminiPracticeAnalyzer,
    issue_type_for_hint,
    secondary_target_id,
)
from server.services.practice.coach import GlmPracticeCoach
from server.services.practice.models import AcousticFinding, FindingResult
from server.storage.practice_store import PracticeStore


async def analyze_practice_take(
    settings: Settings,
    take: RecordingTake,
    profile: SongProfile,
    audio_path: Path,
) -> PracticeAttempt:
    store = PracticeStore(settings.data_dir)
    existing = store.get_for_take(take.take_id)
    if existing is not None and existing.status == PracticeStatus.analyzed:
        return existing

    sentences = [item for item in profile.sentences if item.id in take.sentence_ids]
    selected_part = next(
        (item for item in profile.vocal_parts if item.id == take.vocal_part_id),
        None,
    )
    if selected_part is not None and selected_part.lane.value == "primary":
        sentences = [_primary_only_sentence(item) for item in sentences]
    targets = [
        hint
        for sentence in sentences
        for hint in sentence.language_hints
        if issue_type_for_hint(hint) is not None
    ]
    base = {
        "attempt_id": f"attempt_{uuid4().hex}",
        "take_id": take.take_id,
        "session_id": take.session_id,
        "song_id": take.song_id,
        "track_slot_id": take.track_slot_id,
        "sentence_ids": take.sentence_ids,
        "acoustic_provider": settings.practice_acoustic_provider,
        "acoustic_model": settings.gemini_model,
        "coaching_provider": "glm" if settings.glm_api_key else "template_fallback",
        "coaching_model": settings.glm_model if settings.glm_api_key else "rules-v1",
    }
    history = _comparable_history(store, take)

    is_secondary = take.track_slot_id.startswith("secondary:")
    secondary_part = next(
        (item for item in profile.vocal_parts if item.id == take.vocal_part_id),
        None,
    )
    if is_secondary and secondary_part is None:
        secondary_part = next(
            (
                item
                for item in profile.vocal_parts
                if item.lane.value == "secondary"
                and item.start_seconds < take.selection_end_seconds
                and item.end_seconds > take.selection_start_seconds
            ),
            None,
        )
    if is_secondary and secondary_part is None:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason="所选范围没有可绑定的次轨歌词，无法进行可靠语言诊断。",
        )
        store.save(attempt)
        return attempt
    if not is_secondary and not targets:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason="所选句子还没有可核查的语言标注目标。",
        )
        store.save(attempt)
        return attempt
    if settings.practice_acoustic_provider != "gemini" or settings.gemini_api_key is None:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason="练唱声学分析尚未配置 Gemini API Key。",
        )
        store.save(attempt)
        return attempt

    analyzer = GeminiPracticeAnalyzer(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_model,
    )
    try:
        if is_secondary and secondary_part is not None:
            reference_vocal_path = (
                settings.data_dir / "songs" / profile.song_id / "audio" / "vocals.mp3"
            )
            if not reference_vocal_path.is_file():
                reference_vocal_path = reference_vocal_path.with_suffix(".wav")
            if not reference_vocal_path.is_file():
                raise FileNotFoundError("参考整体人声资产不存在")
            batch = await analyzer.analyze_secondary(
                audio_path,
                reference_vocal_path,
                secondary_part,
            )
        else:
            reference_vocal_path = (
                settings.data_dir / "songs" / profile.song_id / "audio" / "vocals.mp3"
            )
            if not reference_vocal_path.is_file():
                reference_vocal_path = reference_vocal_path.with_suffix(".wav")
            batch = await analyzer.analyze(
                audio_path,
                sentences,
                reference_vocal_path if reference_vocal_path.is_file() else None,
            )
    except Exception as exc:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason=f"Gemini 暂时无法完成本次听感核查：{exc}",
        )
        store.save(attempt)
        return attempt

    if not batch.recording_usable:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason=batch.insufficient_reason or "本次录音不足以可靠判断。",
        )
        store.save(attempt)
        return attempt

    # A usable singing take must contain at least one audible target judgement.
    # Empty findings previously fell through to "no issues" and were incorrectly
    # presented as a successful attempt, including for silent recordings.
    if not _has_audible_judgment(batch.findings):
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(history, []),
            insufficient_reason="未听到足够的演唱内容，无法判断语言动作，请重新录制。",
        )
        store.save(attempt)
        return attempt

    issues = (
        _build_secondary_issues(
            secondary_part,
            batch.findings,
            take.sentence_ids,
            settings.practice_issue_confidence_threshold,
        )
        if is_secondary and secondary_part is not None
        else _build_issues(
            sentences,
            batch.findings,
            settings.practice_issue_confidence_threshold,
        )
    )
    target_types = (
        {
            secondary_target_id(secondary_part.id, issue_type): issue_type
            for issue_type in LanguageIssueType
        }
        if is_secondary and secondary_part is not None
        else {
            hint.id: issue_type_for_hint(hint)
            for sentence in sentences
            for hint in sentence.language_hints
            if issue_type_for_hint(hint) is not None
        }
    )
    evaluations = _build_target_evaluations(batch.findings, target_types)
    comparison = _comparison(history, evaluations)
    coach = GlmPracticeCoach(
        settings.glm_api_key.get_secret_value() if settings.glm_api_key else None,
        settings.glm_model,
        settings.glm_base_url,
        settings.glm_timeout_seconds,
    )
    recommendations = await coach.recommend(issues, store.memory(take.session_id))
    attempt = PracticeAttempt(
        **base,
        status=PracticeStatus.analyzed,
        issues=issues,
        target_evaluations=evaluations,
        recommendations=recommendations,
        comparison=comparison,
    )
    store.save(attempt)
    return attempt


def _has_audible_judgment(findings: list[AcousticFinding]) -> bool:
    return any(item.result != FindingResult.uncertain for item in findings)


def _primary_only_sentence(sentence: SongSentence) -> SongSentence:
    parenthetical_ranges = [match.span() for match in re.finditer(r"\([^)]*\)", sentence.lyrics)]
    hints = [
        hint
        for hint in sentence.language_hints
        if not any(
            start <= mark.start_char_index < end
            for mark in hint.marks
            for start, end in parenthetical_ranges
        )
    ]
    lyrics = re.sub(r"\s*\([^)]*\)", "", sentence.lyrics).strip()
    return sentence.model_copy(update={"lyrics": lyrics, "language_hints": hints})


def _build_issues(
    sentences: list[SongSentence],
    findings: list,
    threshold: float,
) -> list[LanguageIssue]:
    target_map = {
        hint.id: (sentence, hint)
        for sentence in sentences
        for hint in sentence.language_hints
        if issue_type_for_hint(hint) is not None
    }
    issues = []
    for finding in findings:
        target = target_map.get(finding.hint_id)
        if (
            target is None
            or finding.result != FindingResult.issue_detected
            or finding.confidence < threshold
        ):
            continue
        sentence, hint = target
        expected_type = issue_type_for_hint(hint)
        if expected_type is None or finding.issue_type != expected_type:
            continue
        words = sentence.words[hint.start_word_index : hint.end_word_index + 1]
        segments = [
            segment
            for transformation in hint.transformations
            for segment in transformation.input_segments
        ]
        issues.append(
            LanguageIssue(
                issue_id=f"issue_{uuid4().hex}",
                type=expected_type,
                hint_id=hint.id,
                sentence_id=sentence.id,
                word_text=" ".join(item.text for item in words),
                target_segments=segments,
                confidence=finding.confidence,
                audible_evidence=finding.audible_evidence,
            )
        )
    return sorted(issues, key=lambda item: item.confidence, reverse=True)[:3]


def _comparable_history(store: PracticeStore, take: RecordingTake) -> list[PracticeAttempt]:
    candidates = store.list_for_session(take.session_id, take.song_id)
    comparable = [
        item
        for item in candidates
        if item.track_slot_id == take.track_slot_id and item.status == PracticeStatus.analyzed
    ]
    return comparable[-5:]


def _build_target_evaluations(
    findings: list[AcousticFinding],
    target_types: dict[str, LanguageIssueType],
) -> list[TargetEvaluation]:
    evaluations = []
    for finding in findings:
        issue_type = finding.issue_type or target_types.get(finding.hint_id)
        if finding.result == FindingResult.uncertain or issue_type is None:
            continue
        evaluations.append(
            TargetEvaluation(
                target_id=finding.hint_id,
                issue_type=issue_type,
                result=TargetResult(finding.result.value),
                confidence=finding.confidence,
            )
        )
    return evaluations


def _build_secondary_issues(
    vocal_part: VocalPart,
    findings: list,
    sentence_ids: list[str],
    threshold: float,
) -> list[LanguageIssue]:
    issues = []
    for finding in findings:
        if (
            finding.result != FindingResult.issue_detected
            or finding.issue_type is None
            or finding.confidence < threshold
            or finding.hint_id != secondary_target_id(vocal_part.id, finding.issue_type)
        ):
            continue
        issues.append(
            LanguageIssue(
                issue_id=f"issue_{uuid4().hex}",
                type=finding.issue_type,
                hint_id=finding.hint_id,
                sentence_id=sentence_ids[0],
                word_text=vocal_part.lyrics,
                target_segments=[],
                confidence=finding.confidence,
                audible_evidence=finding.audible_evidence,
            )
        )
    return sorted(issues, key=lambda item: item.confidence, reverse=True)[:3]


def _comparison(
    history: list[PracticeAttempt],
    current: list[TargetEvaluation],
) -> AttemptComparison:
    if not history:
        return AttemptComparison(result=ComparisonResult.first_attempt)
    previous = history[-1]
    old_types = {item.type for item in previous.issues}
    new_types = {
        item.issue_type for item in current if item.result == TargetResult.issue_detected
    }
    resolved = sorted(old_types - new_types, key=str)
    added = sorted(new_types - old_types, key=str)
    improved_targets = []
    unchanged_targets = []
    regressed_targets = []
    for evaluation in current:
        prior = [
            item
            for attempt in history
            for item in attempt.target_evaluations
            if item.target_id == evaluation.target_id
        ]
        if not prior:
            continue
        issue_weight = sum(
            item.confidence for item in prior if item.result == TargetResult.issue_detected
        )
        matched_weight = sum(
            item.confidence for item in prior if item.result == TargetResult.reference_matched
        )
        prior_result = (
            TargetResult.issue_detected
            if issue_weight >= matched_weight
            else TargetResult.reference_matched
        )
        if (
            prior_result == TargetResult.issue_detected
            and evaluation.result == TargetResult.reference_matched
        ):
            improved_targets.append(evaluation.target_id)
        elif (
            prior_result == TargetResult.reference_matched
            and evaluation.result == TargetResult.issue_detected
        ):
            regressed_targets.append(evaluation.target_id)
        else:
            unchanged_targets.append(evaluation.target_id)
    if not improved_targets and not regressed_targets and not unchanged_targets:
        result = ComparisonResult.first_attempt
    elif improved_targets and not regressed_targets:
        result = ComparisonResult.improved
    elif regressed_targets and not improved_targets:
        result = ComparisonResult.regressed
    else:
        result = ComparisonResult.unchanged
    return AttemptComparison(
        previous_attempt_id=previous.attempt_id,
        result=result,
        resolved_issue_types=resolved,
        new_issue_types=added,
        lookback_attempt_count=len(history),
        improved_target_ids=improved_targets,
        unchanged_target_ids=unchanged_targets,
        regressed_target_ids=regressed_targets,
    )
