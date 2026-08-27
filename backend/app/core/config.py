from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GaonOne API"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    APP_VERSION: str = "0.4.0"

    DATABASE_URL: str = "postgresql+psycopg://gaonone:gaonone_dev_password@db:5432/gaonone"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_MB: int = 8

    DEV_OTP: str = "123456"
    OTP_TTL_SECONDS: int = 300
    OTP_RATE_WINDOW_SECONDS: int = 900
    OTP_MAX_REQUESTS_PER_WINDOW: int = 5
    OTP_MAX_VERIFY_ATTEMPTS: int = 6
    SMS_PROVIDER: str = "none"
    MSG91_AUTH_KEY: str | None = None
    MSG91_TEMPLATE_ID: str | None = None
    SMS_HTTP_TIMEOUT_SECONDS: float = 8.0

    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    FCM_PROJECT_ID: str | None = None
    MAPS_PROVIDER: str = "none"
    MAPS_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("APP_ENV")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production")
        return normalized

    @field_validator("SMS_PROVIDER")
    @classmethod
    def validate_sms_provider(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"none", "msg91"}:
            raise ValueError("SMS_PROVIDER must be none or msg91")
        return normalized

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.APP_ENV in {"staging", "production"}:
            if len(self.SECRET_KEY.encode("utf-8")) < 32 or self.SECRET_KEY == "change-this-in-production":
                raise ValueError("SECRET_KEY must be at least 32 bytes and changed outside development")
            if self.APP_DEBUG:
                raise ValueError("APP_DEBUG must be false outside development/test")
            if self.SMS_PROVIDER == "msg91" and (not self.MSG91_AUTH_KEY or not self.MSG91_TEMPLATE_ID):
                raise ValueError("MSG91_AUTH_KEY and MSG91_TEMPLATE_ID are required when SMS_PROVIDER=msg91")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [item.strip() for item in self.TRUSTED_HOSTS.split(",") if item.strip()]


settings = Settings()
