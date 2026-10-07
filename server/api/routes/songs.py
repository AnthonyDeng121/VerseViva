from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from server.config import get_settings
from server.models.song import AnalysisJob, AnalysisStage, AnalysisStatus, SongProfile
from server.pipelines.song_analysis import build_default_pipeline
from server.services.language import add_pronunciation_guides
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore

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
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),  # noqa: B008
    title: str = Form(...),
    artist: str = Form(...),
    lyrics: str | None = Form(default=None),
) -> AnalysisJob:
    if not title.strip() or not artist.strip():
        raise HTTPException(status_code=422, detail="Song title and artist are required")
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
    inferred_title, inferred_artist = _infer_song_identity(
        filename=audio.filename or "Untitled",
        title=title,
        artist=artist,
    )
    job = AnalysisJob(
        job_id=job_id,
        song_id=song_id,
        status=AnalysisStatus.queued,
        title=inferred_title,
        artist=inferred_artist,
        has_lyrics=bool(lyrics and lyrics.strip()),
    )
    JobStore(settings.data_dir).save(job)
    if lyrics and lyrics.strip():
        (input_dir / "lyrics.txt").write_text(lyrics.strip(), encoding="utf-8")
    if settings.auto_run_analysis_pipeline:
        background_tasks.add_task(
            build_default_pipeline(settings).run,
            job.job_id,
            destination,
        )
    return job


def _infer_song_identity(
    *, filename: str, title: str | None, artist: str | None
) -> tuple[str, str | None]:
    clean_title = title.strip() if title and title.strip() else None
    clean_artist = artist.strip() if artist and artist.strip() else None
    stem = Path(filename).stem.strip() or "Untitled"
    if clean_title:
        return clean_title, clean_artist
    if " - " in stem:
        inferred_artist, inferred_title = stem.split(" - ", maxsplit=1)
        return inferred_title.strip() or stem, clean_artist or inferred_artist.strip() or None
    return stem, clean_artist


@router.get("/jobs/latest", response_model=AnalysisJob)
async def get_latest_analysis_job() -> AnalysisJob:
    job = JobStore(get_settings().data_dir).latest()
    if job is None:
        raise HTTPException(status_code=404, detail="No analysis jobs found")
    return job


@router.get("/jobs/{job_id}", response_model=AnalysisJob)
async def get_analysis_job(job_id: str) -> AnalysisJob:
    job = JobStore(get_settings().data_dir).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.post(
    "/jobs/{job_id}/retry",
    response_model=AnalysisJob,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis_job(job_id: str, background_tasks: BackgroundTasks) -> AnalysisJob:
    settings = get_settings()
    store = JobStore(settings.data_dir)
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if job.status != AnalysisStatus.failed:
        raise HTTPException(status_code=409, detail="Only failed analysis jobs can be retried")

    input_dir = settings.data_dir / "jobs" / job_id / "input"
    sources = [
        path
        for suffix in ALLOWED_CONTENT_TYPES
        if (path := input_dir / f"source{suffix}").is_file()
    ]
    if len(sources) != 1:
        raise HTTPException(status_code=409, detail="Original audio is missing or ambiguous")

    previous_stage = job.error.stage if job.error else AnalysisStage.queued
    job.status = AnalysisStatus.queued
    job.stage = previous_stage
    job.error = None
    store.save(job)
    background_tasks.add_task(
        build_default_pipeline(settings).run,
        job.job_id,
        sources[0],
    )
    return job


@router.get("/{song_id}", response_model=SongProfile)
async def get_song_profile(song_id: str) -> SongProfile:
    store = ProfileStore(get_settings().data_dir)
    profile = store.get(song_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Song profile not found")
    if profile.language in {"ja", "ko"} and any(
        sentence.pronunciation is None
        or sentence.pronunciation.text.strip() == sentence.lyrics.strip()
        for sentence in profile.sentences
    ):
        upgraded = add_pronunciation_guides(profile.sentences, profile.language)
        profile = profile.model_copy(update={"sentences": upgraded})
        store.save(profile)
    return profile


@router.get("/{song_id}/audio/{asset}", response_class=FileResponse)
async def get_song_audio(song_id: str, asset: str) -> FileResponse:
    settings = get_settings()
    profile = ProfileStore(settings.data_dir).get(song_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Song profile not found")

    audio_dir = settings.data_dir / "songs" / song_id / "audio"
    if asset == "vocals":
        source = audio_dir / "vocals.wav"
    elif asset == "accompaniment":
        source = audio_dir / "accompaniment.wav"
    elif asset == "source":
        matches = sorted(audio_dir.glob("source.*"))
        source = matches[0] if matches else audio_dir / "source"
    else:
        raise HTTPException(status_code=404, detail="Audio asset not found")
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Audio asset not found")
    return FileResponse(source)
