from pathlib import Path
from typing import Protocol

from server.pipelines.command import CommandRunner, SubprocessCommandRunner
from server.pipelines.errors import PipelineOutputError


class AudioDurationProbe(Protocol):
    async def duration_seconds(self, source: Path) -> float: ...


class FfprobeAudioDurationProbe:
    def __init__(
        self,
        executable: str = "ffprobe",
        runner: CommandRunner | None = None,
    ):
        self.executable = executable
        self.runner = runner or SubprocessCommandRunner(timeout_seconds=60)

    async def duration_seconds(self, source: Path) -> float:
        result = await self.runner.run(
            [
                self.executable,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ]
        )
        try:
            duration = float(result.stdout.strip())
        except ValueError as exc:
            raise PipelineOutputError("ffprobe returned an invalid audio duration") from exc
        if duration <= 0:
            raise PipelineOutputError("Audio duration must be greater than zero")
        return duration
