import json
from pathlib import Path
from typing import Any

from server.services.vocal_parts.models import VocalPartCandidateBatch


class GeminiVocalPartAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.api_key = api_key
        self.model = model

    def analyze(
        self,
        audio_path: Path,
        *,
        duration_seconds: float,
        transcript: dict[str, Any],
        lyric_cues: list[dict[str, Any]],
    ) -> VocalPartCandidateBatch:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Vocal Part analysis requires google-genai") from exc

        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )
        uploaded = client.files.upload(file=str(audio_path))
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[uploaded, _build_prompt(duration_seconds, transcript, lyric_cues)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_gemini_schema(VocalPartCandidateBatch.model_json_schema()),
                ),
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty Vocal Part response")
            batch = VocalPartCandidateBatch.model_validate_json(response.text)
            candidates = [
                candidate
                for candidate in batch.candidates
                if candidate.end_seconds <= duration_seconds + 0.05
            ]
            return batch.model_copy(
                update={
                    "audio_duration_seconds": duration_seconds,
                    "candidates": candidates,
                }
            )
        finally:
            name = getattr(uploaded, "name", None)
            if name:
                try:
                    client.files.delete(name=name)
                except Exception:
                    pass


def _build_prompt(
    duration_seconds: float,
    transcript: dict[str, Any],
    lyric_cues: list[dict[str, Any]],
) -> str:
    transcript_segments = [
        {
            "startSeconds": segment.get("start"),
            "endSeconds": segment.get("end"),
            "text": segment.get("text"),
        }
        for segment in transcript.get("segments", [])
    ]
    return f"""
你正在为 VerseViva 标注一段歌曲中的 Vocal Parts。请直接听音频，识别 primary 主唱和与其同时出现的
secondary harmony / backing vocal / response / ad-lib / double / overlap。

规则：
- 时间必须相对于当前 {duration_seconds:.3f} 秒音频片段，从 0 秒开始。
- primary 和 secondary 应拆成可练习的短乐句；同一时刻允许超过两个候选。
- LYRIC_CUES 是歌词排版候选，不是音频事实。只有确实听到时才能采用，并在 matchedCueIds 中引用。
- ASR_TRANSCRIPT 只用于粗定位，可能漏掉较弱声部或听错单词。
- audibleEvidence 只描述实际听到的声部进入、重叠、重复或音色位置，不得虚构频谱数值。
- 所有输出都仍需人工复核，所以 needsHumanReview 必须为 true。
- 无法可靠听清的歌词不要猜；可以缩短区间或降低 confidence。
- 不要声称已经得到独立 stem。

ASR_TRANSCRIPT:
{json.dumps(transcript_segments, ensure_ascii=False)}

LYRIC_CUES:
{json.dumps(lyric_cues, ensure_ascii=False)}
""".strip()


def _gemini_schema(value: Any) -> Any:
    """Remove JSON Schema keywords unsupported by Gemini's Schema subset."""

    if isinstance(value, dict):
        return {
            key: _gemini_schema(item)
            for key, item in value.items()
            if key not in {"additionalProperties", "title"}
        }
    if isinstance(value, list):
        return [_gemini_schema(item) for item in value]
    return value
