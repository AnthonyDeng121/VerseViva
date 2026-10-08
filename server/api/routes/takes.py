import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from server.config import get_settings
from server.models.practice import PracticeAttempt, PracticeMemory
from server.models.recording import (
    RecordingSelectionType,
    RecordingTake,
    RecordingTakeUpdate,
    TakePurpose,
    TakeSaveMode,
)
from server.services.mixdown import render_mixdown
from server.services.practice.service import analyze_practice_take
from server.storage.practice_store import PracticeStore
from server.storage.profile_store import ProfileStore
from server.storage.take_store import TakeStore

router = APIRouter()
CHUNK_SIZE = 1024 * 1024
ALLOWED_RECORDING_TYPES = {
    ".webm": {"audio/webm", "video/webm", "application/octet-stream"},
    ".mp4": {"audio/mp4", "video/mp4", "application/octet-stream"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "application/octet-stream"},
    ".ogg": {"audio/ogg", "application/ogg", "application/octet-stream"},
    ".wav": {"audio/wav", "audio/x-wav", "application/octet-stream"},
}


def _recording_format(header: bytes) -> tuple[str, str] | None:
    """Identify the stored format from bytes instead of trusting browser metadata."""
    if header.startswith(b"\x1aE\xdf\xa3"):
        return ".webm", "audio/webm"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".m4a", "audio/mp4"
    if header.startswith(b"OggS"):
        return ".ogg", "audio/ogg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return ".wav", "audio/wav"
    return None


def _parse_sentence_ids(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="sentenceIds must be a JSON array") from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, str) for item in parsed)
    ):
        raise HTTPException(status_code=422, detail="sentenceIds must be a non-empty string array")
    if len(parsed) != len(set(parsed)):
        raise HTTPException(status_code=422, detail="sentenceIds must not contain duplicates")
    return parsed


