from datetime import datetime

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    Note,
    PitchPoint,
    PitchProcessingSummary,
    SongProfile,
    SongSentence,
    VocalRange,
)


def build_song_profile(
    *,
    song_id: str,
    title: str,
    duration_seconds: float,
    language: str | None,
    audio: AudioAssets,
    sentences: list[SongSentence],
    notes: list[Note],
    pitch_points: list[PitchPoint] | None = None,
    pitch_processing: PitchProcessingSummary | None = None,
    pipeline_version: str,
    separation_model: str,
    pitch_model: str,
    alignment_model: str,
    language_analysis_provider: str | None = None,
    language_analysis_model: str | None = None,
    lyrics_source: LyricsSource,
    created_at: datetime,
) -> SongProfile:
    pitch_points = pitch_points or []
    sentences_with_notes = []
    for sentence in sentences:
        sentence_notes = [
            note
            for note in notes
            if note.end_seconds > sentence.start_seconds
            and note.start_seconds < sentence.end_seconds
        ]
        sentence_pitch_points = [
            point
            for point in pitch_points
            if sentence.start_seconds <= point.time_seconds <= sentence.end_seconds
        ]
        sentences_with_notes.append(
            sentence.model_copy(
                update={"notes": sentence_notes, "pitch_contour": sentence_pitch_points}
            )
        )

    vocal_range = None
    range_midis = _robust_range_midis(pitch_points)
    if range_midis is not None:
        lowest_midi, highest_midi = range_midis
        vocal_range = VocalRange(
            lowest_midi=lowest_midi,
            highest_midi=highest_midi,
            lowest_note=_midi_to_note_name(lowest_midi),
            highest_note=_midi_to_note_name(highest_midi),
        )
    elif notes:
        lowest = min(notes, key=lambda note: note.midi)
        highest = max(notes, key=lambda note: note.midi)
        vocal_range = VocalRange(
            lowest_midi=lowest.midi,
            highest_midi=highest.midi,
            lowest_note=lowest.note_name,
            highest_note=highest.note_name,
        )

    return SongProfile(
        song_id=song_id,
        title=title,
        duration_seconds=duration_seconds,
        language=language,
        audio=audio,
        vocal_range=vocal_range,
        sentences=sentences_with_notes,
        analysis=AnalysisMetadata(
            pipeline_version=pipeline_version,
            separation_model=separation_model,
            pitch_model=pitch_model,
            alignment_model=alignment_model,
            lyrics_source=lyrics_source,
            created_at=created_at,
            pitch_processing=pitch_processing,
            language_analysis_provider=language_analysis_provider,
            language_analysis_model=language_analysis_model,
        ),
    )


def _robust_range_midis(pitch_points: list[PitchPoint]) -> tuple[int, int] | None:
    """Ignore isolated contour extremes when presenting a singer-facing range."""

    if not pitch_points:
        return None
    values = sorted(point.midi for point in pitch_points)
    if len(values) < 20:
        return round(values[0]), round(values[-1])
    lower_index = int((len(values) - 1) * 0.05)
    upper_index = int((len(values) - 1) * 0.95)
    return round(values[lower_index]), round(values[upper_index])


def _midi_to_note_name(midi: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[midi % 12]}{midi // 12 - 1}"
