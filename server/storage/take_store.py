import json
import re
import sqlite3
from pathlib import Path

from server.models.recording import RecordingTake, TakeSaveMode

TAKE_ID_PATTERN = re.compile(r"take_[0-9a-f]{32}")


class TakeStore:
    """SQLite metadata store; immutable recording audio remains in take directories."""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database = data_dir / "verseviva.sqlite3"
        self.takes_dir = data_dir / "takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recording_takes (
                    take_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    song_id TEXT NOT NULL,
                    track_slot_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_take_song_session "
                "ON recording_takes(song_id, session_id, created_at)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS storage_migrations "
                "(name TEXT PRIMARY KEY, completed_at TEXT NOT NULL)"
            )
        self._migrate_legacy_json()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _write(self, connection: sqlite3.Connection, take: RecordingTake) -> None:
        connection.execute(
            """INSERT OR REPLACE INTO recording_takes
            (take_id, session_id, song_id, track_slot_id, created_at, payload)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                take.take_id,
                take.session_id,
                take.song_id,
                take.track_slot_id,
                take.created_at.isoformat(),
                take.model_dump_json(by_alias=True),
            ),
        )

    def save(self, take: RecordingTake) -> None:
        with self._connect() as connection:
            self._write(connection, take)

    def add(self, take: RecordingTake) -> None:
        with self._connect() as connection:
            if take.save_mode == TakeSaveMode.practice_replace:
                rows = connection.execute(
                    "SELECT payload FROM recording_takes "
                    "WHERE song_id = ? AND session_id = ? AND track_slot_id = ?",
                    (take.song_id, take.session_id, take.track_slot_id),
                ).fetchall()
                for row in rows:
                    previous = self._parse(row["payload"])
                    if (
                        previous is not None
                        and previous.save_mode == TakeSaveMode.practice_replace
                        and previous.is_current
                    ):
                        self._write(
                            connection,
                            previous.model_copy(
                                update={
                                    "is_current": False,
                                    "superseded_by_take_id": take.take_id,
                                }
                            ),
                        )
            self._write(connection, take)

    def get(self, take_id: str) -> RecordingTake | None:
        if TAKE_ID_PATTERN.fullmatch(take_id) is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM recording_takes WHERE take_id = ?", (take_id,)
            ).fetchone()
        return self._parse(row["payload"]) if row else None

    def list_for_song(self, song_id: str, *, session_id: str | None = None) -> list[RecordingTake]:
        query = "SELECT payload FROM recording_takes WHERE song_id = ?"
        values = [song_id]
        if session_id is not None:
            query += " AND session_id = ?"
            values.append(session_id)
        query += " ORDER BY created_at"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [take for row in rows if (take := self._parse(row["payload"])) is not None]

    def _parse(self, payload: str) -> RecordingTake | None:
        try:
            value = json.loads(payload)
            value.setdefault("displayName", "未命名轨道")
            return RecordingTake.model_validate(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _migrate_legacy_json(self) -> None:
        """Import old take.json metadata once; leave files as a recoverable backup."""

        with self._connect() as connection:
            migrated = connection.execute(
                "SELECT 1 FROM storage_migrations WHERE name = ?",
                ("recording_takes_json_v1",),
            ).fetchone()
            if migrated is not None:
                return
            for source in self.takes_dir.glob("take_*/take.json"):
                try:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    payload.setdefault("displayName", "未命名轨道")
                    take = RecordingTake.model_validate(payload)
                except (OSError, ValueError):
                    continue
                exists = connection.execute(
                    "SELECT 1 FROM recording_takes WHERE take_id = ?", (take.take_id,)
                ).fetchone()
                if exists is None:
                    self._write(connection, take)
            connection.execute(
                "INSERT OR REPLACE INTO storage_migrations(name, completed_at) "
                "VALUES (?, datetime('now'))",
                ("recording_takes_json_v1",),
            )
