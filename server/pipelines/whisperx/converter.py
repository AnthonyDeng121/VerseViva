import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from server.models.song import SongSentence, WordTiming
from server.pipelines.errors import PipelineOutputError


@dataclass(frozen=True, slots=True)
class WhisperXConversionResult:
    language: str | None
    sentences: list[SongSentence]


def convert_whisperx_json(source: Path) -> WhisperXConversionResult:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PipelineOutputError(f"Cannot read WhisperX JSON: {source}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineOutputError(f"WhisperX output is not valid JSON: {source}") from exc

    if not isinstance(payload, dict):
        raise PipelineOutputError("WhisperX output must be a JSON object")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise PipelineOutputError("WhisperX output is missing the segments list")

    sentences = [
        _convert_segment(segment, sentence_index)
        for sentence_index, segment in enumerate(raw_segments, start=1)
    ]
    language = payload.get("language")
    if language is not None and not isinstance(language, str):
        raise PipelineOutputError("WhisperX language must be a string or null")
    return WhisperXConversionResult(language=language, sentences=sentences)


def _convert_segment(segment: Any, sentence_index: int) -> SongSentence:
    if not isinstance(segment, dict):
        raise PipelineOutputError(f"WhisperX segment {sentence_index} must be an object")
    try:
        start_seconds = float(segment["start"])
        end_seconds = float(segment["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineOutputError(
            f"WhisperX segment {sentence_index} has invalid start or end time"
        ) from exc

    raw_words = segment.get("words", [])
    if not isinstance(raw_words, list):
        raise PipelineOutputError(f"WhisperX segment {sentence_index} words must be a list")
    words: list[WordTiming] = []
    for raw_word in raw_words:
        # WhisperX may keep unaligned words without timestamps. They remain in sentence text,
        # but cannot safely participate in time-based teaching and are omitted here.
        if not isinstance(raw_word, dict) or not {"word", "start", "end"} <= raw_word.keys():
            continue
        try:
            words.append(
                WordTiming(
                    id=f"word_{sentence_index:03d}_{len(words) + 1:03d}",
                    text=str(raw_word["word"]).strip(),
                    start_seconds=raw_word["start"],
                    end_seconds=raw_word["end"],
                    confidence=raw_word.get("score"),
                )
            )
        except ValidationError as exc:
            raise PipelineOutputError(
                f"WhisperX segment {sentence_index} contains an invalid aligned word"
            ) from exc

    text = str(segment.get("text", "")).strip()
    if not text:
        text = " ".join(word.text for word in words)
    try:
        return SongSentence(
            id=f"sentence_{sentence_index:03d}",
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            lyrics=text,
            words=words,
        )
    except ValidationError as exc:
        raise PipelineOutputError(
            f"WhisperX segment {sentence_index} has an invalid time interval"
        ) from exc
