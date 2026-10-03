from pathlib import Path

from server.pipelines.command import CommandRunner, SubprocessCommandRunner
from server.pipelines.contracts import SeparationArtifacts
from server.pipelines.errors import MissingModelArtifactError


class DemucsAdapter:
    def __init__(
        self,
        executable: str = ".venv-demucs/bin/demucs",
        model_name: str = "htdemucs",
        runner: CommandRunner | None = None,
    ):
        self.executable = executable
        self.model_name = model_name
        self.runner = runner or SubprocessCommandRunner()

    async def separate(self, source: Path, output_dir: Path) -> SeparationArtifacts:
        if not source.is_file():
            raise FileNotFoundError(f"Source audio does not exist: {source}")
        output_dir.mkdir(parents=True, exist_ok=True)
        await self.runner.run(
            [
                self.executable,
                "--two-stems",
                "vocals",
                "--name",
                self.model_name,
                "--out",
                str(output_dir),
                str(source),
            ]
        )

        model_dir = output_dir / self.model_name / source.stem
        vocals = model_dir / "vocals.wav"
        accompaniment = model_dir / "no_vocals.wav"
        missing = [path.name for path in (vocals, accompaniment) if not path.is_file()]
        if missing:
            raise MissingModelArtifactError(
                f"Demucs did not produce expected artifacts: {', '.join(missing)}"
            )
        return SeparationArtifacts(vocals=vocals, accompaniment=accompaniment)
