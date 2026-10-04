import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from server.models.song import Note, PitchPoint, PitchProcessingSummary
from server.pipelines.errors import PipelineOutputError

EXPECTED_COLUMNS = ("start_time_s", "end_time_s", "pitch_midi", "velocity")
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
PITCH_BEND_BINS_PER_SEMITONE = 3
OUTPUT_PITCH_POINTS_PER_SECOND = 30
BASIC_PITCH_SAMPLE_RATE = 22050
BASIC_PITCH_FFT_HOP = 256
BASIC_PITCH_FRAMES_PER_WINDOW = 172
BASIC_PITCH_AUDIO_SAMPLES_PER_WINDOW = 43844
BASIC_PITCH_CONTOUR_BASE_FREQUENCY = 27.5
BASIC_PITCH_CONTOUR_BINS = 264
BASIC_PITCH_CONTOUR_SEARCH_RADIUS = 25


@dataclass(frozen=True, slots=True)
class BasicPitchRow:
    start_seconds: float
    end_seconds: float
    midi: int
    velocity: int
    pitch_bends: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BasicPitchConversion:
    notes: list[Note]
    pitch_points: list[PitchPoint]
    summary: PitchProcessingSummary


def midi_to_note_name(midi: int) -> str:
    if not 0 <= midi <= 127:
        raise PipelineOutputError(f"MIDI pitch is outside 0-127: {midi}")
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def _read_basic_pitch_rows(source: Path) -> list[BasicPitchRow]:
    try:
        with source.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = csv.reader(csv_file)
            header = next(rows, None)
            if header is None or tuple(header[:4]) != EXPECTED_COLUMNS:
                raise PipelineOutputError("Basic Pitch CSV has an unsupported header")

            converted: list[BasicPitchRow] = []
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
                    pitch_bends = tuple(int(value) for value in row[4:] if value.strip())
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
                converted.append(
                    BasicPitchRow(
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        midi=midi,
                        velocity=velocity,
                        pitch_bends=pitch_bends,
                    )
                )
    except OSError as exc:
        raise PipelineOutputError(f"Cannot read Basic Pitch CSV: {source}") from exc

    converted.sort(key=lambda item: (item.start_seconds, item.end_seconds, item.midi))
    return converted


def convert_basic_pitch_csv(source: Path) -> list[Note]:
    """Convert Basic Pitch note events while leaving contour decoding to the dedicated path."""

    converted = _read_basic_pitch_rows(source)
    return [
        Note(
            id=f"note_{index:04d}",
            start_seconds=row.start_seconds,
            end_seconds=row.end_seconds,
            midi=row.midi,
            note_name=midi_to_note_name(row.midi),
            confidence=row.velocity / 127,
        )
        for index, row in enumerate(converted, start=1)
    ]


