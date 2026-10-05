from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2

from server.config import Settings
from server.models.song import (
    AnalysisError,
    AnalysisStage,
    AnalysisStatus,
    AudioAssets,
    LyricsSource,
)
from server.pipelines.audio_probe import AudioDurationProbe, FfprobeAudioDurationProbe
from server.pipelines.basic_pitch import BasicPitchAdapter, convert_basic_pitch_contour
from server.pipelines.contracts import LanguageCoach, LyricsAligner, PitchExtractor, VocalSeparator
from server.pipelines.demucs import DemucsAdapter
from server.pipelines.language_coach import DisabledLanguageCoach, GeminiLanguageCoach
from server.pipelines.whisperx import WhisperXAdapter, convert_whisperx_json
from server.services.language import apply_language_observations, generate_language_candidates
from server.services.lyrics_reconciliation import reconcile_provided_lyrics
from server.services.song_profile_builder import build_song_profile
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore

PIPELINE_VERSION = "language-annotation-v1"
STAGE_PROGRESS = {
    AnalysisStage.separating_vocals: 10,
    AnalysisStage.extracting_pitch: 40,
    AnalysisStage.aligning_lyrics: 68,
    AnalysisStage.analyzing_language: 82,
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
        language_coach: LanguageCoach | None = None,
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
        self.language_coach = language_coach or DisabledLanguageCoach()

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
            pitch_conversion = convert_basic_pitch_contour(
                pitch_artifacts.note_events_csv,
                pitch_artifacts.model_output_npz,
            )

            self._advance(job, AnalysisStage.aligning_lyrics)
            alignment_artifacts = await self.lyrics_aligner.align(
                separation.vocals, job_dir / "alignment"
            )
            alignment = convert_whisperx_json(alignment_artifacts.alignment_json)

            self._advance(job, AnalysisStage.analyzing_language)
            provided_lyrics_path = job_dir / "input" / "lyrics.txt"
            lyrics = (
                provided_lyrics_path.read_text(encoding="utf-8")
                if provided_lyrics_path.is_file()
                else "\n".join(sentence.lyrics for sentence in alignment.sentences)
            )
            sentences = alignment.sentences
            lyrics_source = LyricsSource.asr
            if provided_lyrics_path.is_file():
                sentences, lyrics_matched = reconcile_provided_lyrics(lyrics, sentences)
                if lyrics_matched:
                    lyrics_source = LyricsSource.provided
            candidates = generate_language_candidates(sentences)
            observations = await self.language_coach.analyze(
                separation.vocals, lyrics, sentences, candidates
            )
            annotated_sentences = apply_language_observations(
                sentences,
                candidates,
                observations.observations,
                provider=self.language_coach.provider,
                model=self.language_coach.model,
            )

            self._advance(job, AnalysisStage.building_profile)
            duration = await self.duration_probe.duration_seconds(source)
            _publish_audio_assets(
                source=source,
                vocals=separation.vocals,
                song_dir=self.profile_store.songs_dir / job.song_id,
            )
            profile = build_song_profile(
                song_id=job.song_id,
                title=job.title,
                duration_seconds=duration,
                language=alignment.language,
                audio=AudioAssets(
                    source_url=f"/api/v1/songs/{job.song_id}/audio/source",
                    vocal_url=f"/api/v1/songs/{job.song_id}/audio/vocals",
                ),
                sentences=annotated_sentences,
                notes=pitch_conversion.notes,
                pitch_points=pitch_conversion.pitch_points,
                pitch_processing=pitch_conversion.summary,
                pipeline_version=PIPELINE_VERSION,
                separation_model=self.separation_model,
                pitch_model=self.pitch_model,
                alignment_model=self.alignment_model,
                language_analysis_provider=self.language_coach.provider,
                language_analysis_model=self.language_coach.model,
                lyrics_source=lyrics_source,
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

    language_coach: LanguageCoach = DisabledLanguageCoach()
    if settings.language_analysis_provider == "gemini":
        if settings.gemini_api_key is None:
            raise ValueError(
                "VERSEVIVA_GEMINI_API_KEY is required when language analysis provider is gemini"
            )
        language_coach = GeminiLanguageCoach(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
        )

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
        language_coach=language_coach,
    )


def _publish_audio_assets(*, source: Path, vocals: Path, song_dir: Path) -> None:
    audio_dir = song_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    copy2(source, audio_dir / f"source{source.suffix.lower()}")
    copy2(vocals, audio_dir / "vocals.wav")
