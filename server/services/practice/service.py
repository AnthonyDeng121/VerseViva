from pathlib import Path
from uuid import uuid4

from server.config import Settings
from server.models.practice import (
    AttemptComparison,
    ComparisonResult,
    LanguageIssue,
    PracticeAttempt,
    PracticeStatus,
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
    previous = _previous_attempt(store, take)

    is_secondary = take.track_slot_id.startswith("secondary:")
    secondary_part = next(
        (item for item in profile.vocal_parts if item.id == take.vocal_part_id),
        None,
    )
    if is_secondary and secondary_part is None:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(previous, []),
            insufficient_reason="所选范围没有可绑定的次轨歌词，无法进行可靠语言诊断。",
        )
        store.save(attempt)
        return attempt
    if not is_secondary and not targets:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(previous, []),
            insufficient_reason="所选句子还没有可核查的语言标注目标。",
        )
        store.save(attempt)
        return attempt
    if settings.practice_acoustic_provider != "gemini" or settings.gemini_api_key is None:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(previous, []),
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
                settings.data_dir / "songs" / profile.song_id / "audio" / "vocals.wav"
            )
            if not reference_vocal_path.is_file():
                raise FileNotFoundError("参考整体人声资产不存在")
            batch = await analyzer.analyze_secondary(
                audio_path,
                reference_vocal_path,
                secondary_part,
            )
        else:
            batch = await analyzer.analyze(audio_path, sentences)
    except Exception as exc:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(previous, []),
            insufficient_reason=f"Gemini 暂时无法完成本次听感核查：{exc}",
        )
        store.save(attempt)
        return attempt

    if not batch.recording_usable:
        attempt = PracticeAttempt(
            **base,
            status=PracticeStatus.insufficient_data,
            comparison=_comparison(previous, []),
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
            comparison=_comparison(previous, []),
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
    comparison = _comparison(previous, issues)
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
        recommendations=recommendations,
        comparison=comparison,
    )
    store.save(attempt)
    return attempt


def _has_audible_judgment(findings: list[AcousticFinding]) -> bool:
    return any(item.result != FindingResult.uncertain for item in findings)


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


def _previous_attempt(store: PracticeStore, take: RecordingTake) -> PracticeAttempt | None:
    candidates = store.list_for_session(take.session_id, take.song_id)
    comparable = [item for item in candidates if item.track_slot_id == take.track_slot_id]
    return comparable[-1] if comparable else None


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
    previous: PracticeAttempt | None,
    current_issues: list[LanguageIssue],
) -> AttemptComparison:
    if previous is None or previous.status != PracticeStatus.analyzed:
        return AttemptComparison(result=ComparisonResult.first_attempt)
    old_types = {item.type for item in previous.issues}
    new_types = {item.type for item in current_issues}
    resolved = sorted(old_types - new_types, key=str)
    added = sorted(new_types - old_types, key=str)
    if resolved and not added:
        result = ComparisonResult.improved
    elif added and not resolved:
        result = ComparisonResult.regressed
    else:
        result = ComparisonResult.unchanged
    return AttemptComparison(
        previous_attempt_id=previous.attempt_id,
        result=result,
        resolved_issue_types=resolved,
        new_issue_types=added,
    )
