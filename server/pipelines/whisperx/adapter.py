from pathlib import Path

from server.pipelines.command import CommandRunner, SubprocessCommandRunner
from server.pipelines.contracts import AlignmentArtifacts
from server.pipelines.errors import MissingModelArtifactError


class WhisperXAdapter:
    def __init__(
        self,
        executable: str = ".venv-whisperx/bin/whisperx",
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        runner: CommandRunner | None = None,
    ):
        self.executable = executable
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.runner = runner or SubprocessCommandRunner()

    async def align(
        self,
        vocal_audio: Path,
        output_dir: Path,
        language: str | None = None,
    ) -> AlignmentArtifacts:
        if not vocal_audio.is_file():
            raise FileNotFoundError(f"Vocal audio does not exist: {vocal_audio}")
        output_dir.mkdir(parents=True, exist_ok=True)
        alignment_json = output_dir / f"{vocal_audio.stem}.json"
        if alignment_json.is_file() and alignment_json.stat().st_size > 0:
            return AlignmentArtifacts(alignment_json=alignment_json)
        command = [
            self.executable,
            str(vocal_audio),
            "--model",
            self.model_name,
            "--device",
            self.device,
            "--compute_type",
            self.compute_type,
            "--output_format",
            "json",
            "--output_dir",
            str(output_dir),
        ]
        if language:
            command.extend(["--language", language])
        await self.runner.run(command)

        if not alignment_json.is_file():
            raise MissingModelArtifactError(
                f"WhisperX did not produce expected artifact: {alignment_json.name}"
            )
        return AlignmentArtifacts(alignment_json=alignment_json)
