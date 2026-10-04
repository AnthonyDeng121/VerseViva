from pathlib import Path

import pytest

from server.pipelines.basic_pitch.converter import (
    convert_basic_pitch_contour,
    convert_basic_pitch_csv,
    midi_to_frequency,
)
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


def test_basic_pitch_contour_uses_real_pitch_bends() -> None:
    result = convert_basic_pitch_contour(
        DAY1_OUTPUT / "pitch" / "vocals_basic_pitch.csv",
        DAY1_OUTPUT / "pitch" / "vocals_basic_pitch.npz",
    )

    assert result.pitch_points
    assert result.pitch_points == sorted(
        result.pitch_points, key=lambda point: point.time_seconds
    )
    assert any(not point.midi.is_integer() for point in result.pitch_points)
    assert all(point.frequency_hz > 0 for point in result.pitch_points)
    assert result.summary.raw_note_count > result.summary.accepted_note_count
    assert result.summary.output_pitch_point_count == len(result.pitch_points)
    assert result.summary.source == "basic-pitch-npz-contour-with-note-events"
    assert result.summary.fallback_used is False


def test_basic_pitch_contour_filters_weak_short_notes_and_keeps_silence_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.csv"
    source.write_text(
        "start_time_s,end_time_s,pitch_midi,velocity,pitch_bend\n"
        "0.0,0.5,60,100,0,1,2\n"
        "0.6,0.65,72,120,0,0\n"
        "0.8,1.2,64,20,0,0,0\n",
        encoding="utf-8",
    )

    result = convert_basic_pitch_contour(source)

    assert len(result.notes) == 1
    assert [round(point.midi, 3) for point in result.pitch_points] == [60.0, 60.333, 60.667]
    assert result.pitch_points[0].frequency_hz == pytest.approx(midi_to_frequency(60))
    assert not any(0.5 < point.time_seconds < 1.2 for point in result.pitch_points)
    assert result.summary.rejected_note_count == 2
    assert result.summary.fallback_used is True
    assert result.summary.source == "basic-pitch-csv-decoded-bends-fallback"


def test_basic_pitch_contour_corrects_short_harmonic_octave_outlier(tmp_path: Path) -> None:
    source = tmp_path / "octave.csv"
    source.write_text(
        "start_time_s,end_time_s,pitch_midi,velocity,pitch_bend\n"
        "0.0,0.3,60,100,0,0\n"
        "0.3,0.6,61,100,0,0\n"
        "0.6,0.9,72,100,0,0\n"
        "0.9,1.2,60,100,0,0\n"
        "1.2,1.5,61,100,0,0\n",
        encoding="utf-8",
    )

    result = convert_basic_pitch_contour(source)

    assert result.summary.octave_corrections == 1
    assert max(note.midi for note in result.notes) == 61


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
