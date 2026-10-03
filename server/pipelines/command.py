import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from server.pipelines.errors import ModelExecutionError


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    async def run(self, command: Sequence[str], cwd: Path | None = None) -> CommandResult: ...


class SubprocessCommandRunner:
    def __init__(self, timeout_seconds: float = 7200):
        self.timeout_seconds = timeout_seconds

    async def run(self, command: Sequence[str], cwd: Path | None = None) -> CommandResult:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise ModelExecutionError(f"Cannot start model command: {command[0]}") from exc

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ModelExecutionError(
                f"Model command timed out after {self.timeout_seconds:g} seconds: {command[0]}"
            ) from exc

        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")
        if process.returncode != 0:
            detail = stderr.strip() or stdout.strip() or "No process output"
            raise ModelExecutionError(
                f"Model command failed with exit code {process.returncode}: {detail[-4000:]}"
            )
        return CommandResult(stdout=stdout, stderr=stderr)
