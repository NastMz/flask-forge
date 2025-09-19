from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_env: str = Field("development", alias="APP_ENV")
    secret_key: str = Field("change-me", alias="SECRET_KEY")
    port: int = Field(8000, alias="PORT")
    database_url: str = Field("sqlite:///app.db", alias="DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")