"""
Application configuration.
Loads settings from .env file using pydantic-settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    All app-wide settings live here.
    Values are auto-loaded from the .env file at the project root.
    """

    DATABASE_URL: str = "sqlite:///./app_v2.db"
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"


# Single shared instance — import this wherever you need config
settings = Settings()
