import json
import re
from pathlib import Path

from server.models.recording import RecordingTake, TakeSaveMode

TAKE_ID_PATTERN = re.compile(r"take_[0-9a-f]{32}")


class TakeStore:
    """File-backed Demo store. Audio is immutable; replace only changes active metadata."""

    def __init__(self, data_dir: Path):
        self.takes_dir = data_dir / "takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)

    def save(self, take: RecordingTake) -> None:
        take_dir = self.takes_dir / take.take_id
        take_dir.mkdir(parents=True, exist_ok=True)
        destination = take_dir / "take.json"
        temporary = take_dir / ".take.json.tmp"
        temporary.write_text(
            json.dumps(take.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)

    def add(self, take: RecordingTake) -> None:
        if take.save_mode == TakeSaveMode.practice_replace:
            for previous in self.list_for_song(take.song_id, session_id=take.session_id):
                if (
                    previous.save_mode == TakeSaveMode.practice_replace
                    and previous.track_slot_id == take.track_slot_id
                    and previous.is_current
                ):
                    self.save(
                        previous.model_copy(
                            update={
                                "is_current": False,
                                "superseded_by_take_id": take.take_id,
                            }
                        )
                    )
        self.save(take)

    def get(self, take_id: str) -> RecordingTake | None:
        if TAKE_ID_PATTERN.fullmatch(take_id) is None:
            return None
        source = self.takes_dir / take_id / "take.json"
        if not source.is_file():
            return None
        try:
            return RecordingTake.model_validate_json(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def list_for_song(self, song_id: str, *, session_id: str | None = None) -> list[RecordingTake]:
        takes: list[RecordingTake] = []
        for source in self.takes_dir.glob("take_*/take.json"):
            try:
                take = RecordingTake.model_validate_json(source.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if take.song_id == song_id and (session_id is None or take.session_id == session_id):
                takes.append(take)
        return sorted(takes, key=lambda item: item.created_at)
