# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    All app-wide settings live here.
    Values are auto-loaded from the .env file at the project root.
    """
    
    # Database - MUST be in .env
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    
    # Auth - MUST be in .env (change in production)
    SECRET_KEY: str = Field(..., description="Secret for JWT (min 32 chars)")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=14440, description="Token expiry")
    
    # Cloudinary - Add these for image upload
    CLOUDINARY_CLOUD_NAME: str = Field(..., description="Cloudinary cloud name")
    CLOUDINARY_API_KEY: str = Field(..., description="Cloudinary API key")
    CLOUDINARY_API_SECRET: str = Field(..., description="Cloudinary API secret")
    CLOUDINARY_FOLDER: str = Field(default="marketplace", description="Upload folder")

    # Notifications - Add these for notification retention
    DELETE_READ_NOTIFICATIONS_IN_DAYS: int = Field(..., description="Days to keep read notifications")
    DELETE_UNREAD_NOTIFICATIONS_IN_DAYS: int = Field(..., description="Days to keep unread notifications")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

# Single shared instance
settings = Settings()