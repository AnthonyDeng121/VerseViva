from pathlib import Path

from server.services.practice.analyzer import GeminiPracticeAnalyzer
from server.services.practice.models import AcousticFindingBatch


def test_practice_analyzer_retries_gemini_file_processing_failure(monkeypatch) -> None:
    analyzer = GeminiPracticeAnalyzer(api_key="test-key", model="test-model")
    calls = 0

    def analyze_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Gemini 音频文件处理失败")
        return AcousticFindingBatch(recording_usable=True, findings=[])

    monkeypatch.setattr(analyzer, "_analyze_once", analyze_once)
    monkeypatch.setattr("server.services.practice.analyzer.time.sleep", lambda seconds: None)

    result = analyzer._analyze_sync(Path("recording.mp3"), [], None)

    assert result.recording_usable is True
    assert calls == 2
