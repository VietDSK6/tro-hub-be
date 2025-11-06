from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List

class Settings(BaseSettings):
    mongodb_uri: str = Field("mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db: str = Field("roommate", alias="MONGODB_DB")
    app_port: int = Field(8000, alias="APP_PORT")
    app_workers: int = Field(1, alias="APP_WORKERS")
    cors_origins: str = Field(
        default="http://localhost:8000,http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS"
    )

    @field_validator("cors_origins", mode="after")
    @classmethod
    def split_origins(cls, v: str) -> list[str]:
        return [origin.strip() for origin in v.split(",")]

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

settings = Settings()
