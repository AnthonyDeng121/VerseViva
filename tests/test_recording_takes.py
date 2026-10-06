from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.config import get_settings
from server.main import app
from server.storage.profile_store import ProfileStore
from tests.test_song_profile_schema import make_profile


@pytest.fixture
def take_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERSEVIVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERSEVIVA_MAX_RECORDING_SIZE_BYTES", "64")
    get_settings.cache_clear()
    song_id = "song_0123456789abcdef0123456789abcdef"
    ProfileStore(tmp_path).save(make_profile().model_copy(update={"song_id": song_id}))
    with TestClient(app) as client:
        yield client, tmp_path, song_id
    get_settings.cache_clear()


def _webm_upload(client: TestClient, song_id: str, **overrides):
    data = {
        "session_id": "session_mobile_01",
        "track_slot_id": "practice_sentence_001",
        "selection_type": "sentence",
        "sentence_ids": '["sentence_001"]',
        "selection_start_seconds": "0.852",
        "selection_end_seconds": "5.1",
        "timeline_start_seconds": "0.852",
        "save_mode": "practice_replace",
        "client_duration_seconds": "4.4",
        **overrides,
    }
    return client.post(
        f"/api/v1/songs/{song_id}/takes",
        data=data,
        files={"audio": ("recording.webm", b"\x1aE\xdf\xa3mobile-audio", "audio/webm")},
    )


def test_mobile_webm_sentence_take_uploads_and_restores(take_client) -> None:
    client, data_dir, song_id = take_client

    response = _webm_upload(client, song_id)

    assert response.status_code == 201
    payload = response.json()
    assert payload["selectionType"] == "sentence"
    assert payload["sentenceIds"] == ["sentence_001"]
    assert payload["isCurrent"] is True
    assert (data_dir / "takes" / payload["takeId"] / "original.webm").is_file()
    assert client.get(payload["audioUrl"]).content.startswith(b"\x1aE\xdf\xa3")
    restored = client.get(f"/api/v1/songs/{song_id}/takes?session_id=session_mobile_01")
    assert restored.status_code == 200
    assert [item["takeId"] for item in restored.json()] == [payload["takeId"]]


def test_practice_replace_only_supersedes_current_session_track(take_client) -> None:
    client, _, song_id = take_client
    first = _webm_upload(client, song_id).json()
    second = _webm_upload(client, song_id).json()
    other_session = _webm_upload(
        client,
        song_id,
        session_id="session_mobile_02",
    ).json()

    takes = client.get(f"/api/v1/songs/{song_id}/takes").json()
    by_id = {take["takeId"]: take for take in takes}
    assert by_id[first["takeId"]]["isCurrent"] is False
    assert by_id[first["takeId"]]["supersededByTakeId"] == second["takeId"]
    assert by_id[second["takeId"]]["isCurrent"] is True
    assert by_id[other_session["takeId"]]["isCurrent"] is True
    assert client.get(first["audioUrl"]).status_code == 200


def test_segment_and_overdub_takes_append_without_covering_previous_audio(take_client) -> None:
    client, _, song_id = take_client
    data = {
        "track_slot_id": "secondary_layer_01",
        "selection_type": "segment",
        "sentence_ids": '["sentence_001"]',
        "selection_start_seconds": "1.0",
        "selection_end_seconds": "4.8",
        "timeline_start_seconds": "1.0",
        "save_mode": "overdub_append",
    }
    first = _webm_upload(client, song_id, **data).json()
    second = _webm_upload(client, song_id, **data).json()

    takes = client.get(
        f"/api/v1/songs/{song_id}/takes?session_id=session_mobile_01"
    ).json()
    by_id = {take["takeId"]: take for take in takes}
    assert first["selectionType"] == "segment"
    assert by_id[first["takeId"]]["isCurrent"] is True
    assert by_id[second["takeId"]]["isCurrent"] is True
    assert by_id[first["takeId"]]["supersededByTakeId"] is None


def test_take_upload_rejects_unknown_sentence_and_mismatched_media(take_client) -> None:
    client, data_dir, song_id = take_client

    unknown = _webm_upload(client, song_id, sentence_ids='["sentence_missing"]')
    mismatched = client.post(
        f"/api/v1/songs/{song_id}/takes",
        data={
            "session_id": "session_mobile_01",
            "track_slot_id": "practice_sentence_001",
            "selection_type": "sentence",
            "sentence_ids": '["sentence_001"]',
            "selection_start_seconds": "0.852",
            "selection_end_seconds": "5.1",
            "timeline_start_seconds": "0.852",
            "save_mode": "practice_replace",
        },
        files={"audio": ("recording.mp4", b"not-an-mp4", "audio/mp4")},
    )

    assert unknown.status_code == 422
    assert mismatched.status_code == 415
    assert list((data_dir / "takes").glob("take_*/take.json")) == []
