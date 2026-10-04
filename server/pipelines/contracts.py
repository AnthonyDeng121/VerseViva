from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from server.models.song import LanguageHint, WordTiming


@dataclass(frozen=True, slots=True)
class SeparationArtifacts:
    vocals: Path
    accompaniment: Path


@dataclass(frozen=True, slots=True)
class PitchArtifacts:
    note_events_csv: Path
    midi: Path
    model_output_npz: Path


@dataclass(frozen=True, slots=True)
class AlignmentArtifacts:
    alignment_json: Path


class VocalSeparator(Protocol):
    async def separate(self, source: Path, output_dir: Path) -> SeparationArtifacts: ...


class PitchExtractor(Protocol):
    async def extract(self, vocal_audio: Path, output_dir: Path) -> PitchArtifacts: ...


class LyricsAligner(Protocol):
    async def align(
        self,
        vocal_audio: Path,
        output_dir: Path,
        language: str | None = None,
    ) -> AlignmentArtifacts: ...


class LanguageCoach(Protocol):
    async def analyze(
        self, vocal_audio: Path, lyrics: str, words: list[WordTiming]
    ) -> list[LanguageHint]: ...
