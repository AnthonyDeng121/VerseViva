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
