import os
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file()


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class Settings:
    app_name: str = os.getenv("APP_NAME", "InfoGlobe API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_description: str = os.getenv(
        "APP_DESCRIPTION",
        "API inicial para consultar informacoes globais.",
    )
    api_prefix: str = os.getenv("API_PREFIX", "")
    rest_countries_api_key: str = os.getenv("API_KEY_REST_COUNTRIES", "")
    openrouter_api_key: str = os.getenv("API_KEY_OPENROUTER", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "")
    mongo_db_url_conn: str = os.getenv("MONGO_DB_URL_CONN", "")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "infoglobe")
    mongo_country_collection: str = os.getenv(
        "MONGO_COUNTRY_COLLECTION",
        "country_info_cache",
    )
    rate_limit_requests_per_minute: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "10")
    )
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    cors_allow_origins: list[str] = _parse_csv_env("CORS_ALLOW_ORIGINS", "*")


settings = Settings()
