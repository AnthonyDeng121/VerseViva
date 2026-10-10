import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2

from server.config import Settings
from server.models.song import (
    AnalysisError,
    AnalysisStage,
    AnalysisStatus,
    AnalysisWarning,
    AudioAssets,
    LyricsSource,
    StageRuntime,
    VocalArrangementMode,
    VocalPart,
)
from server.pipelines.audio_probe import AudioDurationProbe, FfprobeAudioDurationProbe
from server.pipelines.contracts import (
    LanguageCoach,
    LyricsAligner,
    LyricsProvider,
    VocalPartAnalyzer,
    VocalSeparator,
)
from server.pipelines.demucs import DemucsAdapter
from server.pipelines.language_coach import DisabledLanguageCoach, GeminiLanguageCoach
from server.pipelines.whisperx import WhisperXAdapter, convert_whisperx_json
from server.services.language import (
    add_pronunciation_guides,
    apply_language_observations,
    generate_language_candidates,
    supports_language_coaching,
)
from server.services.language.models import LanguageCandidate, LanguageObservationBatch
from server.services.lyrics import DisabledLyricsProvider, LrclibLyricsProvider
from server.services.lyrics.models import LyricsLookupResult
from server.services.lyrics_reconciliation import (
    reconcile_provided_lyrics,
    reconcile_synced_lyrics_excerpt,
)
from server.services.song_profile_builder import build_song_profile
from server.services.vocal_parts import GeminiVocalPartAnalyzer
from server.services.vocal_parts.arrangement import (
    DualTrackArrangementPipeline,
    SingleTrackArrangementPipeline,
    select_arrangement_mode,
)
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore

PIPELINE_VERSION = "language-and-arrangement-v4"
STAGE_PROGRESS = {
    AnalysisStage.probing_audio: 2,
    AnalysisStage.separating_vocals: 10,
    AnalysisStage.fetching_lyrics: 30,
    AnalysisStage.aligning_lyrics: 55,
    AnalysisStage.analyzing_vocal_parts: 70,
    AnalysisStage.analyzing_language: 82,
    AnalysisStage.building_profile: 92,
    AnalysisStage.completed: 100,
}
STAGE_ESTIMATE = {
    AnalysisStage.probing_audio: (2.0, 0.0),
    AnalysisStage.separating_vocals: (8.0, 3.1),
    AnalysisStage.fetching_lyrics: (5.0, 0.0),
    AnalysisStage.aligning_lyrics: (20.0, 14.0),
    AnalysisStage.analyzing_vocal_parts: (8.0, 1.7),
    AnalysisStage.analyzing_language: (10.0, 5.0),
    AnalysisStage.building_profile: (6.0, 0.1),
}


