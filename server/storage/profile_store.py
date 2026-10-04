import json
import re
from pathlib import Path

from server.models.song import SongProfile

SONG_ID_PATTERN = re.compile(r"song_[0-9a-f]{32}")


class ProfileStore:
    def __init__(self, data_dir: Path):
        self.songs_dir = data_dir / "songs"
        self.songs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, profile: SongProfile) -> None:
        song_dir = self.songs_dir / profile.song_id
        song_dir.mkdir(parents=True, exist_ok=True)
        destination = song_dir / "profile.json"
        temporary = song_dir / ".profile.json.tmp"
        payload = profile.model_dump(mode="json", by_alias=True)
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)

    def get(self, song_id: str) -> SongProfile | None:
        if SONG_ID_PATTERN.fullmatch(song_id) is None:
            return None
        source = self.songs_dir / song_id / "profile.json"
        if not source.is_file():
            return None
        return SongProfile.model_validate_json(source.read_text(encoding="utf-8"))
