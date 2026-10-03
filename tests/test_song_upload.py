from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.config import get_settings
from server.main import app


@pytest.fixture
def upload_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOCALCOMPASS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VOCALCOMPASS_MAX_UPLOAD_SIZE_BYTES", "32")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client, tmp_path
    get_settings.cache_clear()


def test_upload_creates_independent_ids_and_isolated_task_directory(upload_client) -> None:
    client, data_dir = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("Demo.MP3", b"ID3-valid-demo", "audio/mpeg")},
        data={"title": "  Demo Song  ", "lyrics": "hello"},
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
    )

    assert response.status_code == expected_status
    assert list((data_dir / "jobs").iterdir()) == []


def test_recognized_extension_accepts_generic_browser_content_type(upload_client) -> None:
    client, _ = upload_client
    response = client.post(
        "/api/v1/songs/analyze",
        files={"audio": ("demo.flac", b"fLaC-demo", "application/octet-stream")},
    )

    assert response.status_code == 202


def test_missing_or_malformed_job_id_returns_404(upload_client) -> None:
    client, _ = upload_client

    assert client.get("/api/v1/songs/jobs/job_00000000000000000000000000000000").status_code == 404
    assert client.get("/api/v1/songs/jobs/not-a-job-id").status_code == 404