class SongAnalysisPipeline:
    def __init__(
        self,
        separator: VocalSeparator,
        lyrics_aligner: LyricsAligner,
        duration_probe: AudioDurationProbe,
        job_store: JobStore,
        profile_store: ProfileStore,
        separation_model: str,
        alignment_model: str,
        lyrics_provider: LyricsProvider | None = None,
        language_coach: LanguageCoach | None = None,
        vocal_part_analyzer: VocalPartAnalyzer | None = None,
    ):
        self.separator = separator
        self.lyrics_aligner = lyrics_aligner
        self.duration_probe = duration_probe
        self.job_store = job_store
        self.profile_store = profile_store
        self.separation_model = separation_model
        self.alignment_model = alignment_model
        self.lyrics_provider = lyrics_provider or DisabledLyricsProvider()
        self.language_coach = language_coach or DisabledLanguageCoach()
        self.vocal_part_analyzer = vocal_part_analyzer

    async def run(self, job_id: str, source: Path) -> None:
        job = self.job_store.get(job_id)
        if job is None:
            return
        job_dir = source.parents[1]
        try:
            job.attempt_count += 1
            self._advance(job, AnalysisStage.probing_audio)
            duration = await self.duration_probe.duration_seconds(source)
            job.audio_duration_seconds = duration
            self._apply_estimates(job, duration)
            self.job_store.save(job)
            self._advance(job, AnalysisStage.separating_vocals)
            separation = await self.separator.separate(source, job_dir / "separation")
            analysis_vocals = job_dir / "separation" / "analysis-vocals.mp3"
            _create_web_audio(separation.vocals, analysis_vocals)
            if not analysis_vocals.is_file():
                analysis_vocals = separation.vocals

            provided_lyrics_path = job_dir / "input" / "lyrics.txt"
            if provided_lyrics_path.is_file():
                job.warnings = [
                    warning
                    for warning in job.warnings
                    if warning.stage != AnalysisStage.fetching_lyrics
                ]
                self.job_store.save(job)
            lyrics_lookup = _load_lyrics_lookup(job_dir / "lyrics" / "lookup.json")
            if not provided_lyrics_path.is_file():
                self._advance(job, AnalysisStage.fetching_lyrics)
                if lyrics_lookup is None:
                    try:
                        if self.lyrics_provider.provider != "disabled":
                            self._record_api_call(job, AnalysisStage.fetching_lyrics)
                        lyrics_lookup = await self.lyrics_provider.find(
                            title=job.title,
                            artist=job.artist,
                            duration_seconds=duration,
                        )
                        if lyrics_lookup is not None:
                            _save_json(
                                job_dir / "lyrics" / "lookup.json",
                                asdict(lyrics_lookup),
                            )
                    except Exception as exc:
                        job.warnings.append(
                            AnalysisWarning(
                                stage=AnalysisStage.fetching_lyrics,
                                message="联网歌词查询失败，已回退到 WhisperX 转写。",
                                detail=str(exc),
                            )
                        )
                        self.job_store.save(job)
                else:
                    self._mark_cache_hit(job, AnalysisStage.fetching_lyrics)

            self._advance(job, AnalysisStage.aligning_lyrics)
            alignment_language_hint = _detect_lyrics_language(
                provided_lyrics_path.read_text(encoding="utf-8")
                if provided_lyrics_path.is_file()
                else lyrics_lookup.plain_lyrics
                if lyrics_lookup is not None
                else ""
            )
            alignment_artifacts = await self.lyrics_aligner.align(
                analysis_vocals,
                job_dir / "alignment",
                language=alignment_language_hint,
            )
            alignment = convert_whisperx_json(alignment_artifacts.alignment_json)

            lyrics = (
                provided_lyrics_path.read_text(encoding="utf-8")
                if provided_lyrics_path.is_file()
                else lyrics_lookup.plain_lyrics
                if lyrics_lookup is not None
                else "\n".join(sentence.lyrics for sentence in alignment.sentences)
            )
            arrangement_source_lyrics = lyrics
            sentences = alignment.sentences
            lyrics_source = LyricsSource.asr
            if provided_lyrics_path.is_file():
                sentences, lyrics_matched = reconcile_provided_lyrics(lyrics, sentences)
                if lyrics_matched:
                    lyrics_source = LyricsSource.provided
            elif lyrics_lookup is not None:
                sentences, lyrics_matched = reconcile_provided_lyrics(lyrics, sentences)
                if (
                    not lyrics_matched
                    and lyrics_lookup.synced_lyrics
                    and lyrics_lookup.match_confidence >= 0.90
                ):
                    sentences, lyrics_matched = reconcile_synced_lyrics_excerpt(
                        lyrics_lookup.synced_lyrics, sentences
                    )
                if lyrics_matched:
                    lyrics_source = LyricsSource.lrclib
                else:
                    lyrics = "\n".join(sentence.lyrics for sentence in sentences)

            arrangement_mode = select_arrangement_mode(arrangement_source_lyrics)
            vocal_parts: list[VocalPart] = []
            if arrangement_mode == VocalArrangementMode.dual_track:
                self._advance(job, AnalysisStage.analyzing_vocal_parts)
                vocal_parts_path = job_dir / "vocal-parts" / "parts-v3.json"
                cached_vocal_parts = _load_vocal_parts(vocal_parts_path)
                if cached_vocal_parts is not None:
                    self._mark_cache_hit(job, AnalysisStage.analyzing_vocal_parts)
                    vocal_parts = cached_vocal_parts
                else:
                    transcript = json.loads(
                        alignment_artifacts.alignment_json.read_text(encoding="utf-8")
                    )
                    dual_pipeline = DualTrackArrangementPipeline(self.vocal_part_analyzer)
                    try:
                        if self.vocal_part_analyzer is not None:
                            self._record_api_call(job, AnalysisStage.analyzing_vocal_parts)
                        vocal_parts = await dual_pipeline.analyze(
                            vocal_audio=analysis_vocals,
                            duration_seconds=duration,
                            transcript=transcript,
                            sentences=sentences,
                        )
                    except Exception as exc:
                        job.warnings.append(
                            AnalysisWarning(
                                stage=AnalysisStage.analyzing_vocal_parts,
                                message="双轨声部时间核查失败，已保留确定歌词并使用句级时间。",
                                detail=str(exc),
                            )
                        )
                        self.job_store.save(job)
                        vocal_parts = await DualTrackArrangementPipeline().analyze(
                            vocal_audio=analysis_vocals,
                            duration_seconds=duration,
                            transcript=transcript,
                            sentences=sentences,
                        )
                    _save_json(
                        vocal_parts_path,
                        [part.model_dump(mode="json", by_alias=True) for part in vocal_parts],
                    )
            else:
                vocal_parts = await SingleTrackArrangementPipeline().analyze(
                    vocal_audio=analysis_vocals,
                    duration_seconds=duration,
                    transcript={},
                    sentences=sentences,
                )

            profile_language = _detect_lyrics_language(lyrics) or alignment.language
            sentences = add_pronunciation_guides(sentences, profile_language)
            language_analysis_provider = self.language_coach.provider
            language_analysis_model = self.language_coach.model
            if supports_language_coaching(profile_language):
                candidates = generate_language_candidates(
                    sentences, language=profile_language
                )
                self._advance(job, AnalysisStage.analyzing_language)
                observation_fingerprint = _language_cache_fingerprint(lyrics, candidates)
                observations_path = (
                    job_dir
                    / "language"
                    / f"observations-v6-{observation_fingerprint}.json"
                )
                observations = _load_observations(observations_path)
                if observations is None:
                    if self.language_coach.provider != "disabled":
                        self._record_api_call(job, AnalysisStage.analyzing_language)
                    observations = await self.language_coach.analyze(
                        analysis_vocals, lyrics, sentences, candidates
                    )
                    _save_json(
                        observations_path,
                        observations.model_dump(mode="json", by_alias=True),
                    )
                else:
                    self._mark_cache_hit(job, AnalysisStage.analyzing_language)
                annotated_sentences = apply_language_observations(
                    sentences,
                    candidates,
                    observations.observations,
                    provider=self.language_coach.provider,
                    model=self.language_coach.model,
                )
            else:
                annotated_sentences = sentences
                language_analysis_provider = "skipped_chinese"
                language_analysis_model = None

            self._advance(job, AnalysisStage.building_profile)
            _publish_audio_assets(
                source=source,
                vocals=separation.vocals,
                accompaniment=separation.accompaniment,
                song_dir=self.profile_store.songs_dir / job.song_id,
            )
            profile = build_song_profile(
                song_id=job.song_id,
                title=job.title,
                duration_seconds=duration,
                language=profile_language,
                audio=AudioAssets(
                    source_url=f"/api/v1/songs/{job.song_id}/audio/source",
                    vocal_url=f"/api/v1/songs/{job.song_id}/audio/vocals",
                    accompaniment_url=(
                        f"/api/v1/songs/{job.song_id}/audio/accompaniment"
                    ),
                ),
                sentences=annotated_sentences,
                pipeline_version=PIPELINE_VERSION,
                separation_model=self.separation_model,
                alignment_model=self.alignment_model,
                language_analysis_provider=language_analysis_provider,
                language_analysis_model=language_analysis_model,
                lyrics_source=lyrics_source,
                lyrics_provider=lyrics_lookup.provider if lyrics_lookup else None,
                lyrics_provider_track_id=(
                    lyrics_lookup.provider_track_id if lyrics_lookup else None
                ),
                lyrics_match_confidence=(
                    lyrics_lookup.match_confidence if lyrics_lookup else None
                ),
                vocal_parts=vocal_parts,
                vocal_arrangement_mode=arrangement_mode,
                created_at=datetime.now(UTC),
            )
            self.profile_store.save(profile)
            self._advance(job, AnalysisStage.completed, AnalysisStatus.completed)
        except Exception as exc:
            failed_stage = job.stage
            self._finish_active_stage(job)
            job.status = AnalysisStatus.failed
            job.stage = AnalysisStage.failed
            job.error = AnalysisError(
                code=f"{failed_stage.value}_failed",
                stage=failed_stage,
                message=_stage_error_message(failed_stage),
                detail=str(exc),
            )
            self.job_store.save(job)

    def _advance(
        self,
        job,
        stage: AnalysisStage,
        status: AnalysisStatus = AnalysisStatus.processing,
    ) -> None:
        previous_stage = job.stage
        now = datetime.now(UTC)
        current = next(
            (item for item in job.stage_runtimes if item.stage == previous_stage),
            None,
        )
        if current is not None and current.completed_at is None and previous_stage != stage:
            current.completed_at = now
            current.elapsed_seconds = round(
                (current.completed_at - current.started_at).total_seconds(), 3
            )
        job.status = status
        job.stage = stage
        job.progress = STAGE_PROGRESS[stage]
        job.error = None
        if stage not in {AnalysisStage.completed, AnalysisStage.failed}:
            target = next((item for item in job.stage_runtimes if item.stage == stage), None)
            if target is None:
                base, ratio = STAGE_ESTIMATE.get(stage, (0.0, 0.0))
                estimated = (
                    round(base + ratio * job.audio_duration_seconds, 1)
                    if job.audio_duration_seconds is not None
                    else None
                )
                job.stage_runtimes.append(
                    StageRuntime(
                        stage=stage,
                        started_at=now,
                        estimated_seconds=estimated,
                    )
                )
            elif target.completed_at is not None:
                target.started_at = now
                target.completed_at = None
                target.run_count += 1
        job.estimated_remaining_seconds = self._estimated_remaining(job, stage)
        self.job_store.save(job)

    def _apply_estimates(self, job, duration: float) -> None:
        total = 0.0
        for stage, (base, ratio) in STAGE_ESTIMATE.items():
            estimated = round(base + ratio * duration, 1)
            total += estimated
            runtime = next((item for item in job.stage_runtimes if item.stage == stage), None)
            if runtime is not None:
                runtime.estimated_seconds = estimated
        job.estimated_total_seconds = round(total, 1)
        job.estimated_remaining_seconds = round(total, 1)

    def _record_api_call(self, job, stage: AnalysisStage) -> None:
        runtime = next((item for item in job.stage_runtimes if item.stage == stage), None)
        if runtime is not None:
            runtime.api_call_count += 1
        job.api_call_count += 1
        self.job_store.save(job)

    def _mark_cache_hit(self, job, stage: AnalysisStage) -> None:
        runtime = next((item for item in job.stage_runtimes if item.stage == stage), None)
        if runtime is not None:
            runtime.cache_hit = True
        self.job_store.save(job)

    def _estimated_remaining(self, job, current_stage: AnalysisStage) -> float | None:
        if job.estimated_total_seconds is None:
            return None
        remaining = 0.0
        reached_current = False
        for stage in STAGE_ESTIMATE:
            if stage == current_stage:
                reached_current = True
            if not reached_current:
                continue
            runtime = next((item for item in job.stage_runtimes if item.stage == stage), None)
            if runtime is not None:
                remaining += runtime.estimated_seconds or 0
            elif job.audio_duration_seconds is not None:
                base, ratio = STAGE_ESTIMATE[stage]
                remaining += base + ratio * job.audio_duration_seconds
        return round(remaining, 1)

    def _finish_active_stage(self, job) -> None:
        runtime = next(
            (item for item in job.stage_runtimes if item.stage == job.stage),
            None,
        )
        if runtime is None or runtime.completed_at is not None:
            return
        runtime.completed_at = datetime.now(UTC)
        runtime.elapsed_seconds = round(
            (runtime.completed_at - runtime.started_at).total_seconds(), 3
        )


