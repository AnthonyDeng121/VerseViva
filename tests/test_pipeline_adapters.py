import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from server.pipelines.basic_pitch import BasicPitchAdapter
from server.pipelines.command import CommandResult
from server.pipelines.demucs import DemucsAdapter
from server.pipelines.errors import MissingModelArtifactError
from server.pipelines.whisperx import WhisperXAdapter


class FakeCommandRunner:
    def __init__(self, create_artifacts: Callable[[Sequence[str]], None] | None = None):
        self.create_artifacts = create_artifacts
        self.commands: list[list[str]] = []

    async def run(
        self, command: Sequence[str], cwd: Path | None = None
    ) -> CommandResult:
        self.commands.append(list(command))
        if self.create_artifacts:
            self.create_artifacts(command)
        return CommandResult(stdout="ok", stderr="")


def test_demucs_adapter_runs_model_and_returns_stems(tmp_path: Path) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"audio")
    output_dir = tmp_path / "separation"

    def create_artifacts(_: Sequence[str]) -> None:
        model_dir = output_dir / "htdemucs" / "source"
        model_dir.mkdir(parents=True)
        (model_dir / "vocals.wav").write_bytes(b"vocals")
        (model_dir / "no_vocals.wav").write_bytes(b"music")

    runner = FakeCommandRunner(create_artifacts)
    result = asyncio.run(DemucsAdapter(runner=runner).separate(source, output_dir))

    assert result.vocals.name == "vocals.wav"
    assert result.accompaniment.name == "no_vocals.wav"
    assert runner.commands[0][-1] == str(source)
    assert "--two-stems" in runner.commands[0]
    assert "htdemucs" in runner.commands[0]


def test_basic_pitch_adapter_returns_all_three_artifacts(tmp_path: Path) -> None:
    vocal_audio = tmp_path / "vocals.wav"
    vocal_audio.write_bytes(b"audio")
    output_dir = tmp_path / "pitch"

    def create_artifacts(_: Sequence[str]) -> None:
        for suffix in (".csv", ".mid", ".npz"):
            (output_dir / f"vocals_basic_pitch{suffix}").write_bytes(b"result")

    runner = FakeCommandRunner(create_artifacts)
    result = asyncio.run(BasicPitchAdapter(runner=runner).extract(vocal_audio, output_dir))

    assert result.note_events_csv.name == "vocals_basic_pitch.csv"
    assert result.midi.name == "vocals_basic_pitch.mid"
    assert result.model_output_npz.name == "vocals_basic_pitch.npz"
    assert runner.commands[0][1:] == [str(output_dir), str(vocal_audio)]


def test_whisperx_adapter_supports_language_hint(tmp_path: Path) -> None:
    vocal_audio = tmp_path / "vocals.wav"
    vocal_audio.write_bytes(b"audio")
    output_dir = tmp_path / "alignment"

    def create_artifacts(_: Sequence[str]) -> None:
        (output_dir / "vocals.json").write_text("{}", encoding="utf-8")

    runner = FakeCommandRunner(create_artifacts)
    result = asyncio.run(
        WhisperXAdapter(runner=runner).align(vocal_audio, output_dir, language="en")
    )

    assert result.alignment_json.name == "vocals.json"
    assert runner.commands[0][-2:] == ["--language", "en"]
    assert "--output_format" in runner.commands[0]


def test_adapter_rejects_missing_expected_artifacts(tmp_path: Path) -> None:
    vocal_audio = tmp_path / "vocals.wav"
    vocal_audio.write_bytes(b"audio")

    with pytest.raises(MissingModelArtifactError):
        asyncio.run(
            BasicPitchAdapter(runner=FakeCommandRunner()).extract(
                vocal_audio, tmp_path / "pitch"
            )
        )
