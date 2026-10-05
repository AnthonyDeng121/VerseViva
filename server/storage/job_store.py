import json
import re
from datetime import UTC, datetime
from pathlib import Path

from server.models.song import AnalysisError, AnalysisJob, AnalysisStage, AnalysisStatus

JOB_ID_PATTERN = re.compile(r"job_[0-9a-f]{32}")


class JobStore:
    """Persists analysis state beside the files belonging to that job."""

    def __init__(self, data_dir: Path):
        self.jobs_dir = data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job: AnalysisJob) -> None:
        job.updated_at = datetime.now(UTC)
        job_dir = self.jobs_dir / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        destination = job_dir / "job.json"
        temporary = job_dir / ".job.json.tmp"
        payload = job.model_dump(mode="json")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)

    def get(self, job_id: str) -> AnalysisJob | None:
        if JOB_ID_PATTERN.fullmatch(job_id) is None:
            return None
        source = self.jobs_dir / job_id / "job.json"
        if not source.is_file():
            return None
        return AnalysisJob.model_validate_json(source.read_text(encoding="utf-8"))

    def latest(self) -> AnalysisJob | None:
        jobs: list[AnalysisJob] = []
        for source in self.jobs_dir.glob("job_*/job.json"):
            try:
                jobs.append(
                    AnalysisJob.model_validate_json(source.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError):
                continue
        return max(jobs, key=lambda job: job.updated_at, default=None)

    def recover_interrupted_jobs(self) -> list[AnalysisJob]:
        """Turn states orphaned by a worker restart into explicit retryable failures."""

        recovered: list[AnalysisJob] = []
        for source in self.jobs_dir.glob("job_*/job.json"):
            try:
                job = AnalysisJob.model_validate_json(source.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.status not in {AnalysisStatus.queued, AnalysisStatus.processing}:
                continue
            interrupted_stage = (
                job.stage if job.stage != AnalysisStage.failed else AnalysisStage.queued
            )
            job.status = AnalysisStatus.failed
            job.stage = AnalysisStage.failed
            job.error = AnalysisError(
                code="worker_interrupted",
                stage=interrupted_stage,
                message="分析进程因后端重启而中断。",
                detail="已完成的阶段产物仍然保留，可以从断点重试。",
            )
            self.save(job)
            recovered.append(job)
        return recovered
