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
    web_dist_dir: Path = Path("web/dist")
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    max_upload_size_bytes: int = 100 * 1024 * 1024
    max_recording_size_bytes: int = 25 * 1024 * 1024
    auto_run_analysis_pipeline: bool = True
    demucs_executable: Path = Path(".venv-demucs/bin/demucs")
    demucs_model: str = "htdemucs"
    whisperx_executable: Path = Path(".venv-whisperx/bin/whisperx")
    whisperx_model: str = "small"
    whisperx_device: str = "cpu"
    whisperx_compute_type: str = "int8"
    ffprobe_executable: str = "ffprobe"
    lyrics_provider: Literal["disabled", "lrclib"] = "lrclib"
    lrclib_base_url: str = "https://lrclib.net"
    lrclib_timeout_seconds: float = 10.0
    lrclib_min_match_score: float = 0.78
    language_analysis_provider: Literal["disabled", "gemini"] = "disabled"
    language_worker_url: str | None = None
    language_worker_token: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    practice_acoustic_provider: Literal["disabled", "gemini"] = "gemini"
    practice_issue_confidence_threshold: float = 0.65
    glm_api_key: SecretStr | None = None
    glm_model: str = "glm-4.7-flash"
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_timeout_seconds: float = 45.0

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

