from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VerseViva API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    data_dir: Path = Path("data")
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
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
    language_analysis_provider: Literal["disabled", "gemini"] = "disabled"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VERSEVIVA_",
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

