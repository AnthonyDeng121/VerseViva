from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from server.config import get_settings
from server.models.song import AnalysisJob, AnalysisStatus

router = APIRouter()
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac"}


@router.post("/analyze", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def analyze_song(
    audio: UploadFile = File(...),  # noqa: B008
    title: str | None = Form(default=None),
    lyrics: str | None = Form(default=None),
) -> AnalysisJob:
    if audio.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Only MP3, WAV, and FLAC audio is supported")

    job_id = uuid4().hex
    suffix = Path(audio.filename or "song.mp3").suffix.lower() or ".mp3"
    destination = get_settings().data_dir / "uploads" / f"{job_id}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as output:
        while chunk := await audio.read(1024 * 1024):
            output.write(chunk)

    # The worker pipeline will consume this durable upload in the next milestone.
    return AnalysisJob(
        job_id=job_id,
        status=AnalysisStatus.queued,
        title=title or Path(audio.filename or "Untitled").stem,
        has_lyrics=bool(lyrics and lyrics.strip()),
    )
