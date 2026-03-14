import os
from pathlib import Path


def _load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


GARMIN_EMAIL = _require("GARMIN_EMAIL")
GARMIN_PASSWORD = _require("GARMIN_PASSWORD")
OPENWEATHER_API_KEY = _require("OPENWEATHER_API_KEY")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "quantifiedstrides")
DB_USER = _require("DB_USER")
DB_PASSWORD = _require("DB_PASSWORD")

ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
