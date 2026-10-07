from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.api.routes import songs as songs_route
from server.config import get_settings
from server.main import app
from server.models.song import AnalysisError, AnalysisStage, AnalysisStatus
from server.storage.job_store import JobStore
from server.storage.profile_store import ProfileStore
from tests.test_song_profile_schema import make_profile


@pytest.fixture
def upload_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERSEVIVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERSEVIVA_MAX_UPLOAD_SIZE_BYTES", "32")
    monkeypatch.setenv("VERSEVIVA_AUTO_RUN_ANALYSIS_PIPELINE", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client, tmp_path
    get_settings.cache_clear()


def test_upload_creates_independent_ids_and_isolated_task_directory(upload_client) -> None:
    client, data_dir = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("Demo.MP3", b"ID3-valid-demo", "audio/mpeg")},
        data={"title": "  Demo Song  ", "artist": "Demo Artist", "lyrics": "hello"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["song_id"].startswith("song_")
    assert payload["job_id"].removeprefix("job_") != payload["song_id"].removeprefix("song_")
    assert payload["title"] == "Demo Song"
    assert payload["has_lyrics"] is True
    saved_audio = data_dir / "jobs" / payload["job_id"] / "input" / "source.mp3"
    assert saved_audio.read_bytes() == b"ID3-valid-demo"
    assert (saved_audio.parent / "lyrics.txt").read_text(encoding="utf-8") == "hello"
    assert (saved_audio.parents[1] / "job.json").is_file()

    query_response = client.get(f"/api/v1/songs/jobs/{payload['job_id']}")
    assert query_response.status_code == 200
    assert query_response.json() == payload


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_status"),
    [
        ("demo.txt", b"text", "text/plain", 415),
        ("demo.mp3", b"ID3", "text/plain", 415),
        ("demo.mp3", b"", "audio/mpeg", 400),
        ("demo.mp3", b"not-an-mp3", "audio/mpeg", 415),
        ("demo.wav", b"ID3-wrong-format", "audio/wav", 415),
        ("demo.flac", b"fLaC" + b"x" * 29, "audio/flac", 413),
    ],
)
def test_upload_rejects_invalid_audio(
    upload_client,
    filename: str,
    content: bytes,
    content_type: str,
    expected_status: int,
) -> None:
    client, data_dir = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={"audio": (filename, content, content_type)},
        data={"title": "Demo", "artist": "Artist"},
    )

    assert response.status_code == expected_status
    assert list((data_dir / "jobs").iterdir()) == []


def test_recognized_extension_accepts_generic_browser_content_type(upload_client) -> None:
    client, _ = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("demo.flac", b"fLaC-demo", "application/octet-stream")},
        data={"title": "Demo", "artist": "Artist"},
    )

    assert response.status_code == 202


def test_upload_requires_artist_and_title_even_when_filename_contains_them(upload_client) -> None:
    client, _ = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={
            "audio": (
                "Sabrina Carpenter - Juno.mp3",
                b"ID3-demo",
                "audio/mpeg",
            )
        },
    )

    assert response.status_code == 422


def test_missing_or_malformed_job_id_returns_404(upload_client) -> None:
    client, _ = upload_client

    assert client.get("/api/v1/songs/jobs/job_00000000000000000000000000000000").status_code == 404
    assert client.get("/api/v1/songs/jobs/not-a-job-id").status_code == 404


def test_latest_job_endpoint_restores_most_recent_upload(upload_client) -> None:
    client, _ = upload_client
    uploaded = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("demo.mp3", b"ID3-demo", "audio/mpeg")},
        data={"title": "Demo", "artist": "Artist"},
    ).json()

    response = client.get("/api/v1/songs/jobs/latest")

    assert response.status_code == 200
    assert response.json()["job_id"] == uploaded["job_id"]


def test_upload_starts_automatic_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, Path]] = []

    class StubPipeline:
        async def run(self, job_id: str, source: Path) -> None:
            calls.append((job_id, source))

    monkeypatch.setenv("VERSEVIVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERSEVIVA_AUTO_RUN_ANALYSIS_PIPELINE", "true")
    monkeypatch.setattr(songs_route, "build_default_pipeline", lambda settings: StubPipeline())
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/songs/analyze",
            files={"audio": ("demo.mp3", b"ID3-demo", "audio/mpeg")},
            data={"title": "Demo", "artist": "Artist"},
        )
    get_settings.cache_clear()

    assert response.status_code == 202
    assert calls == [
        (
            response.json()["job_id"],
            tmp_path / "jobs" / response.json()["job_id"] / "input" / "source.mp3",
        )
    ]


