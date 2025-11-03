from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    mongodb_uri: str = Field("mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db: str = Field("roommate", alias="MONGODB_DB")
    app_port: int = Field(8000, alias="APP_PORT")
    app_workers: int = Field(1, alias="APP_WORKERS")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

settings = Settings()
