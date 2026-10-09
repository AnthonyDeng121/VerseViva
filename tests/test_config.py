from pathlib import Path

from server.config import Settings


def test_settings_use_verseviva_environment_names(monkeypatch) -> None:
    monkeypatch.setenv("VERSEVIVA_ENV", "production")
    monkeypatch.setenv("VERSEVIVA_DATA_DIR", "./data")
    monkeypatch.setenv(
        "VERSEVIVA_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    monkeypatch.setenv("VOCALCOMPASS_DATA_DIR", "/should/not/be/read")

    settings = Settings(_env_file=None)

    assert settings.data_dir == Path("data")
    assert settings.environment == "production"
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_default_model_commands_are_project_relative() -> None:
    settings = Settings(_env_file=None)

    assert not settings.demucs_executable.is_absolute()
    assert not settings.whisperx_executable.is_absolute()
