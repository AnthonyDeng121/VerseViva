from pathlib import Path

from server.services.practice.analyzer import GeminiPracticeAnalyzer
from server.services.practice.models import AcousticFinding, AcousticFindingBatch, FindingResult


def test_practice_analyzer_retries_gemini_file_processing_failure(monkeypatch) -> None:
    analyzer = GeminiPracticeAnalyzer(api_key="test-key", model="test-model")
    calls = 0

    def analyze_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Gemini 音频文件处理失败")
        return AcousticFindingBatch(
            recording_usable=True,
            findings=[
                AcousticFinding(
                    hint_id="hint_1",
                    result=FindingResult.reference_matched,
                    confidence=0.9,
                )
            ],
        )

    monkeypatch.setattr(analyzer, "_analyze_once", analyze_once)
    monkeypatch.setattr("server.services.practice.analyzer.time.sleep", lambda seconds: None)

    result = analyzer._analyze_sync(Path("recording.mp3"), [], None)

    assert result.recording_usable is True
    assert calls == 2


def test_practice_analyzer_retries_usable_response_without_findings(monkeypatch) -> None:
    analyzer = GeminiPracticeAnalyzer(api_key="test-key", model="test-model")
    calls = 0

    def retryable_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return AcousticFindingBatch(recording_usable=True, findings=[])
        return AcousticFindingBatch(recording_usable=False, insufficient_reason="确实无法判断")

    monkeypatch.setattr(analyzer, "_analyze_once", retryable_once)
    monkeypatch.setattr("server.services.practice.analyzer.time.sleep", lambda seconds: None)

    result = analyzer._analyze_sync(Path("recording.mp3"), [], None)

    assert result.recording_usable is False
    assert calls == 2


def test_secondary_analysis_falls_back_to_user_audio_only(monkeypatch) -> None:
    analyzer = GeminiPracticeAnalyzer(api_key="test-key", model="test-model")
    reference_modes = []

    def analyze_once(*args, use_reference):
        reference_modes.append(use_reference)
        if use_reference:
            return AcousticFindingBatch(recording_usable=True, findings=[])
        return AcousticFindingBatch(recording_usable=False, insufficient_reason="用户录音不可辨认")

    monkeypatch.setattr(analyzer, "_analyze_secondary_once", analyze_once)

    result = analyzer._analyze_secondary_sync(
        Path("recording.mp3"),
        Path("reference.mp3"),
        [],
        [],
    )

    assert result.recording_usable is False
    assert reference_modes == [True, False]
