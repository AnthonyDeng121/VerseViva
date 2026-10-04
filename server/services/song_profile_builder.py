from datetime import datetime

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    Note,
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
    pipeline_version: str,
    separation_model: str,
    pitch_model: str,
    alignment_model: str,
    lyrics_source: LyricsSource,
    created_at: datetime,
) -> SongProfile:
    sentences_with_notes = []
    for sentence in sentences:
        sentence_notes = [
            note
            for note in notes
            if note.end_seconds > sentence.start_seconds
            and note.start_seconds < sentence.end_seconds
        ]
        sentences_with_notes.append(sentence.model_copy(update={"notes": sentence_notes}))

    vocal_range = None
    if notes:
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
        ),
    )
