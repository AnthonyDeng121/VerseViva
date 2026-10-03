from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from server.config import get_settings
from server.models.song import AnalysisJob, AnalysisStatus
from server.storage.job_store import JobStore

router = APIRouter()
CHUNK_SIZE = 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    ".mp3": {"audio/mpeg", "audio/mp3", "application/octet-stream"},
    ".wav": {"audio/wav", "audio/x-wav", "application/octet-stream"},
    ".flac": {"audio/flac", "audio/x-flac", "application/octet-stream"},
}


def has_expected_audio_signature(suffix: str, header: bytes) -> bool:
    if suffix == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )
    if suffix == ".wav":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    if suffix == ".flac":
        return header.startswith(b"fLaC")
    return False


@router.post("/analyze", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def analyze_song(
    audio: UploadFile = File(...),  # noqa: B008
    title: str | None = Form(default=None),
    lyrics: str | None = Form(default=None),
) -> AnalysisJob:
    suffix = Path(audio.filename or "").suffix.lower()
    expected_content_types = ALLOWED_CONTENT_TYPES.get(suffix)
    if expected_content_types is None or audio.content_type not in expected_content_types:
        raise HTTPException(status_code=415, detail="Only MP3, WAV, and FLAC audio is supported")

    settings = get_settings()
    song_id = f"song_{uuid4().hex}"
    job_id = f"job_{uuid4().hex}"
    job_dir = settings.data_dir / "jobs" / job_id
    input_dir = job_dir / "input"
    destination = input_dir / f"source{suffix}"
    input_dir.mkdir(parents=True, exist_ok=False)

    size = 0
    header = b""
    try:
        with destination.open("wb") as output:
            while chunk := await audio.read(CHUNK_SIZE):
                if not header:
                    header = chunk[:12]
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise HTTPException(status_code=413, detail="Audio file is too large")
                output.write(chunk)

        if size == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        if not has_expected_audio_signature(suffix, header):
            raise HTTPException(
                status_code=415,
                detail="File content does not match its audio extension",
            )
    except Exception:
        destination.unlink(missing_ok=True)
        input_dir.rmdir()
        job_dir.rmdir()
        raise

    # The worker pipeline will update this persisted state in the next milestone.
    job = AnalysisJob(
        job_id=job_id,
        song_id=song_id,
        status=AnalysisStatus.queued,
        title=(title or Path(audio.filename or "Untitled").stem).strip() or "Untitled",
        has_lyrics=bool(lyrics and lyrics.strip()),
    )
    JobStore(settings.data_dir).save(job)
    return job


@router.get("/jobs/{job_id}", response_model=AnalysisJob)
async def get_analysis_job(job_id: str) -> AnalysisJob:
    job = JobStore(get_settings().data_dir).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job
