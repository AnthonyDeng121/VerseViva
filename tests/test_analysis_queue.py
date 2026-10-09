import asyncio
from pathlib import Path

from server.models.song import AnalysisJob, AnalysisStatus
from server.services.analysis_queue import AnalysisTaskQueue
from server.storage.job_store import JobStore


def test_analysis_queue_runs_jobs_fifo_without_overlap(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = JobStore(tmp_path)
        queue = AnalysisTaskQueue(store)
        events: list[str] = []
        active = 0
        maximum_active = 0

        async def runner(job_id: str, source: Path) -> None:
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            events.append(f"start:{job_id}")
            await asyncio.sleep(0.01)
            events.append(f"finish:{job_id}")
            active -= 1

        queue.start()
        try:
            for index in range(3):
                job_id = f"job_{index:032x}"
                store.save(
                    AnalysisJob(
                        job_id=job_id,
                        song_id=f"song_{index:032x}",
                        status=AnalysisStatus.queued,
                        title=f"Song {index}",
                        has_lyrics=False,
                    )
                )
                await queue.enqueue(job_id, tmp_path / f"{index}.mp3", runner)
            await queue.join()
        finally:
            await queue.stop()

        assert maximum_active == 1
        assert events == [
            "start:job_00000000000000000000000000000000",
            "finish:job_00000000000000000000000000000000",
            "start:job_00000000000000000000000000000001",
            "finish:job_00000000000000000000000000000001",
            "start:job_00000000000000000000000000000002",
            "finish:job_00000000000000000000000000000002",
        ]

    asyncio.run(scenario())


def test_analysis_queue_persists_unhandled_runner_failure(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = JobStore(tmp_path)
        job = AnalysisJob(
            job_id="job_0123456789abcdef0123456789abcdef",
            song_id="song_0123456789abcdef0123456789abcdef",
            status=AnalysisStatus.queued,
            title="Broken",
            has_lyrics=False,
        )
        store.save(job)

        async def runner(job_id: str, source: Path) -> None:
            raise RuntimeError("unexpected worker error")

        queue = AnalysisTaskQueue(store)
        queue.start()
        try:
            await queue.enqueue(job.job_id, tmp_path / "source.mp3", runner)
            await queue.join()
        finally:
            await queue.stop()

        failed = store.get(job.job_id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error is not None
        assert failed.error.code == "analysis_worker_failed"
        assert "unexpected worker error" in (failed.error.detail or "")

    asyncio.run(scenario())
