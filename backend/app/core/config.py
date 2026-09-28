from decimal import Decimal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    APP_NAME:str="GaonOne API"; APP_ENV:str="development"; APP_DEBUG:bool=True; API_V1_PREFIX:str="/api/v1"; APP_VERSION:str="0.5.0"
    DATABASE_URL:str="postgresql+psycopg://gaonone:gaonone_dev_password@db:5432/gaonone"; REDIS_URL:str="redis://redis:6379/0"
    SECRET_KEY:str="change-this-in-production"; ACCESS_TOKEN_EXPIRE_MINUTES:int=60
    CORS_ORIGINS:str="http://localhost:3000,http://127.0.0.1:3000"; TRUSTED_HOSTS:str="localhost,127.0.0.1,testserver"; PUBLIC_BASE_URL:str="http://localhost:8000"; UPLOAD_DIR:str="data/uploads"; MAX_UPLOAD_MB:int=8
    AUTH_PROVIDER:str="local_otp"; DEV_OTP:str="123456"; OTP_TTL_SECONDS:int=300; OTP_RATE_WINDOW_SECONDS:int=900; OTP_MAX_REQUESTS_PER_WINDOW:int=5; OTP_MAX_VERIFY_ATTEMPTS:int=6; SMS_AUTH_ENABLED:bool=True; SMS_PROVIDER:str="none"
    MSG91_AUTH_KEY:str|None=Field(default=None,validation_alias=AliasChoices("MSG91_AUTH_KEY","MSG91_WIDGET_AUTH_KEY")); MSG91_TEMPLATE_ID:str|None=None; SMS_HTTP_TIMEOUT_SECONDS:float=8.0
    FIREBASE_PROJECT_ID:str|None=None; FIREBASE_SERVICE_ACCOUNT_JSON_B64:str|None=None
    RAZORPAY_KEY_ID:str|None=None; RAZORPAY_KEY_SECRET:str|None=None; RAZORPAY_WEBHOOK_SECRET:str|None=None
    FCM_PROJECT_ID:str|None=None; FCM_SERVICE_ACCOUNT_JSON_B64:str|None=None
    MAPS_PROVIDER:str="none"; MAPS_API_KEY:str|None=None
    # Template-only processing limits. They are provider-neutral defaults and
    # remain configurable before any external media-generation service exists.
    BANNER_REGEN_MAX_REQUESTS:int=3; BANNER_REGEN_WINDOW_SECONDS:int=86400
    BANNER_JOB_MAX_ATTEMPTS:int=3; BANNER_JOB_LEASE_SECONDS:int=120; BANNER_JOB_BATCH:int=25
    # Product-media B1 is disabled until private R2/S3 and the mandatory
    # automated scanner are provisioned. Local is development/test only.
    PRODUCT_MEDIA_ENABLED:bool=False; MEDIA_STORAGE_BACKEND:str="local"; MEDIA_SCAN_PROVIDER:str="disabled"; MEDIA_SCAN_REQUIRED:bool=True
    MEDIA_S3_ENDPOINT_URL:str|None=None; MEDIA_S3_REGION:str|None=None; MEDIA_S3_QUARANTINE_BUCKET:str|None=None; MEDIA_S3_PUBLIC_BUCKET:str|None=None; MEDIA_PUBLIC_BASE_URL:str|None=None
    MEDIA_S3_ACCESS_KEY_ID:str|None=None; MEDIA_S3_SECRET_ACCESS_KEY:str|None=None; MEDIA_SCAN_ENDPOINT_URL:str|None=None; MEDIA_SCAN_AUTH_TOKEN:str|None=None
    MEDIA_UPLOAD_MAX_BYTES:int=8*1024*1024; MEDIA_IMAGE_MAX_WIDTH:int=4096; MEDIA_IMAGE_MAX_HEIGHT:int=4096; MEDIA_IMAGE_MAX_PIXELS:int=16_000_000; MEDIA_IMAGE_MAX_PER_LISTING:int=8
    MEDIA_JOB_BATCH:int=25; MEDIA_JOB_MAX_ATTEMPTS:int=3; MEDIA_JOB_LEASE_SECONDS:int=120; MEDIA_RETENTION_SECONDS:int=30*24*60*60
    DEFAULT_DELIVERY_FEE:Decimal=Decimal("20.00")
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    @field_validator("APP_ENV")
    @classmethod
    def validate_environment(cls,value:str)->str:
        v=value.lower().strip()
        if v not in {"development","test","staging","production"}: raise ValueError("APP_ENV must be development, test, staging, or production")
        return v
    @field_validator("SMS_PROVIDER")
    @classmethod
    def validate_sms_provider(cls,value:str)->str:
        v=value.lower().strip()
        if v not in {"none","msg91"}: raise ValueError("SMS_PROVIDER must be none or msg91")
        return v
    @field_validator("AUTH_PROVIDER")
    @classmethod
    def validate_auth_provider(cls,value:str)->str:
        v=value.lower().strip()
        if v not in {"firebase","local_otp","msg91_widget"}: raise ValueError("AUTH_PROVIDER must be firebase, local_otp or msg91_widget")
        return v
    @field_validator("MEDIA_STORAGE_BACKEND")
    @classmethod
    def validate_media_storage_backend(cls,value:str)->str:
        v=value.lower().strip()
        if v not in {"local","s3"}: raise ValueError("MEDIA_STORAGE_BACKEND must be local or s3")
        return v
    @field_validator("MEDIA_SCAN_PROVIDER")
    @classmethod
    def validate_media_scan_provider(cls,value:str)->str:
        v=value.lower().strip()
        if v not in {"disabled","http"}: raise ValueError("MEDIA_SCAN_PROVIDER must be disabled or http")
        return v
    @model_validator(mode="after")
    def validate_production_safety(self)->"Settings":
        if self.APP_ENV in {"staging","production"}:
            if len(self.SECRET_KEY.encode())<32 or self.SECRET_KEY=="change-this-in-production": raise ValueError("SECRET_KEY must be at least 32 bytes and changed outside development")
            if self.APP_DEBUG: raise ValueError("APP_DEBUG must be false outside development/test")
            if self.DEV_OTP: raise ValueError("DEV_OTP must be empty outside development/test")
            if self.AUTH_PROVIDER=="firebase" and (not self.FIREBASE_PROJECT_ID or not self.FIREBASE_SERVICE_ACCOUNT_JSON_B64): raise ValueError("FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_JSON_B64 are required when AUTH_PROVIDER=firebase")
            if self.SMS_AUTH_ENABLED and self.SMS_PROVIDER!="msg91": raise ValueError("SMS_PROVIDER must be msg91 when SMS_AUTH_ENABLED=true outside development/test")
            if self.SMS_AUTH_ENABLED and (not self.MSG91_AUTH_KEY or not self.MSG91_TEMPLATE_ID): raise ValueError("MSG91_AUTH_KEY and MSG91_TEMPLATE_ID are required when SMS_AUTH_ENABLED=true and SMS_PROVIDER=msg91")
            if bool(self.FCM_PROJECT_ID)!=bool(self.FCM_SERVICE_ACCOUNT_JSON_B64): raise ValueError("FCM_PROJECT_ID and FCM_SERVICE_ACCOUNT_JSON_B64 must be configured together")
        if self.PRODUCT_MEDIA_ENABLED:
            if self.APP_ENV in {"staging","production"} and self.MEDIA_STORAGE_BACKEND!="s3": raise ValueError("PRODUCT_MEDIA_ENABLED requires MEDIA_STORAGE_BACKEND=s3 outside development/test")
            if self.MEDIA_STORAGE_BACKEND=="s3":
                required=(self.MEDIA_S3_ENDPOINT_URL,self.MEDIA_S3_REGION,self.MEDIA_S3_QUARANTINE_BUCKET,self.MEDIA_S3_PUBLIC_BUCKET,self.MEDIA_PUBLIC_BASE_URL,self.MEDIA_S3_ACCESS_KEY_ID,self.MEDIA_S3_SECRET_ACCESS_KEY)
                if not all(required): raise ValueError("S3 product-media storage requires endpoint, region, distinct buckets, public base URL and credentials")
                if self.MEDIA_S3_QUARANTINE_BUCKET==self.MEDIA_S3_PUBLIC_BUCKET: raise ValueError("Product-media quarantine and public buckets must differ")
            if not self.MEDIA_SCAN_REQUIRED or self.MEDIA_SCAN_PROVIDER!="http" or not self.MEDIA_SCAN_ENDPOINT_URL or not self.MEDIA_SCAN_AUTH_TOKEN: raise ValueError("Enabled product media requires a configured mandatory HTTP scanner")
        return self
    @field_validator("DEFAULT_DELIVERY_FEE")
    @classmethod
    def validate_delivery_fee(cls,value:Decimal)->Decimal:
        if value < 0: raise ValueError("DEFAULT_DELIVERY_FEE cannot be negative")
        return value
    @field_validator("BANNER_REGEN_MAX_REQUESTS", "BANNER_REGEN_WINDOW_SECONDS", "BANNER_JOB_MAX_ATTEMPTS", "BANNER_JOB_LEASE_SECONDS", "BANNER_JOB_BATCH")
    @classmethod
    def validate_banner_limits(cls,value:int)->int:
        if value <= 0: raise ValueError("Banner processing limits must be positive")
        return value
    @field_validator("MEDIA_UPLOAD_MAX_BYTES", "MEDIA_IMAGE_MAX_WIDTH", "MEDIA_IMAGE_MAX_HEIGHT", "MEDIA_IMAGE_MAX_PIXELS", "MEDIA_IMAGE_MAX_PER_LISTING", "MEDIA_JOB_BATCH", "MEDIA_JOB_MAX_ATTEMPTS", "MEDIA_JOB_LEASE_SECONDS", "MEDIA_RETENTION_SECONDS")
    @classmethod
    def validate_media_limits(cls,value:int)->int:
        if value <= 0: raise ValueError("Product-media limits must be positive")
        return value
    @property
    def cors_origins(self)->list[str]: return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]
    @property
    def trusted_hosts(self)->list[str]: return [x.strip() for x in self.TRUSTED_HOSTS.split(",") if x.strip()]
settings=Settings()
