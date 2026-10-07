import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import httpx

from server.services.lyrics.models import LyricsLookupResult

QUALIFIER_PATTERN = re.compile(
    r"\s*[\[(](?:official|audio|video|lyrics?|lyric video|remaster(?:ed)?(?: \d{4})?)[^\])]*[\])]",
    re.IGNORECASE,
)


class DisabledLyricsProvider:
    provider = "disabled"

    async def find(self, *, title: str, artist: str | None, duration_seconds: float | None):
        return None


class LrclibLyricsProvider:
    provider = "lrclib"

    def __init__(
        self,
        *,
        base_url: str = "https://lrclib.net",
        timeout_seconds: float = 10.0,
        min_match_score: float = 0.78,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.min_match_score = min_match_score
        self.transport = transport

    async def find(
        self, *, title: str, artist: str | None, duration_seconds: float | None
    ) -> LyricsLookupResult | None:
        params = {"track_name": title}
        if artist:
            params["artist_name"] = artist
        headers = {"User-Agent": "VerseViva/0.1 (lyrics lookup for language coaching)"}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
            headers=headers,
        ) as client:
            response = await client.get(f"{self.base_url}/api/search", params=params)
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return None

        ranked: list[tuple[float, dict[str, Any]]] = []
        for item in payload:
            if not isinstance(item, dict) or item.get("instrumental"):
                continue
            plain_lyrics = item.get("plainLyrics") or _strip_lrc(item.get("syncedLyrics"))
            if not plain_lyrics:
                continue
            score = _match_score(item, title, artist, duration_seconds)
            ranked.append((score, item))
        if not ranked:
            return None
        score, best = max(ranked, key=lambda pair: pair[0])
        if score < self.min_match_score:
            return None
        return LyricsLookupResult(
            provider=self.provider,
            provider_track_id=best.get("id"),
            track_name=str(best.get("trackName") or title),
            artist_name=str(best.get("artistName") or artist or ""),
            album_name=best.get("albumName"),
            duration_seconds=_number(best.get("duration")),
            plain_lyrics=str(
                best.get("plainLyrics") or _strip_lrc(best.get("syncedLyrics"))
            ).strip(),
            synced_lyrics=best.get("syncedLyrics"),
            match_confidence=round(score, 3),
        )


def _match_score(
    item: dict[str, Any], title: str, artist: str | None, duration_seconds: float | None
) -> float:
    title_score = _similarity(title, str(item.get("trackName") or ""))
    artist_score = _similarity(artist, str(item.get("artistName") or "")) if artist else 1.0
    item_duration = _number(item.get("duration"))
    if duration_seconds is None or item_duration is None:
        duration_score = 0.5
    else:
        duration_score = max(0.0, 1.0 - abs(duration_seconds - item_duration) / 15.0)
    return title_score * 0.65 + artist_score * 0.25 + duration_score * 0.10


def _similarity(left: str | None, right: str | None) -> float:
    left_normalized = _normalize(left or "")
    right_normalized = _normalize(right or "")
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def _normalize(value: str) -> str:
    value = QUALIFIER_PATTERN.sub("", value)
    value = unicodedata.normalize("NFKC", value).casefold()
    # Keep letters and numbers from every script. The old ASCII-only expression
    # reduced Japanese and Korean titles to an empty string.
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _strip_lrc(value: object) -> str:
    if not isinstance(value, str):
        return ""
    lines = []
    for line in value.splitlines():
        text = re.sub(r"^(?:\[\d{2}:\d{2}(?:\.\d+)?\])+", "", line).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)
