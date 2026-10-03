from pathlib import Path

from server.pipelines.command import CommandRunner, SubprocessCommandRunner
from server.pipelines.contracts import PitchArtifacts
from server.pipelines.errors import MissingModelArtifactError


class BasicPitchAdapter:
    def __init__(
        self,
        executable: str = ".venv-pitch/bin/basic-pitch",
        runner: CommandRunner | None = None,
    ):
        self.executable = executable
        self.runner = runner or SubprocessCommandRunner()

    async def extract(self, vocal_audio: Path, output_dir: Path) -> PitchArtifacts:
        if not vocal_audio.is_file():
            raise FileNotFoundError(f"Vocal audio does not exist: {vocal_audio}")
        output_dir.mkdir(parents=True, exist_ok=True)
        await self.runner.run([self.executable, str(output_dir), str(vocal_audio)])

        base_name = f"{vocal_audio.stem}_basic_pitch"
        artifacts = PitchArtifacts(
            note_events_csv=output_dir / f"{base_name}.csv",
            midi=output_dir / f"{base_name}.mid",
            model_output_npz=output_dir / f"{base_name}.npz",
        )
        missing = [
            path.name
            for path in (
                artifacts.note_events_csv,
                artifacts.midi,
                artifacts.model_output_npz,
            )
            if not path.is_file()
        ]
        if missing:
            raise MissingModelArtifactError(
                f"Basic Pitch did not produce expected artifacts: {', '.join(missing)}"
            )
        return artifacts
