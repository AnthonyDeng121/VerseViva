from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class RecordingModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RecordingSelectionType(StrEnum):
    sentence = "sentence"
    segment = "segment"


class TakeSaveMode(StrEnum):
    practice_replace = "practice_replace"
    overdub_append = "overdub_append"


class TakePurpose(StrEnum):
    guided_practice = "guided_practice"
    free_overdub = "free_overdub"


class TakeStatus(StrEnum):
    uploaded = "uploaded"
    processing = "processing"
    aligned = "aligned"
    insufficient_data = "insufficient_data"
    failed = "failed"


class RecordingTake(RecordingModel):
    """One immutable user recording plus mutable selection/playback metadata."""

    take_id: str
    display_name: str = Field(default="未命名轨道", min_length=1, max_length=40)
    session_id: str = Field(min_length=1, max_length=128)
    song_id: str
    track_slot_id: str = Field(min_length=1, max_length=128)
    selection_type: RecordingSelectionType
    sentence_ids: list[str] = Field(min_length=1)
    vocal_part_id: str | None = None
    selection_start_seconds: float = Field(ge=0)
    selection_end_seconds: float = Field(gt=0)
    timeline_start_seconds: float = Field(ge=0)
    save_mode: TakeSaveMode
    purpose: TakePurpose = TakePurpose.guided_practice
    status: TakeStatus = TakeStatus.uploaded
    audio_url: str
    stored_filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    client_duration_seconds: float | None = Field(default=None, gt=0)
    latency_compensation_ms: float = 0
    manual_offset_ms: float = 0
    gain: float = Field(default=1, ge=0, le=2)
    muted: bool = False
    is_current: bool = True
    superseded_by_take_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_selection(self) -> "RecordingTake":
        if self.selection_end_seconds <= self.selection_start_seconds:
            raise ValueError("selection end must be greater than selection start")
        if self.selection_type == RecordingSelectionType.sentence and len(self.sentence_ids) != 1:
            raise ValueError("sentence selection must contain exactly one sentence ID")
        if self.save_mode == TakeSaveMode.overdub_append and not self.is_current:
            raise ValueError("new overdub takes must remain independently current")
        return self


class RecordingTakeUpdate(RecordingModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    gain: float | None = Field(default=None, ge=0, le=2)
    manual_offset_ms: float | None = Field(default=None, ge=-2000, le=2000)
    muted: bool | None = None

    @model_validator(mode="after")
    def require_update(self) -> "RecordingTakeUpdate":
        if (
            self.display_name is None
            and self.gain is None
            and self.manual_offset_ms is None
            and self.muted is None
        ):
            raise ValueError("at least one take field must be updated")
        if self.display_name is not None:
            self.display_name = self.display_name.strip()
            if not self.display_name:
                raise ValueError("display_name must not be blank")
        return self
