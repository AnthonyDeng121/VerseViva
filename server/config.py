from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VocalCompass API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    data_dir: Path = Path("data")
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_size_bytes: int = 100 * 1024 * 1024
    auto_run_analysis_pipeline: bool = True
    demucs_executable: Path = Path(".venv-demucs/bin/demucs")
    demucs_model: str = "htdemucs"
    basic_pitch_executable: Path = Path(".venv-pitch/bin/basic-pitch")
    whisperx_executable: Path = Path(".venv-whisperx/bin/whisperx")
    whisperx_model: str = "small"
    whisperx_device: str = "cpu"
    whisperx_compute_type: str = "int8"
    ffprobe_executable: str = "ffprobe"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOCALCOMPASS_",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

