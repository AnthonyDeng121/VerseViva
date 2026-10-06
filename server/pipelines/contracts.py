from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from server.models.song import SongSentence
from server.services.language.models import LanguageCandidate, LanguageObservationBatch
from server.services.lyrics.models import LyricsLookupResult
from server.services.vocal_parts.models import VocalCueTimingBatch


@dataclass(frozen=True, slots=True)
class SeparationArtifacts:
    vocals: Path
    accompaniment: Path


@dataclass(frozen=True, slots=True)
class AlignmentArtifacts:
    alignment_json: Path


class VocalSeparator(Protocol):
    async def separate(self, source: Path, output_dir: Path) -> SeparationArtifacts: ...


class LyricsAligner(Protocol):
    async def align(
        self,
        vocal_audio: Path,
        output_dir: Path,
        language: str | None = None,
    ) -> AlignmentArtifacts: ...


class LyricsProvider(Protocol):
    provider: str

    async def find(
        self, *, title: str, artist: str | None, duration_seconds: float | None
    ) -> LyricsLookupResult | None: ...


class LanguageCoach(Protocol):
    provider: str
    model: str

    async def analyze(
        self,
        vocal_audio: Path,
        lyrics: str,
        sentences: list[SongSentence],
        candidates: list[LanguageCandidate],
    ) -> LanguageObservationBatch: ...


class VocalPartAnalyzer(Protocol):
    provider: str
    model: str

    async def analyze(
        self,
        vocal_audio: Path,
        *,
        duration_seconds: float,
        transcript: dict,
        lyric_cues: list[dict],
    ) -> VocalCueTimingBatch: ...