@router.post(
    "/songs/{song_id}/takes",
    response_model=RecordingTake,
    status_code=status.HTTP_201_CREATED,
)
async def upload_take(
    song_id: str,
    audio: UploadFile = File(...),  # noqa: B008
    session_id: str = Form(...),
    track_slot_id: str = Form(...),
    selection_type: RecordingSelectionType = Form(...),  # noqa: B008
    sentence_ids: str = Form(...),
    selection_start_seconds: float = Form(...),
    selection_end_seconds: float = Form(...),
    timeline_start_seconds: float = Form(...),
    save_mode: TakeSaveMode = Form(...),  # noqa: B008
    purpose: TakePurpose = Form(default=TakePurpose.guided_practice),  # noqa: B008
    vocal_part_id: str | None = Form(default=None),
    client_duration_seconds: float | None = Form(default=None),
    latency_compensation_ms: float = Form(default=0),
    manual_offset_ms: float = Form(default=0),
) -> RecordingTake:
    settings = get_settings()
    profile = ProfileStore(settings.data_dir).get(song_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Song profile not found")

    selected_sentence_ids = _parse_sentence_ids(sentence_ids)
    known_sentence_ids = {sentence.id for sentence in profile.sentences}
    if not set(selected_sentence_ids).issubset(known_sentence_ids):
        raise HTTPException(
            status_code=422,
            detail="Recording selection contains unknown sentences",
        )
    if selection_type == RecordingSelectionType.sentence and len(selected_sentence_ids) != 1:
        raise HTTPException(
            status_code=422,
            detail="Single-sentence recording requires one sentence",
        )
    if selection_end_seconds <= selection_start_seconds:
        raise HTTPException(
            status_code=422,
            detail="Recording selection must have a positive interval",
        )
    if selection_end_seconds > profile.duration_seconds + 0.05:
        raise HTTPException(status_code=422, detail="Recording selection exceeds song duration")
    if timeline_start_seconds > profile.duration_seconds:
        raise HTTPException(status_code=422, detail="Timeline start exceeds song duration")
    if vocal_part_id is not None and vocal_part_id not in {part.id for part in profile.vocal_parts}:
        raise HTTPException(status_code=422, detail="Vocal Part does not belong to this song")

    suffix = Path(audio.filename or "").suffix.lower()
    expected_content_types = ALLOWED_RECORDING_TYPES.get(suffix)
    content_type = (
        (audio.content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    )
    if expected_content_types is None or content_type not in expected_content_types:
        raise HTTPException(
            status_code=415,
            detail="Recordings must be WebM, MP4/M4A, OGG, or WAV audio",
        )

    take_id = f"take_{uuid4().hex}"
    take_dir = settings.data_dir / "takes" / take_id
    take_dir.mkdir(parents=True, exist_ok=False)
    destination = take_dir / f"original{suffix}"
    size = 0
    header = b""
    try:
        with destination.open("wb") as output:
            while chunk := await audio.read(CHUNK_SIZE):
                if len(header) < 12:
                    header = (header + chunk)[:12]
                size += len(chunk)
                if size > settings.max_recording_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="录音文件过大，请缩短演唱范围后重试（当前上限 100 MB）",
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Recording is empty")
        detected_format = _recording_format(header)
        if detected_format is None:
            raise HTTPException(
                status_code=415,
                detail="Recording content is not a supported audio container",
            )
        detected_suffix, detected_content_type = detected_format
        if detected_suffix != suffix:
            corrected_destination = take_dir / f"original{detected_suffix}"
            destination.replace(corrected_destination)
            destination = corrected_destination
        content_type = detected_content_type

        existing_takes = TakeStore(settings.data_dir).list_for_song(
            song_id,
            session_id=session_id,
        )
        take = RecordingTake(
            take_id=take_id,
            display_name=f"轨道{len(existing_takes) + 1}",
            session_id=session_id,
            song_id=song_id,
            track_slot_id=track_slot_id,
            selection_type=selection_type,
            sentence_ids=selected_sentence_ids,
            vocal_part_id=vocal_part_id,
            selection_start_seconds=selection_start_seconds,
            selection_end_seconds=selection_end_seconds,
            timeline_start_seconds=timeline_start_seconds,
            save_mode=save_mode,
            purpose=purpose,
            audio_url=f"/api/v1/takes/{take_id}/audio",
            stored_filename=destination.name,
            mime_type=content_type,
            size_bytes=size,
            client_duration_seconds=client_duration_seconds,
            latency_compensation_ms=latency_compensation_ms,
            manual_offset_ms=manual_offset_ms,
        )
        TakeStore(settings.data_dir).add(take)
        return take
    except Exception:
        destination.unlink(missing_ok=True)
        try:
            take_dir.rmdir()
        except OSError:
            pass
        raise


@router.get("/songs/{song_id}/takes", response_model=list[RecordingTake])
async def list_song_takes(
    song_id: str,
    session_id: str | None = Query(default=None),
) -> list[RecordingTake]:
    settings = get_settings()
    if ProfileStore(settings.data_dir).get(song_id) is None:
        raise HTTPException(status_code=404, detail="Song profile not found")
    return TakeStore(settings.data_dir).list_for_song(song_id, session_id=session_id)


@router.get("/songs/{song_id}/mixdown", response_class=FileResponse)
async def download_song_mixdown(
    song_id: str,
    session_id: str = Query(...),
    accompaniment_volume: float = Query(default=0.55, ge=0, le=1),
    voice_volume: float = Query(default=1, ge=0, le=1),
) -> FileResponse:
    settings = get_settings()
    profile = ProfileStore(settings.data_dir).get(song_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Song profile not found")
    accompaniment = settings.data_dir / "songs" / song_id / "audio" / "accompaniment.mp3"
    if not accompaniment.is_file():
        accompaniment = accompaniment.with_suffix(".wav")
    if not accompaniment.is_file():
        raise HTTPException(status_code=409, detail="当前歌曲没有可用伴奏")
    takes = TakeStore(settings.data_dir).list_for_song(song_id, session_id=session_id)
    current = [take for take in takes if take.is_current]
    if not current:
        raise HTTPException(status_code=409, detail="当前会话还没有可混音的录音")
    sources = []
    for take in current:
        source = settings.data_dir / "takes" / take.take_id / take.stored_filename
        if not source.is_file():
            raise HTTPException(
                status_code=409,
                detail=f"音轨 {take.display_name} 的录音文件不存在",
            )
        sources.append((take, source))
    output_dir = settings.data_dir / "mixdowns" / f"mix_{uuid4().hex}"
    output = output_dir / "verseviva-mix.mp3"
    try:
        await asyncio.to_thread(
            render_mixdown,
            ffmpeg_executable=settings.ffmpeg_executable,
            accompaniment=accompaniment,
            takes=sources,
            output=output,
            accompaniment_volume=accompaniment_volume,
            voice_volume=voice_volume,
        )
    except (RuntimeError, ValueError) as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        output,
        media_type="audio/mpeg",
        filename=f"{profile.title}-VerseViva整体混音.mp3",
        background=BackgroundTask(shutil.rmtree, output_dir, ignore_errors=True),
    )


@router.get("/takes/{take_id}", response_model=RecordingTake)
async def get_take(take_id: str) -> RecordingTake:
    take = TakeStore(get_settings().data_dir).get(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="Recording Take not found")
    return take


@router.patch("/takes/{take_id}", response_model=RecordingTake)
async def update_take(take_id: str, update: RecordingTakeUpdate) -> RecordingTake:
    store = TakeStore(get_settings().data_dir)
    take = store.get(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="Recording Take not found")
    changes = update.model_dump(exclude_none=True)
    updated = take.model_copy(update=changes)
    store.save(updated)
    return updated


@router.delete("/takes/{take_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_take(
    take_id: str,
    preserve_attempt: bool = Query(default=False),
) -> None:
    settings = get_settings()
    take = TakeStore(settings.data_dir).delete(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="Recording Take not found")
    if not preserve_attempt:
        PracticeStore(settings.data_dir).delete_for_take(take_id)
    take_dir = (settings.data_dir / "takes" / take_id).resolve()
    expected_parent = (settings.data_dir / "takes").resolve()
    if take_dir.parent == expected_parent:
        shutil.rmtree(take_dir, ignore_errors=True)


@router.get("/takes/{take_id}/audio", response_class=FileResponse)
async def get_take_audio(take_id: str) -> FileResponse:
    settings = get_settings()
    take = TakeStore(settings.data_dir).get(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="Recording Take not found")
    source = settings.data_dir / "takes" / take.take_id / take.stored_filename
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Recording audio not found")
    return FileResponse(source, media_type=take.mime_type)


@router.post("/takes/{take_id}/analyze", response_model=PracticeAttempt)
async def analyze_take(take_id: str) -> PracticeAttempt:
    settings = get_settings()
    take = TakeStore(settings.data_dir).get(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="Recording Take not found")
    if take.purpose == TakePurpose.free_overdub:
        raise HTTPException(
            status_code=409,
            detail="清唱叠录仅用于保存与混音，不参与演唱分析或长期记忆",
        )
    profile = ProfileStore(settings.data_dir).get(take.song_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Song profile not found")
    source = settings.data_dir / "takes" / take.take_id / take.stored_filename
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Recording audio not found")
    return await analyze_practice_take(settings, take, profile, source)


@router.get("/songs/{song_id}/attempts", response_model=list[PracticeAttempt])
async def list_practice_attempts(
    song_id: str,
    session_id: str = Query(...),
) -> list[PracticeAttempt]:
    settings = get_settings()
    if ProfileStore(settings.data_dir).get(song_id) is None:
        raise HTTPException(status_code=404, detail="Song profile not found")
    return PracticeStore(settings.data_dir).list_for_session(session_id, song_id)


@router.get("/practice/memory", response_model=PracticeMemory)
async def get_practice_memory(session_id: str = Query(...)) -> PracticeMemory:
    return PracticeStore(get_settings().data_dir).memory(session_id)