def build_default_pipeline(settings: Settings) -> SongAnalysisPipeline:
    project_root = Path(__file__).resolve().parents[2]

    def executable(path: Path) -> str:
        return str(path if path.is_absolute() else project_root / path)

    language_coach: LanguageCoach = DisabledLanguageCoach()
    vocal_part_analyzer: VocalPartAnalyzer | None = None
    if settings.language_analysis_provider == "gemini":
        if settings.gemini_api_key is None:
            raise ValueError(
                "VERSEVIVA_GEMINI_API_KEY is required when language analysis provider is gemini"
            )
        language_coach = GeminiLanguageCoach(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
        )
        vocal_part_analyzer = GeminiVocalPartAnalyzer(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
        )

    lyrics_provider: LyricsProvider = DisabledLyricsProvider()
    if settings.lyrics_provider == "lrclib":
        lyrics_provider = LrclibLyricsProvider(
            base_url=settings.lrclib_base_url,
            timeout_seconds=settings.lrclib_timeout_seconds,
            min_match_score=settings.lrclib_min_match_score,
        )

    return SongAnalysisPipeline(
        separator=DemucsAdapter(
            executable=executable(settings.demucs_executable),
            model_name=settings.demucs_model,
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
        alignment_model=f"whisperx-{settings.whisperx_model}",
        lyrics_provider=lyrics_provider,
        language_coach=language_coach,
        vocal_part_analyzer=vocal_part_analyzer,
    )


def _publish_audio_assets(
    *, source: Path, vocals: Path, accompaniment: Path, song_dir: Path
) -> None:
    audio_dir = song_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    copy2(source, audio_dir / f"source{source.suffix.lower()}")
    copy2(vocals, audio_dir / "vocals.wav")
    copy2(accompaniment, audio_dir / "accompaniment.wav")
    _create_web_audio(vocals, audio_dir / "vocals.mp3")
    _create_web_audio(accompaniment, audio_dir / "accompaniment.mp3")


def _create_web_audio(source: Path, destination: Path) -> None:
    """Create a compact browser asset while retaining WAV for analysis."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        destination.unlink(missing_ok=True)


def _save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _load_lyrics_lookup(path: Path) -> LyricsLookupResult | None:
    if not path.is_file():
        return None
    try:
        return LyricsLookupResult(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _load_observations(path: Path) -> LanguageObservationBatch | None:
    if not path.is_file():
        return None
    try:
        return LanguageObservationBatch.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def _load_vocal_parts(path: Path) -> list[VocalPart] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [VocalPart.model_validate(item) for item in payload]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _stage_error_message(stage: AnalysisStage) -> str:
    messages = {
        AnalysisStage.probing_audio: "无法读取音频信息。",
        AnalysisStage.separating_vocals: "人声分离失败。",
        AnalysisStage.fetching_lyrics: "联网歌词查询失败。",
        AnalysisStage.aligning_lyrics: "歌词时间对齐失败。",
        AnalysisStage.analyzing_vocal_parts: "双轨 Vocal 解析失败。",
        AnalysisStage.analyzing_language: "语言现象分析失败。",
        AnalysisStage.building_profile: "教学标注生成失败。",
    }
    return messages.get(stage, "歌曲分析没有完成。")


def _detect_lyrics_language(lyrics: str) -> str | None:
    korean = sum("\uac00" <= char <= "\ud7a3" for char in lyrics)
    japanese_kana = sum(
        "\u3040" <= char <= "\u30ff" for char in lyrics
    )
    japanese_kanji = sum("\u3400" <= char <= "\u9fff" for char in lyrics)
    latin = sum(char.isascii() and char.isalpha() for char in lyrics)
    if korean >= 2 and korean > japanese_kana + japanese_kanji and korean >= latin * 0.2:
        return "ko"
    if (
        japanese_kana >= 2
        and japanese_kana + japanese_kanji > korean
        and japanese_kana >= latin * 0.2
    ):
        return "ja"
    if japanese_kanji >= 2 and japanese_kana == 0 and korean == 0:
        return "zh"
    return None


def _language_cache_fingerprint(
    lyrics: str, candidates: list[LanguageCandidate]
) -> str:
    payload = {
        "lyrics": lyrics,
        "candidates": [
            candidate.model_dump(mode="json", by_alias=True) for candidate in candidates
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
