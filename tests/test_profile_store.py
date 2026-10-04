from pathlib import Path

from server.storage.profile_store import ProfileStore
from tests.test_song_profile_schema import make_profile


def test_profile_store_round_trips_camel_case_json(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    profile = make_profile().model_copy(
        update={"song_id": "song_0123456789abcdef0123456789abcdef"}
    )

    store.save(profile)
    restored = store.get(profile.song_id)

    assert restored == profile
    payload = (tmp_path / "songs" / profile.song_id / "profile.json").read_text(
        encoding="utf-8"
    )
    assert '"schemaVersion"' in payload
    assert '"durationSeconds"' in payload
