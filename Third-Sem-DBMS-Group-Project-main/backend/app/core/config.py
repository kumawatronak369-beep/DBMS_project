from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Private Network Monitoring System"
    cors_origins: str = "http://localhost:5173"
    enable_api_docs: bool = True

    # connection target without credentials
    database_url: str = "mysql+pymysql://localhost:3306/network_monitor"
    database_username: str = "root"
    database_password: str = ""

    jwt_secret: str = ""
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)
    bcrypt_rounds: int = Field(default=12, ge=10, le=15)

    @property
    def sqlalchemy_url(self) -> URL:
        return make_url(self.database_url).set(
            username=self.database_username,
            password=self.database_password,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
