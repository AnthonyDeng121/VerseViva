import asyncio

import httpx

from server.services.lyrics.lrclib import LrclibLyricsProvider


def test_lrclib_selects_matching_non_instrumental_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["track_name"] == "Juno"
        assert request.url.params["artist_name"] == "Sabrina Carpenter"
        assert request.headers["user-agent"].startswith("VerseViva/")
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "trackName": "Juno",
                    "artistName": "Other Artist",
                    "duration": 182,
                    "instrumental": False,
                    "plainLyrics": "wrong words",
                    "syncedLyrics": None,
                },
                {
                    "id": 2,
                    "trackName": "Juno",
                    "artistName": "Sabrina Carpenter",
                    "albumName": "Short n' Sweet",
                    "duration": 183,
                    "instrumental": False,
                    "plainLyrics": "I know you want my touch for life",
                    "syncedLyrics": "[00:00.00]I know you want my touch for life",
                },
            ],
        )

    provider = LrclibLyricsProvider(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        provider.find(title="Juno", artist="Sabrina Carpenter", duration_seconds=183.0)
    )

    assert result is not None
    assert result.provider_track_id == 2
    assert result.plain_lyrics.startswith("I know")
    assert result.match_confidence == 1.0


def test_lrclib_rejects_weak_match() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[
                {
                    "id": 9,
                    "trackName": "A Completely Different Track",
                    "artistName": "Someone Else",
                    "instrumental": False,
                    "plainLyrics": "not the requested song",
                }
            ],
        )
    )
    provider = LrclibLyricsProvider(transport=transport)

    result = asyncio.run(
        provider.find(title="Juno", artist="Sabrina Carpenter", duration_seconds=183.0)
    )

    assert result is None


def test_lrclib_can_derive_plain_lyrics_from_synced_lyrics() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[
                {
                    "id": 2,
                    "trackName": "Juno",
                    "artistName": "Sabrina Carpenter",
                    "instrumental": False,
                    "plainLyrics": None,
                    "syncedLyrics": "[00:01.20]First line\n[00:04.00]Second line",
                }
            ],
        )
    )
    provider = LrclibLyricsProvider(transport=transport)

    result = asyncio.run(provider.find(title="Juno", artist=None, duration_seconds=None))

    assert result is not None
    assert result.plain_lyrics == "First line\nSecond line"
