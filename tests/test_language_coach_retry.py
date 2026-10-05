from pathlib import Path

from server.pipelines.language_coach import GeminiLanguageCoach
from server.services.language import LanguageObservationBatch


def test_gemini_retries_transient_service_errors(monkeypatch) -> None:
    coach = GeminiLanguageCoach(api_key="test-key")
    calls = 0

    def analyze_once(*args):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("503 service_unavailable: high demand")
        return LanguageObservationBatch(lyrics_match="match", observations=[])

    monkeypatch.setattr(coach, "_analyze_once", analyze_once)
    monkeypatch.setattr("server.pipelines.language_coach.time.sleep", lambda seconds: None)

    result = coach._analyze_sync(Path("vocals.wav"), "lyrics", [], [])

    assert result.lyrics_match == "match"
    assert calls == 3
