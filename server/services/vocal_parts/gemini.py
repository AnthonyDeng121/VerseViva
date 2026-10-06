import asyncio
import json
from pathlib import Path
from typing import Any

from server.services.vocal_parts.models import VocalCueTimingBatch


class GeminiVocalPartAnalyzer:
    provider = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.api_key = api_key
        self.model = model

    async def analyze(
        self,
        audio_path: Path,
        *,
        duration_seconds: float,
        transcript: dict[str, Any],
        lyric_cues: list[dict[str, Any]],
    ) -> VocalCueTimingBatch:
        return await asyncio.to_thread(
            self._analyze_sync,
            audio_path,
            duration_seconds=duration_seconds,
            transcript=transcript,
            lyric_cues=lyric_cues,
        )

    def _analyze_sync(
        self,
        audio_path: Path,
        *,
        duration_seconds: float,
        transcript: dict[str, Any],
        lyric_cues: list[dict[str, Any]],
    ) -> VocalCueTimingBatch:
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
                    response_schema=_gemini_schema(VocalCueTimingBatch.model_json_schema()),
                ),
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty Vocal Part response")
            batch = VocalCueTimingBatch.model_validate_json(response.text)
            known_ids = {str(cue["id"]) for cue in lyric_cues}
            timings = [
                timing
                for timing in batch.timings
                if timing.cue_id in known_ids
                and (not timing.detected or timing.end_seconds <= duration_seconds + 0.05)
            ]
            return batch.model_copy(
                update={
                    "audio_duration_seconds": duration_seconds,
                    "timings": timings,
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
你正在为 VerseViva 定位已知的叠唱歌词。LYRIC_CUES 已经由歌词网站确定为 secondary 文本；
你只负责直接听音频，确定每个 cueId 对应的声音是否出现，以及出现时的起止时间。

规则：
- 时间必须相对于当前 {duration_seconds:.3f} 秒音频片段，从 0 秒开始。
- 对 LYRIC_CUES 中每个 cueId 恰好返回一条 timing，不得新增、遗漏或改写 cue。
- 不返回歌词文本、lane 或 role；这些由结构化歌词决定。
- 听到叠唱时 detected=true，并返回该句 secondary 的开始和结束。
- 无法可靠定位时 detected=false，startSeconds 和 endSeconds 都返回 0，不得猜测。
- ASR_TRANSCRIPT 只用于粗定位，可能漏掉较弱声部或听错单词。
- audibleEvidence 只描述实际听到的叠唱进入、退出或重叠听感，不得虚构频谱数值。
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