def midi_to_frequency(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def convert_basic_pitch_contour(
    source: Path,
    model_output_npz: Path | None = None,
    *,
    confidence_threshold: float = 0.45,
    minimum_note_duration_seconds: float = 0.1,
) -> BasicPitchConversion:
    """Build a lead-vocal contour from raw NPZ data with CSV bends as fallback."""

    rows = _read_basic_pitch_rows(source)
    accepted = [
        row
        for row in rows
        if row.velocity / 127 >= confidence_threshold
        and row.end_seconds - row.start_seconds >= minimum_note_duration_seconds
        and row.pitch_bends
    ]
    accepted, octave_corrections = _correct_short_octave_outliers(accepted)
    notes = [
        Note(
            id=f"note_{index:04d}",
            start_seconds=row.start_seconds,
            end_seconds=row.end_seconds,
            midi=row.midi,
            note_name=midi_to_note_name(row.midi),
            confidence=row.velocity / 127,
        )
        for index, row in enumerate(accepted, start=1)
    ]

    fallback_reason = None
    try:
        if model_output_npz is None:
            raise PipelineOutputError("Basic Pitch NPZ was not provided")
        raw_points = _pitch_points_from_npz(model_output_npz, accepted)
        source_name = "basic-pitch-npz-contour-with-note-events"
    except Exception as exc:
        raw_points = _pitch_points_from_decoded_bends(accepted)
        source_name = "basic-pitch-csv-decoded-bends-fallback"
        fallback_reason = str(exc)

    pitch_points = _downsample_pitch_points(raw_points)
    summary = PitchProcessingSummary(
        source=source_name,
        fallback_used=fallback_reason is not None,
        fallback_reason=fallback_reason,
        raw_note_count=len(rows),
        accepted_note_count=len(accepted),
        rejected_note_count=len(rows) - len(accepted),
        raw_pitch_point_count=len(raw_points),
        output_pitch_point_count=len(pitch_points),
        confidence_threshold=confidence_threshold,
        minimum_note_duration_seconds=minimum_note_duration_seconds,
        octave_corrections=octave_corrections,
    )
    return BasicPitchConversion(notes=notes, pitch_points=pitch_points, summary=summary)


def _pitch_points_from_npz(source: Path, rows: list[BasicPitchRow]) -> list[PitchPoint]:
    """Decode a trusted, locally generated Basic Pitch contour posterior."""

    if not source.is_file():
        raise PipelineOutputError(f"Basic Pitch NPZ does not exist: {source}")
    # Basic Pitch stores a Python dict inside the NPZ, which requires pickle. This
    # function must only receive artifacts produced by our own Basic Pitch adapter.
    with np.load(source, allow_pickle=True) as archive:
        root = archive["basic_pitch_model_output"]
        output = root.item()
        contour = np.asarray(output["contour"], dtype=float)
        note = np.asarray(output["note"], dtype=float)

    if contour.ndim != 2 or contour.shape[1] != BASIC_PITCH_CONTOUR_BINS:
        raise PipelineOutputError(
            f"Basic Pitch contour has unsupported shape: {contour.shape}"
        )
    if note.ndim != 2 or note.shape[0] != contour.shape[0]:
        raise PipelineOutputError(f"Basic Pitch note output has unsupported shape: {note.shape}")
    if not np.isfinite(contour).all():
        raise PipelineOutputError("Basic Pitch contour contains non-finite values")

    points: list[PitchPoint] = []
    times = _model_frame_times(contour.shape[0])
    for frame_index, time_seconds in enumerate(times):
        active_rows = [
            row for row in rows if row.start_seconds <= time_seconds <= row.end_seconds
        ]
        best_point = None
        best_score = -1.0
        for row in active_rows:
            center = 12 * PITCH_BEND_BINS_PER_SEMITONE * math.log2(
                midi_to_frequency(row.midi) / BASIC_PITCH_CONTOUR_BASE_FREQUENCY
            )
            start = max(0, int(round(center)) - BASIC_PITCH_CONTOUR_SEARCH_RADIUS)
            end = min(
                BASIC_PITCH_CONTOUR_BINS,
                int(round(center)) + BASIC_PITCH_CONTOUR_SEARCH_RADIUS + 1,
            )
            indexes = np.arange(start, end)
            weights = np.exp(-0.5 * ((indexes - center) / 5.0) ** 2)
            local_values = contour[frame_index, start:end] * weights
            selected_bin = start + int(np.argmax(local_values))
            confidence = float(contour[frame_index, selected_bin])
            score = confidence * (row.velocity / 127)
            if score <= best_score:
                continue
            frequency = BASIC_PITCH_CONTOUR_BASE_FREQUENCY * 2 ** (
                selected_bin / (12 * PITCH_BEND_BINS_PER_SEMITONE)
            )
            midi = 69 + 12 * math.log2(frequency / 440)
            best_score = score
            best_point = PitchPoint(
                time_seconds=float(time_seconds),
                frequency_hz=frequency,
                midi=midi,
                confidence=confidence,
            )
        if best_point is not None:
            points.append(best_point)
    return points


def _model_frame_times(frame_count: int) -> np.ndarray:
    frame_indexes = np.arange(frame_count)
    original_times = frame_indexes * BASIC_PITCH_FFT_HOP / BASIC_PITCH_SAMPLE_RATE
    window_numbers = np.floor(frame_indexes / BASIC_PITCH_FRAMES_PER_WINDOW)
    window_offset = (BASIC_PITCH_FFT_HOP / BASIC_PITCH_SAMPLE_RATE) * (
        BASIC_PITCH_FRAMES_PER_WINDOW
        - BASIC_PITCH_AUDIO_SAMPLES_PER_WINDOW / BASIC_PITCH_FFT_HOP
    ) + 0.0018
    return original_times - window_offset * window_numbers


def _pitch_points_from_decoded_bends(rows: list[BasicPitchRow]) -> list[PitchPoint]:
    points: list[PitchPoint] = []
    for row in rows:
        bend_count = len(row.pitch_bends)
        duration = row.end_seconds - row.start_seconds
        for index, bend in enumerate(row.pitch_bends):
            fraction = index / (bend_count - 1) if bend_count > 1 else 0.5
            time_seconds = row.start_seconds + duration * fraction
            midi = row.midi + bend / PITCH_BEND_BINS_PER_SEMITONE
            if not math.isfinite(midi) or not 0 < midi < 128:
                continue
            points.append(
                PitchPoint(
                    time_seconds=time_seconds,
                    frequency_hz=midi_to_frequency(midi),
                    midi=midi,
                    confidence=row.velocity / 127,
                )
            )
    return points


def _downsample_pitch_points(points: list[PitchPoint]) -> list[PitchPoint]:
    candidates: dict[int, PitchPoint] = {}
    for point in points:
        # Basic Pitch can emit overlapping notes. For a lead-vocal curve, keep
        # the strongest candidate in each frontend-sized time bucket.
        bucket = round(point.time_seconds * OUTPUT_PITCH_POINTS_PER_SECOND)
        existing = candidates.get(bucket)
        if existing is None or point.confidence > existing.confidence:
            candidates[bucket] = point
    return sorted(candidates.values(), key=lambda point: point.time_seconds)


def _correct_short_octave_outliers(
    rows: list[BasicPitchRow],
    *,
    context_seconds: float = 2.0,
    maximum_duration_seconds: float = 0.5,
) -> tuple[list[BasicPitchRow], int]:
    """Move short harmonic detections down by octaves when local context is stable.

    Basic Pitch is polyphonic, so isolated vocal harmonics can be decoded as notes one
    or two octaves above the lead. A correction is only applied when the local median
    is at least an octave lower and the difference is close to a whole number of octaves.
    """

    corrected: list[BasicPitchRow] = []
    correction_count = 0
    centers = [(row.start_seconds + row.end_seconds) / 2 for row in rows]
    for index, row in enumerate(rows):
        duration = row.end_seconds - row.start_seconds
        neighbors = [
            other.midi
            for other_index, other in enumerate(rows)
            if other_index != index
            and abs(centers[other_index] - centers[index]) <= context_seconds
        ]
        if duration > maximum_duration_seconds or len(neighbors) < 3:
            corrected.append(row)
            continue

        neighbors.sort()
        local_median = neighbors[len(neighbors) // 2]
        difference = row.midi - local_median
        octave_count = round(difference / 12)
        is_octave_outlier = (
            octave_count >= 1
            and abs(difference - octave_count * 12) <= 2
            and difference >= 10
        )
        if is_octave_outlier:
            corrected.append(replace(row, midi=row.midi - octave_count * 12))
            correction_count += 1
        else:
            corrected.append(row)
    return corrected, correction_count
