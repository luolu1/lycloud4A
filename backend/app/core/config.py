"""应用配置：pydantic-settings 从环境变量 / .env 读取。"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # 应用
    APP_NAME: str = "lycloud4A"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/4a.db"

    # JWT / 会话
    SECRET_KEY: str = "dev-insecure-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # 密码策略
    PASSWORD_MIN_LENGTH: int = 12

    # 密码托管主密钥
    VAULT_MASTER_KEY: str = ""
    VAULT_KEY_FAIL_MODE: str = "fail"

    # 登录防爆破
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 调度
    ROTATION_SCHEDULER_ENABLED: bool = True
    ROTATION_CHECK_CRON: str = "0 2 * * *"

    # 引导管理员
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "Admin@12345"
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@corp.example.com"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
