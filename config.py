import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, env="DEEPSEEK_API_KEY")
    payment_provider_token: Optional[str] = Field(None, env="PAYMENT_PROVIDER_TOKEN")
    admin_user_id: Optional[int] = Field(None, env="ADMIN_USER_ID")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    webhook_secret: Optional[str] = Field(None, env="WEBHOOK_SECRET")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    environment: str = Field("development", env="ENVIRONMENT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # ignore unexpected variables

settings = Settings()