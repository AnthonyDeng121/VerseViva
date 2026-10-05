from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LyricsLookupResult:
    provider: str
    provider_track_id: int | None
    track_name: str
    artist_name: str
    album_name: str | None
    duration_seconds: float | None
    plain_lyrics: str
    synced_lyrics: str | None
    match_confidence: float
