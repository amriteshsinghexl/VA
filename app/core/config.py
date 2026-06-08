from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False
    reload: bool = False

    # CORS â€” allow the FIA UI dev and production servers
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Project root â€” resolved from this file: app/core/ â†’ ../../
    base_dir: str = str(Path(__file__).resolve().parent.parent.parent)

    # Python executable used to spawn abc_corp_va/run.py
    python_exec: str = "python"

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    model_config = SettingsConfigDict(
        env_prefix="VA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
