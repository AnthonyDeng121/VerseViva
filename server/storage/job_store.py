import json
import re
from datetime import UTC, datetime
from pathlib import Path

from server.models.song import AnalysisJob

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
