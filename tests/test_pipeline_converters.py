from pathlib import Path

import pytest

from server.pipelines.basic_pitch.converter import convert_basic_pitch_csv
from server.pipelines.errors import PipelineOutputError
from server.pipelines.whisperx.converter import convert_whisperx_json

ROOT = Path(__file__).resolve().parents[1]
DAY1_OUTPUT = ROOT / "data" / "day1" / "output"


def test_basic_pitch_converter_handles_real_variable_length_pitch_bends() -> None:
    notes = convert_basic_pitch_csv(DAY1_OUTPUT / "pitch" / "vocals_basic_pitch.csv")

    assert notes
    assert notes == sorted(
        notes,
        key=lambda note: (note.start_seconds, note.end_seconds, note.midi),
    )
    assert notes[0].id == "note_0001"
    assert all(0 <= note.confidence <= 1 for note in notes)
    assert all(note.note_name for note in notes)


def test_whisperx_converter_handles_real_day1_alignment() -> None:
    result = convert_whisperx_json(DAY1_OUTPUT / "whisperx" / "vocals.json")

    assert result.language == "en"
    assert len(result.sentences) == 4
    assert sum(len(sentence.words) for sentence in result.sentences) == 96
    assert result.sentences[0].id == "sentence_001"
    assert result.sentences[0].words[0].id == "word_001_001"


def test_whisperx_converter_omits_words_without_timestamps(tmp_path: Path) -> None:
    source = tmp_path / "alignment.json"
    source.write_text(
        '{"language":"en","segments":[{"start":0,"end":1,"text":"hello world",'
        '"words":[{"word":"hello"},{"word":"world","start":0.5,"end":1}]}]}',
        encoding="utf-8",
    )

    result = convert_whisperx_json(source)

    assert result.sentences[0].lyrics == "hello world"
    assert [word.text for word in result.sentences[0].words] == ["world"]


@pytest.mark.parametrize(
    ("converter", "filename"),
    [(convert_basic_pitch_csv, "bad.csv"), (convert_whisperx_json, "bad.json")],
)
def test_converters_report_invalid_model_outputs(converter, filename: str, tmp_path: Path) -> None:
    source = tmp_path / filename
    source.write_text("not valid model output", encoding="utf-8")

    with pytest.raises(PipelineOutputError):
        converter(source)
