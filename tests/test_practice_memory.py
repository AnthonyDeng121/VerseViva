from datetime import UTC, datetime, timedelta

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
from server.services.practice.models import AcousticFinding, FindingResult
from server.services.practice.service import (
    _comparable_history,
    _has_audible_judgment,
    _has_audible_signal,
)
from server.storage.practice_store import PracticeStore


def _attempt(
    index: int,
    *,
    issue_type: LanguageIssueType | None,
    status: PracticeStatus = PracticeStatus.analyzed,
) -> PracticeAttempt:
    issues = []
    if issue_type is not None:
        issues.append(
            LanguageIssue(
                issue_id=f"issue_{index}",
                type=issue_type,
                hint_id="hint_1",
                sentence_id="sentence_1",
                word_text="want me",
                target_segments=["t"],
                confidence=0.9,
                audible_evidence=["听到独立尾音"],
            )
        )
    return PracticeAttempt(
        attempt_id=f"attempt_{index}",
        take_id=f"take_{index}",
        session_id="session_test",
        song_id="song_test",
        track_slot_id="primary:sentence_1",
        sentence_ids=["sentence_1"],
        status=status,
        issues=issues,
        target_evaluations=[TargetEvaluation(
            target_id="hint_1",
            issue_type=issue_type,
            result=TargetResult.issue_detected,
            confidence=0.9,
        )] if issue_type is not None and status == PracticeStatus.analyzed else [],
        recommendations=[],
        comparison=AttemptComparison(result=ComparisonResult.first_attempt),
        insufficient_reason="证据不足" if status == PracticeStatus.insufficient_data else None,
        acoustic_provider="gemini",
        acoustic_model="gemini-test",
        coaching_provider="glm",
        coaching_model="glm-test",
        created_at=datetime.now(UTC) + timedelta(seconds=index),
    )


def test_memory_only_aggregates_reliable_attempts(tmp_path):
    store = PracticeStore(tmp_path)
    store.save(_attempt(1, issue_type=LanguageIssueType.expected_elision_realized))
    store.save(
        _attempt(
            2,
            issue_type=LanguageIssueType.identical_consonants_separated,
            status=PracticeStatus.insufficient_data,
        )
    )
    store.save(_attempt(3, issue_type=None))

    memory = store.memory("session_test")

    assert memory.total_attempts == 3
    assert memory.reliable_attempts == 2
    assert [item.issue_type for item in memory.phenomena] == [
        LanguageIssueType.expected_elision_realized
    ]
    assert memory.phenomena[0].issue_count == 1


def test_failed_service_attempt_does_not_enter_reliable_memory(tmp_path):
    store = PracticeStore(tmp_path)
    store.save(
        _attempt(
            1,
            issue_type=None,
            status=PracticeStatus.failed,
        )
    )

    memory = store.memory("session_test")

    assert memory.total_attempts == 1
    assert memory.reliable_attempts == 0


def test_attempt_payload_round_trips_through_sqlite(tmp_path):
    store = PracticeStore(tmp_path)
    original = _attempt(1, issue_type=LanguageIssueType.coalescent_assimilation_missing)

    store.save(original)

    assert store.get_for_take(original.take_id) == original
    assert store.list_for_session("session_test", "song_test") == [original]


def test_silent_or_uncertain_recording_cannot_be_treated_as_success() -> None:
    uncertain = AcousticFinding(
        hint_id="hint_1",
        result=FindingResult.uncertain,
        confidence=0.2,
        audible_evidence=[],
    )

    assert _has_audible_judgment([]) is False
    assert _has_audible_judgment([uncertain]) is False


def test_same_target_comparison_uses_recent_reliable_judgements() -> None:
    from server.services.practice.service import _comparison

    history = [_attempt(1, issue_type=LanguageIssueType.expected_elision_realized)]
    current = [TargetEvaluation(
        target_id="hint_1",
        issue_type=LanguageIssueType.expected_elision_realized,
        result=TargetResult.reference_matched,
        confidence=0.88,
    )]

    comparison = _comparison(history, current)

    assert comparison.result == ComparisonResult.improved
    assert comparison.lookback_attempt_count == 1
    assert comparison.improved_target_ids == ["hint_1"]


def test_history_matches_same_lane_and_overlapping_sentence(tmp_path) -> None:
    from types import SimpleNamespace

    store = PracticeStore(tmp_path)
    prior = _attempt(1, issue_type=LanguageIssueType.expected_elision_realized).model_copy(
        update={
            "track_slot_id": "primary:sentence_1+sentence_2+sentence_3",
            "sentence_ids": ["sentence_1", "sentence_2", "sentence_3"],
        }
    )
    store.save(prior)
    take = SimpleNamespace(
        take_id="take_current",
        session_id="session_test",
        song_id="song_test",
        track_slot_id="primary:sentence_1+sentence_2",
        sentence_ids=["sentence_1", "sentence_2"],
    )

    assert _comparable_history(store, take) == [prior]


def test_near_silent_recording_is_rejected_before_gemini(monkeypatch, tmp_path) -> None:
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        "server.services.practice.service.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "", "max_volume: -51.5 dB"),
    )

    assert _has_audible_signal("ffmpeg", tmp_path / "silent.webm") is False
