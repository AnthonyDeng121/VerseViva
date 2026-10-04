from datetime import UTC, datetime
from pathlib import Path

from server.config import Settings
from server.models.song import (
    AnalysisError,
    AnalysisStage,
    AnalysisStatus,
    AudioAssets,
    LyricsSource,
)
from server.pipelines.audio_probe import AudioDurationProbe, FfprobeAudioDurationProbe
from server.pipelines.basic_pitch import BasicPitchAdapter, convert_basic_pitch_csv
from server.pipelines.contracts import LyricsAligner, PitchExtractor, VocalSeparator
from server.pipelines.demucs import DemucsAdapter
from server.pipelines.whisperx import WhisperXAdapter, convert_whisperx_json
from server.services.song_profile_builder import build_song_profile
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore

PIPELINE_VERSION = "day2-v1"
STAGE_PROGRESS = {
    AnalysisStage.separating_vocals: 10,
    AnalysisStage.extracting_pitch: 40,
    AnalysisStage.aligning_lyrics: 68,
    AnalysisStage.building_profile: 90,
    AnalysisStage.completed: 100,
}


class SongAnalysisPipeline:
    def __init__(
        self,
        separator: VocalSeparator,
        pitch_extractor: PitchExtractor,
        lyrics_aligner: LyricsAligner,
        duration_probe: AudioDurationProbe,
        job_store: JobStore,
        profile_store: ProfileStore,
        separation_model: str,
        pitch_model: str,
        alignment_model: str,
    ):
        self.separator = separator
        self.pitch_extractor = pitch_extractor
        self.lyrics_aligner = lyrics_aligner
        self.duration_probe = duration_probe
        self.job_store = job_store
        self.profile_store = profile_store
        self.separation_model = separation_model
        self.pitch_model = pitch_model
        self.alignment_model = alignment_model

    async def run(self, job_id: str, source: Path) -> None:
        job = self.job_store.get(job_id)
        if job is None:
            return
        job_dir = source.parents[1]
        try:
            self._advance(job, AnalysisStage.separating_vocals)
            separation = await self.separator.separate(source, job_dir / "separation")

            self._advance(job, AnalysisStage.extracting_pitch)
            pitch_artifacts = await self.pitch_extractor.extract(
                separation.vocals, job_dir / "pitch"
            )
            notes = convert_basic_pitch_csv(pitch_artifacts.note_events_csv)

            self._advance(job, AnalysisStage.aligning_lyrics)
            alignment_artifacts = await self.lyrics_aligner.align(
                separation.vocals, job_dir / "alignment"
            )
            alignment = convert_whisperx_json(alignment_artifacts.alignment_json)

            self._advance(job, AnalysisStage.building_profile)
            duration = await self.duration_probe.duration_seconds(source)
            profile = build_song_profile(
                song_id=job.song_id,
                title=job.title,
                duration_seconds=duration,
                language=alignment.language,
                audio=AudioAssets(
                    source_url=f"/api/v1/songs/{job.song_id}/audio/source",
                    vocal_url=f"/api/v1/songs/{job.song_id}/audio/vocals",
                ),
                sentences=alignment.sentences,
                notes=notes,
                pipeline_version=PIPELINE_VERSION,
                separation_model=self.separation_model,
                pitch_model=self.pitch_model,
                alignment_model=self.alignment_model,
                lyrics_source=LyricsSource.asr,
                created_at=datetime.now(UTC),
            )
            self.profile_store.save(profile)
            self._advance(job, AnalysisStage.completed, AnalysisStatus.completed)
        except Exception as exc:
            failed_stage = job.stage
            job.status = AnalysisStatus.failed
            job.stage = AnalysisStage.failed
            job.error = AnalysisError(
                code=f"{failed_stage.value}_failed",
                stage=failed_stage,
                message="歌曲分析没有完成，请稍后重试。",
                detail=str(exc),
            )
            self.job_store.save(job)

    def _advance(
        self,
        job,
        stage: AnalysisStage,
        status: AnalysisStatus = AnalysisStatus.processing,
    ) -> None:
        job.status = status
        job.stage = stage
        job.progress = STAGE_PROGRESS[stage]
        job.error = None
        self.job_store.save(job)


def build_default_pipeline(settings: Settings) -> SongAnalysisPipeline:
    project_root = Path(__file__).resolve().parents[2]

    def executable(path: Path) -> str:
        return str(path if path.is_absolute() else project_root / path)

    return SongAnalysisPipeline(
        separator=DemucsAdapter(
            executable=executable(settings.demucs_executable),
            model_name=settings.demucs_model,
        ),
        pitch_extractor=BasicPitchAdapter(
            executable=executable(settings.basic_pitch_executable)
        ),
        lyrics_aligner=WhisperXAdapter(
            executable=executable(settings.whisperx_executable),
            model_name=settings.whisperx_model,
            device=settings.whisperx_device,
            compute_type=settings.whisperx_compute_type,
        ),
        duration_probe=FfprobeAudioDurationProbe(executable=settings.ffprobe_executable),
        job_store=JobStore(settings.data_dir),
        profile_store=ProfileStore(settings.data_dir),
        separation_model=settings.demucs_model,
        pitch_model="basic-pitch",
        alignment_model=f"whisperx-{settings.whisperx_model}",
    )
