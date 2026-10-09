import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from server.models.song import AnalysisError, AnalysisStage, AnalysisStatus
from server.storage.job_store import JobStore

logger = logging.getLogger(__name__)

AnalysisRunner = Callable[[str, Path], Awaitable[None]]


@dataclass(frozen=True)
class AnalysisTask:
    job_id: str
    source: Path
    runner: AnalysisRunner


class AnalysisTaskQueue:
    """Run heavyweight song pipelines FIFO with exactly one in-process worker."""

    def __init__(self, job_store: JobStore) -> None:
        self._job_store = job_store
        self._queue: asyncio.Queue[AnalysisTask] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._scheduled_job_ids: set[str] = set()
        self.active_job_id: str | None = None

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(
                self._run(),
                name="verseviva-song-analysis-worker",
            )

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        finally:
            self._worker = None
            self.active_job_id = None

    async def enqueue(self, job_id: str, source: Path, runner: AnalysisRunner) -> bool:
        if self._worker is None or self._worker.done():
            raise RuntimeError("analysis task queue is not running")
        if job_id in self._scheduled_job_ids:
            return False
        self._scheduled_job_ids.add(job_id)
        await self._queue.put(AnalysisTask(job_id=job_id, source=source, runner=runner))
        return True

    async def join(self) -> None:
        await self._queue.join()

    async def _run(self) -> None:
        while True:
            task = await self._queue.get()
            self.active_job_id = task.job_id
            try:
                await task.runner(task.job_id, task.source)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - pipeline normally persists its failures
                logger.exception("Unhandled song analysis failure for %s", task.job_id)
                self._persist_unhandled_failure(task.job_id, exc)
            finally:
                self.active_job_id = None
                self._scheduled_job_ids.discard(task.job_id)
                self._queue.task_done()

    def _persist_unhandled_failure(self, job_id: str, exc: Exception) -> None:
        job = self._job_store.get(job_id)
        if job is None or job.status in {AnalysisStatus.completed, AnalysisStatus.failed}:
            return
        interrupted_stage = (
            job.stage if job.stage != AnalysisStage.failed else AnalysisStage.queued
        )
        job.status = AnalysisStatus.failed
        job.stage = AnalysisStage.failed
        job.error = AnalysisError(
            code="analysis_worker_failed",
            stage=interrupted_stage,
            message="歌曲分析任务异常终止，可以从失败阶段重试。",
            detail=str(exc),
        )
        self._job_store.save(job)
