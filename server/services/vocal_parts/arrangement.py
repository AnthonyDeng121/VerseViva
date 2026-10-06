import re
from dataclasses import dataclass
from pathlib import Path

from server.models.song import (
    SongSentence,
    VocalArrangementMode,
    VocalLane,
    VocalPart,
    VocalPartTimingStatus,
)
from server.pipelines.contracts import VocalPartAnalyzer
from server.services.vocal_parts.structure import derive_structural_vocal_parts

PARENTHETICAL_CUE = re.compile(r"\([^()]+\)")


def select_arrangement_mode(lyrics: str) -> VocalArrangementMode:
    """Route provider lyrics with parenthetical cues through the dual-track branch."""

    if PARENTHETICAL_CUE.search(lyrics):
        return VocalArrangementMode.dual_track
    return VocalArrangementMode.single_track


@dataclass(slots=True)
class SingleTrackArrangementPipeline:
    async def analyze(
        self,
        *,
        vocal_audio: Path,
        duration_seconds: float,
        transcript: dict,
        sentences: list[SongSentence],
    ) -> list[VocalPart]:
        del vocal_audio, duration_seconds, transcript, sentences
        return []


@dataclass(slots=True)
class DualTrackArrangementPipeline:
    analyzer: VocalPartAnalyzer | None = None

    async def analyze(
        self,
        *,
        vocal_audio: Path,
        duration_seconds: float,
        transcript: dict,
        sentences: list[SongSentence],
    ) -> list[VocalPart]:
        parts = derive_structural_vocal_parts(sentences)
        if self.analyzer is None:
            return parts

        secondary = [part for part in parts if part.lane == VocalLane.secondary]
        if not secondary:
            return parts
        cues = [
            {
                "id": part.id,
                "lyrics": part.lyrics,
                "startSeconds": part.start_seconds,
                "endSeconds": part.end_seconds,
            }
            for part in secondary
        ]
        result = await self.analyzer.analyze(
            vocal_audio,
            duration_seconds=duration_seconds,
            transcript=transcript,
            lyric_cues=cues,
        )
        timings = {timing.cue_id: timing for timing in result.timings}
        refined: list[VocalPart] = []
        for part in parts:
            timing = timings.get(part.id)
            if timing is None or not timing.detected:
                refined.append(part)
                continue
            refined.append(
                part.model_copy(
                    update={
                        "start_seconds": timing.start_seconds,
                        "end_seconds": timing.end_seconds,
                        "timing_status": VocalPartTimingStatus.audio_model_observed,
                        "timing_confidence": timing.confidence,
                        "timing_needs_human_review": True,
                        "evidence": {
                            **part.evidence,
                            "audioInput": "demucsVocalsStem",
                            "audibleEvidence": timing.audible_evidence,
                            "limitations": result.limitations,
                        },
                    }
                )
            )
        return refined
