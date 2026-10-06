import asyncio
import json
from pathlib import Path

from server.config import get_settings
from server.services.vocal_parts import GeminiVocalPartAnalyzer


def analyze_day3_vocal_parts(project_root: Path) -> Path:
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise RuntimeError("VERSEVIVA_GEMINI_API_KEY is required")

    day3_dir = project_root / "data" / "day3"
    audio_path = (
        day3_dir / "output" / "demucs" / "htdemucs" / "get him back!" / "vocals.wav"
    )
    transcript_path = day3_dir / "output" / "whisperx" / "get him back!.json"
    cues_path = project_root / "server" / "fixtures" / "get-him-back-vocal-cues.json"
    missing = [path for path in (audio_path, transcript_path, cues_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing Day 3 Demucs vocals/transcript/cues: " + ", ".join(map(str, missing))
        )

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    lyric_cues = [
        cue
        for cue in json.loads(cues_path.read_text(encoding="utf-8"))["cues"]
        if cue["lane"] == "secondary"
    ]
    analyzer = GeminiVocalPartAnalyzer(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
    )
    result = asyncio.run(
        analyzer.analyze(
            audio_path,
            duration_seconds=36.340893,
            transcript=transcript,
            lyric_cues=lyric_cues,
        )
    )
    destination = day3_dir / "output" / "vocal-parts" / "gemini-cue-timings.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    destination = analyze_day3_vocal_parts(project_root)
    print(f"Created {destination}")


if __name__ == "__main__":
    main()
