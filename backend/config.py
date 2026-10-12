"""Настройки приложения из переменных окружения."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    BOT_TOKEN: str = ""
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'database.db'}"
    FRONTEND_ORIGINS: str = ""
    OFF_BASE_URL: str = "https://world.openfoodfacts.org"
    OFF_SEARCH_URL: str = "https://search.openfoodfacts.org/search"
    OFF_CONTACT_EMAIL: str = "caloriebot@example.com"
    OFF_CACHE_TTL_DAYS: int = 30
    OFF_SEARCH_MAX_PER_MINUTE: int = 8
    INIT_DATA_MAX_AGE: int = 86400
    DEV_MODE: bool = False
    DEV_USER_ID: int = 1
    LOG_LEVEL: str = "INFO"

    @property
    def frontend_origins_list(self) -> list[str]:
        """Список разрешённых origin для CORS без пустых строк и пробелов."""
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]


settings = Settings()
