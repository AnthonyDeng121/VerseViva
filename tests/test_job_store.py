from pathlib import Path

from server.models.song import AnalysisJob, AnalysisStage, AnalysisStatus
from server.storage.job_store import JobStore


def test_job_store_persists_status_updates(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    job = AnalysisJob(
        job_id="job_0123456789abcdef0123456789abcdef",
        song_id="song_0123456789abcdef0123456789abcdef",
        status=AnalysisStatus.queued,
        title="Demo",
        has_lyrics=False,
    )
    store.save(job)

    job.status = AnalysisStatus.processing
    job.stage = AnalysisStage.separating_vocals
    job.progress = 20
    store.save(job)

    restored = store.get(job.job_id)
    assert restored is not None
    assert restored.status == AnalysisStatus.processing
    assert restored.stage == AnalysisStage.separating_vocals
    assert restored.progress == 20
    assert restored.updated_at >= restored.created_at


def test_job_store_marks_processing_job_retryable_after_worker_restart(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    job = AnalysisJob(
        job_id="job_0123456789abcdef0123456789abcdef",
        song_id="song_0123456789abcdef0123456789abcdef",
        status=AnalysisStatus.processing,
        stage=AnalysisStage.analyzing_language,
        progress=82,
        title="Juno",
        has_lyrics=False,
    )
    store.save(job)

    recovered = store.recover_interrupted_jobs()

    assert len(recovered) == 1
    restored = store.get(job.job_id)
    assert restored is not None
    assert restored.status == AnalysisStatus.failed
    assert restored.progress == 82
    assert restored.error is not None
    assert restored.error.code == "worker_interrupted"
    assert restored.error.stage == AnalysisStage.analyzing_language


def test_job_store_returns_latest_job(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    first = AnalysisJob(
        job_id="job_0123456789abcdef0123456789abcdef",
        song_id="song_0123456789abcdef0123456789abcdef",
        status=AnalysisStatus.completed,
        title="First",
        has_lyrics=False,
    )
    second = AnalysisJob(
        job_id="job_1123456789abcdef0123456789abcdef",
        song_id="song_1123456789abcdef0123456789abcdef",
        status=AnalysisStatus.failed,
        title="Second",
        has_lyrics=False,
    )
    store.save(first)
    store.save(second)

    latest = store.latest()

    assert latest is not None
    assert latest.job_id == second.job_id
