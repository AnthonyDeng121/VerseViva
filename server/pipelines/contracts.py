from pathlib import Path
from typing import Protocol

from server.models.song import PitchPoint, SingingHints, WordTiming


class VocalSeparator(Protocol):
    async def separate(self, source: Path, output_dir: Path) -> Path: ...


class PitchExtractor(Protocol):
    async def extract(self, vocal_audio: Path) -> list[PitchPoint]: ...


class LyricsAligner(Protocol):
    async def align(self, vocal_audio: Path, lyrics: str | None) -> list[WordTiming]: ...


class EnglishCoach(Protocol):
    async def analyze(
        self, vocal_audio: Path, lyrics: str, words: list[WordTiming]
    ) -> SingingHints: ...

