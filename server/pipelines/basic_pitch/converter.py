import csv
from pathlib import Path

from server.models.song import Note
from server.pipelines.errors import PipelineOutputError

EXPECTED_COLUMNS = ("start_time_s", "end_time_s", "pitch_midi", "velocity")
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_to_note_name(midi: int) -> str:
    if not 0 <= midi <= 127:
        raise PipelineOutputError(f"MIDI pitch is outside 0-127: {midi}")
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def convert_basic_pitch_csv(source: Path) -> list[Note]:
    """Convert Basic Pitch note events; variable-length pitch bends are intentionally ignored."""

    try:
        with source.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = csv.reader(csv_file)
            header = next(rows, None)
            if header is None or tuple(header[:4]) != EXPECTED_COLUMNS:
                raise PipelineOutputError("Basic Pitch CSV has an unsupported header")

            converted: list[tuple[float, float, int, int]] = []
            for line_number, row in enumerate(rows, start=2):
                if not row or not any(value.strip() for value in row):
                    continue
                if len(row) < 4:
                    raise PipelineOutputError(
                        f"Basic Pitch CSV row {line_number} has fewer than four columns"
                    )
                try:
                    start_seconds = float(row[0])
                    end_seconds = float(row[1])
                    midi_value = float(row[2])
                    velocity = int(row[3])
                except ValueError as exc:
                    raise PipelineOutputError(
                        f"Basic Pitch CSV row {line_number} contains a non-numeric value"
                    ) from exc

                if not midi_value.is_integer():
                    raise PipelineOutputError(
                        f"Basic Pitch CSV row {line_number} has a non-integer MIDI pitch"
                    )
                midi = int(midi_value)
                if end_seconds < start_seconds:
                    raise PipelineOutputError(
                        f"Basic Pitch CSV row {line_number} ends before it starts"
                    )
                if not 0 <= velocity <= 127:
                    raise PipelineOutputError(
                        f"Basic Pitch CSV row {line_number} has velocity outside 0-127"
                    )
                midi_to_note_name(midi)
                converted.append((start_seconds, end_seconds, midi, velocity))
    except OSError as exc:
        raise PipelineOutputError(f"Cannot read Basic Pitch CSV: {source}") from exc

    converted.sort(key=lambda item: (item[0], item[1], item[2]))
    return [
        Note(
            id=f"note_{index:04d}",
            start_seconds=start,
            end_seconds=end,
            midi=midi,
            note_name=midi_to_note_name(midi),
            confidence=velocity / 127,
        )
        for index, (start, end, midi, velocity) in enumerate(converted, start=1)
    ]
