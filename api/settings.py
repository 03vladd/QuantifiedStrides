"""
API settings loaded from environment variables / .env file.
Separate from the pipeline config.py — API concerns only.
"""

import os
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings


def _find_env() -> Path:
    return Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "quantifiedstrides"
    db_user: str
    db_password: str
    db_echo: bool = False          # set True in dev to log SQL

    # API
    api_cors_origins: list[str] = ["http://localhost:5173"]   # Vite default port

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "QuantifiedStrides <noreply@quantifiedstrides.com>"

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # Anthropic
    anthropic_api_key: str

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": str(_find_env()), "extra": "ignore"}


settings = Settings()
