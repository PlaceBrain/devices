import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PostgresDsn
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent


class AppSettings(BaseModel):
    debug: bool = Field(default=False)
    port: int = Field(default=50053)


class LoggingConfig(BaseModel):
    level: Literal[
        "debug",
        "info",
        "warning",
        "error",
        "critical",
    ] = Field(default="info")
    format: str = Field(
        default=(
            "[%(asctime)s.%(msecs)03d] %(module)10s:%(lineno)-3d %(levelname)-7s - %(message)s"
        )
    )
    date_format: str = Field(default="%Y-%m-%d %H:%M:%S")

    @property
    def level_value(self) -> int:
        return logging.getLevelNamesMapping()[self.level.upper()]


class PostgresConfig(BaseModel):
    url: PostgresDsn = Field(default=...)
    echo: bool = Field(default=False)
    echo_pool: bool = Field(default=False)
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=5)
    pool_pre_ping: bool = Field(default=True)
    pool_timeout: int = Field(default=30)


class MqttConfig(BaseModel):
    url: str = Field(default="mqtt://placebrain-emqx:1883")


class RedisConfig(BaseModel):
    url: str = Field(default="redis://placebrain-redis:6379/0")


class Settings(BaseSettings):
    app: AppSettings = Field(default=...)
    logging: LoggingConfig = Field(default=...)
    database: PostgresConfig = Field(default=...)
    mqtt: MqttConfig = Field(default=...)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    places_service_url: str = Field(default=...)

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
