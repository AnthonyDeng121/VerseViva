import asyncio
import json
from pathlib import Path

from server.models.song import AnalysisJob, AnalysisStage, AnalysisStatus
from server.pipelines.contracts import (
    AlignmentArtifacts,
    PitchArtifacts,
    SeparationArtifacts,
)
from server.pipelines.song_analysis import SongAnalysisPipeline
from server.services.language import (
    EvidenceStrength,
    LanguageObservation,
    LanguageObservationBatch,
    ObservationResult,
)
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore


class FakeSeparator:
    async def separate(self, source: Path, output_dir: Path) -> SeparationArtifacts:
        output_dir.mkdir(parents=True)
        vocals = output_dir / "vocals.wav"
        accompaniment = output_dir / "no_vocals.wav"
        vocals.write_bytes(b"vocals")
        accompaniment.write_bytes(b"music")
        return SeparationArtifacts(vocals=vocals, accompaniment=accompaniment)


class FakePitchExtractor:
    async def extract(self, vocal_audio: Path, output_dir: Path) -> PitchArtifacts:
        output_dir.mkdir(parents=True)
        csv_path = output_dir / "vocals_basic_pitch.csv"
        csv_path.write_text(
            "start_time_s,end_time_s,pitch_midi,velocity,pitch_bend\n"
            "0.5,1.5,60,100,0,1,0\n"
            "1.5,2.5,64,90,0,0\n",
            encoding="utf-8",
        )
        midi = output_dir / "vocals_basic_pitch.mid"
        npz = output_dir / "vocals_basic_pitch.npz"
        midi.write_bytes(b"midi")
        npz.write_bytes(b"npz")
        return PitchArtifacts(note_events_csv=csv_path, midi=midi, model_output_npz=npz)


class FakeLyricsAligner:
    async def align(
        self, vocal_audio: Path, output_dir: Path, language: str | None = None
    ) -> AlignmentArtifacts:
        output_dir.mkdir(parents=True)
        alignment = output_dir / "vocals.json"
        alignment.write_text(
            json.dumps(
                {
                    "language": "en",
                    "segments": [
                        {
                            "start": 0.4,
                            "end": 2.0,
                            "text": "hello world",
                            "words": [
                                {"word": "hello", "start": 0.4, "end": 1.0, "score": 0.9},
                                {"word": "world", "start": 1.1, "end": 2.0, "score": 0.8},
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return AlignmentArtifacts(alignment_json=alignment)


class FakeDurationProbe:
    async def duration_seconds(self, source: Path) -> float:
        return 3.0


class FailingSeparator:
    async def separate(self, source: Path, output_dir: Path) -> SeparationArtifacts:
        raise RuntimeError("separation exploded")


class FakeLanguageCoach:
    provider = "fake-audio-llm"
    model = "fake-language-model"

    async def analyze(self, vocal_audio, lyrics, sentences, candidates):
        return LanguageObservationBatch(
            lyrics_match="match",
            observations=[
                LanguageObservation(
                    candidate_id=candidates[0].id,
                    result=ObservationResult.linked_or_resegmented,
                    evidence_strength=EvidenceStrength.strong,
                    audible_evidence=["前词尾音直接承接后词。"],
                    needs_human_review=False,
                )
            ],
        )


def make_job(data_dir: Path) -> tuple[AnalysisJob, Path, JobStore, ProfileStore]:
    job_id = "job_0123456789abcdef0123456789abcdef"
    song_id = "song_0123456789abcdef0123456789abcdef"
    source = data_dir / "jobs" / job_id / "input" / "source.mp3"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"ID3-audio")
    job_store = JobStore(data_dir)
    profile_store = ProfileStore(data_dir)
    job = AnalysisJob(
        job_id=job_id,
        song_id=song_id,
        status=AnalysisStatus.queued,
        title="Demo Song",
        has_lyrics=False,
    )
    job_store.save(job)
    return job, source, job_store, profile_store


def make_pipeline(
    job_store: JobStore,
    profile_store: ProfileStore,
    separator=None,
    language_coach=None,
) -> SongAnalysisPipeline:
    return SongAnalysisPipeline(
        separator=separator or FakeSeparator(),
        pitch_extractor=FakePitchExtractor(),
        lyrics_aligner=FakeLyricsAligner(),
        duration_probe=FakeDurationProbe(),
        job_store=job_store,
        profile_store=profile_store,
        separation_model="fake-demucs",
        pitch_model="fake-pitch",
        alignment_model="fake-whisperx",
        language_coach=language_coach,
    )


def test_pipeline_builds_and_persists_song_profile(tmp_path: Path) -> None:
    job, source, job_store, profile_store = make_job(tmp_path)

    asyncio.run(make_pipeline(job_store, profile_store).run(job.job_id, source))

    completed = job_store.get(job.job_id)
    assert completed is not None
    assert completed.status == AnalysisStatus.completed
    assert completed.stage == AnalysisStage.completed
    assert completed.progress == 100

    profile = profile_store.get(job.song_id)
    assert profile is not None
    assert profile.language == "en"
    assert profile.duration_seconds == 3.0
    assert profile.vocal_range is not None
    assert profile.vocal_range.lowest_note == "C4"
    assert profile.vocal_range.highest_note == "E4"
    assert len(profile.sentences[0].notes) == 2
    assert len(profile.sentences[0].pitch_contour) == 3
    assert profile.analysis.pitch_processing is not None
    assert profile.analysis.pitch_processing.output_pitch_point_count == 4
    assert profile.analysis.pitch_processing.fallback_used is True
    assert profile.analysis.pipeline_version == "language-annotation-v1"
    assert profile.analysis.pitch_model == "fake-pitch"
    assert profile.analysis.language_analysis_provider == "disabled"
    assert (
        tmp_path / "songs" / job.song_id / "audio" / "source.mp3"
    ).read_bytes() == b"ID3-audio"
    assert (tmp_path / "songs" / job.song_id / "audio" / "vocals.wav").read_bytes() == b"vocals"


def test_pipeline_persists_failure_stage_and_message(tmp_path: Path) -> None:
    job, source, job_store, profile_store = make_job(tmp_path)

    asyncio.run(
        make_pipeline(job_store, profile_store, separator=FailingSeparator()).run(
            job.job_id, source
        )
    )

    failed = job_store.get(job.job_id)
    assert failed is not None
    assert failed.status == AnalysisStatus.failed
    assert failed.stage == AnalysisStage.failed
    assert failed.error is not None
    assert failed.error.stage == AnalysisStage.separating_vocals
    assert failed.error.code == "separating_vocals_failed"
    assert "separation exploded" in (failed.error.detail or "")


def test_pipeline_maps_audio_model_observation_into_profile_hint(tmp_path: Path) -> None:
    job, source, job_store, profile_store = make_job(tmp_path)

    asyncio.run(
        make_pipeline(
            job_store,
            profile_store,
            language_coach=FakeLanguageCoach(),
        ).run(job.job_id, source)
    )

    profile = profile_store.get(job.song_id)
    assert profile is not None
    assert profile.sentences[0].language_hints[0].marks[0].symbol == "‿"
    assert profile.analysis.language_analysis_provider == "fake-audio-llm"