def test_api_exposes_model_failure_after_background_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingPipeline:
        def __init__(self, data_dir: Path):
            self.store = JobStore(data_dir)

        async def run(self, job_id: str, source: Path) -> None:
            job = self.store.get(job_id)
            assert job is not None
            job.status = AnalysisStatus.failed
            job.stage = AnalysisStage.failed
            job.progress = 10
            job.error = AnalysisError(
                code="separating_vocals_failed",
                stage=AnalysisStage.separating_vocals,
                message="歌曲分析没有完成，请稍后重试。",
                detail="simulated Demucs failure",
            )
            self.store.save(job)

    monkeypatch.setenv("VERSEVIVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERSEVIVA_AUTO_RUN_ANALYSIS_PIPELINE", "true")
    monkeypatch.setattr(
        songs_route,
        "build_default_pipeline",
        lambda settings: FailingPipeline(settings.data_dir),
    )
    get_settings.cache_clear()
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/songs/analyze",
            files={"audio": ("demo.mp3", b"ID3-demo", "audio/mpeg")},
            data={"title": "Demo", "artist": "Artist"},
        )
        queried = client.get(f"/api/v1/songs/jobs/{upload.json()['job_id']}")
    get_settings.cache_clear()

    assert upload.status_code == 202
    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "failed"
    assert payload["stage"] == "failed"
    assert payload["error"]["code"] == "separating_vocals_failed"
    assert payload["error"]["stage"] == "separating_vocals"
    assert payload["error"]["message"] == "歌曲分析没有完成，请稍后重试。"
    assert "Demucs" in payload["error"]["detail"]


def test_failed_job_can_retry_with_original_audio(
    upload_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, data_dir = upload_client
    calls: list[tuple[str, Path]] = []

    class StubPipeline:
        async def run(self, job_id: str, source: Path) -> None:
            calls.append((job_id, source))

    upload = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("demo.mp3", b"ID3-demo", "audio/mpeg")},
        data={"title": "Demo", "artist": "Artist"},
    ).json()
    store = JobStore(data_dir)
    job = store.get(upload["job_id"])
    assert job is not None
    job.status = AnalysisStatus.failed
    job.stage = AnalysisStage.failed
    job.progress = 82
    job.error = AnalysisError(
        code="analyzing_language_failed",
        stage=AnalysisStage.analyzing_language,
        message="语言现象分析失败。",
        detail="503 high demand",
    )
    store.save(job)
    monkeypatch.setattr(songs_route, "build_default_pipeline", lambda settings: StubPipeline())

    response = client.post(f"/api/v1/songs/jobs/{job.job_id}/retry")

    assert response.status_code == 202
    assert calls == [
        (job.job_id, data_dir / "jobs" / job.job_id / "input" / "source.mp3")
    ]
    assert response.json()["error"] is None


def test_song_profile_query_returns_saved_profile(upload_client) -> None:
    client, data_dir = upload_client
    song_id = "song_0123456789abcdef0123456789abcdef"
    profile = make_profile().model_copy(update={"song_id": song_id})
    ProfileStore(data_dir).save(profile)

    response = client.get(f"/api/v1/songs/{song_id}")

    assert response.status_code == 200
    assert response.json()["songId"] == song_id
    assert response.json()["schemaVersion"] == "1.6"
    assert response.json()["sentences"][0]["words"][0]["text"] == "I"


def test_missing_or_malformed_song_profile_returns_404(upload_client) -> None:
    client, _ = upload_client

    missing = client.get("/api/v1/songs/song_00000000000000000000000000000000")
    malformed = client.get("/api/v1/songs/not-a-song-id")

    assert missing.status_code == 404
    assert malformed.status_code == 404


def test_song_audio_assets_are_served_only_for_existing_profiles(upload_client) -> None:
    client, data_dir = upload_client
    song_id = "song_0123456789abcdef0123456789abcdef"
    ProfileStore(data_dir).save(make_profile().model_copy(update={"song_id": song_id}))
    audio_dir = data_dir / "songs" / song_id / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / "source.mp3").write_bytes(b"ID3-source")
    (audio_dir / "vocals.wav").write_bytes(b"RIFF-vocals")
    (audio_dir / "accompaniment.wav").write_bytes(b"RIFF-accompaniment")
    (audio_dir / "vocals.mp3").write_bytes(b"ID3-compact-vocals")
    (audio_dir / "accompaniment.mp3").write_bytes(b"ID3-compact-accompaniment")

    assert client.get(f"/api/v1/songs/{song_id}/audio/source").content == b"ID3-source"
    assert client.get(f"/api/v1/songs/{song_id}/audio/vocals").content == (
        b"ID3-compact-vocals"
    )
    assert client.get(f"/api/v1/songs/{song_id}/audio/accompaniment").content == (
        b"ID3-compact-accompaniment"
    )
    assert client.get(f"/api/v1/songs/{song_id}/audio/unknown").status_code == 404
