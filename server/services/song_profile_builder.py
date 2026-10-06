from datetime import datetime

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    SongProfile,
    SongSentence,
    VocalArrangementMode,
    VocalPart,
)


def build_song_profile(
    *,
    song_id: str,
    title: str,
    duration_seconds: float,
    language: str | None,
    audio: AudioAssets,
    sentences: list[SongSentence],
    pipeline_version: str,
    separation_model: str,
    alignment_model: str,
    language_analysis_provider: str | None = None,
    language_analysis_model: str | None = None,
    lyrics_source: LyricsSource,
    lyrics_provider: str | None = None,
    lyrics_provider_track_id: int | None = None,
    lyrics_match_confidence: float | None = None,
    created_at: datetime,
    vocal_parts: list[VocalPart] | None = None,
    vocal_arrangement_mode: VocalArrangementMode = VocalArrangementMode.single_track,
) -> SongProfile:
    return SongProfile(
        song_id=song_id,
        title=title,
        duration_seconds=duration_seconds,
        language=language,
        audio=audio,
        sentences=sentences,
        vocal_parts=vocal_parts or [],
        analysis=AnalysisMetadata(
            pipeline_version=pipeline_version,
            separation_model=separation_model,
            alignment_model=alignment_model,
            lyrics_source=lyrics_source,
            lyrics_provider=lyrics_provider,
            lyrics_provider_track_id=lyrics_provider_track_id,
            lyrics_match_confidence=lyrics_match_confidence,
            created_at=created_at,
            language_analysis_provider=language_analysis_provider,
            language_analysis_model=language_analysis_model,
            vocal_arrangement_mode=vocal_arrangement_mode,
        ),
    )
