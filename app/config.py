"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_id: int = Field(alias="API_ID")
    api_hash: str = Field(alias="API_HASH")
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids_raw: str = Field(alias="ADMIN_IDS")
    mongodb_uri: str = Field(alias="MONGODB_URI")
    heroku_api_key: str = Field(alias="HEROKU_API_KEY")
    encryption_key: str = Field(alias="ENCRYPTION_KEY")
    github_webhook_secret: str = Field(alias="GITHUB_WEBHOOK_SECRET")

    mongodb_database: str = Field(default="heroku_manager", alias="MONGODB_DATABASE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_region: str = Field(default="eu", alias="DEFAULT_REGION")
    default_dyno_type: str = Field(default="standard-1x", alias="DEFAULT_DYNO_TYPE")

    @property
    def admin_ids(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_ids_raw.split(",") if x.strip()}

    @property
    def mongodb_configured(self) -> bool:
        return bool(self.mongodb_uri)


@lru_cache
def get_settings() -> Settings:
    return Settings()
