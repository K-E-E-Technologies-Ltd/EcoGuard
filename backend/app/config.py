from functools import lru_cache
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'postgresql+psycopg://ecoguard:ecoguard@localhost:5432/ecoguard'
    allowed_origins: str = 'http://localhost:5173,http://localhost:8080'
    session_cookie: str = 'ecoguard_session'
    cookie_secure: bool = False
    session_hours: int = 12
    jobs_mode: Literal['celery', 'inline'] = 'celery'
    redis_url: str = 'redis://localhost:6379/0'
    storage_backend: Literal['local', 's3'] = 'local'
    media_dir: str = './var/media'
    max_upload_mb: int = 10
    s3_endpoint_url: str | None = None
    s3_bucket: str = 'ecoguard-private'
    s3_region: str = 'us-east-1'
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    model_path: str | None = None
    model_labels_path: str | None = None
    model_version: str = 'not-configured'
    confidence_threshold: float = .75
    sms_provider: Literal['disabled', 'webhook'] = 'disabled'
    sms_webhook_url: str | None = None
    sms_webhook_token: str | None = None
    demo_enabled: bool = False
    enable_api_docs: bool = True
    auto_create_tables: bool = False

    @property
    def origins(self):
        return [o.strip().rstrip('/') for o in self.allowed_origins.split(',') if o.strip()]

    @model_validator(mode='after')
    def production_guard(self):
        if self.app_env == 'production':
            if not self.cookie_secure or self.demo_enabled or self.auto_create_tables:
                raise ValueError('Production requires secure cookies, no demo seed and migrations (not auto_create_tables).')
            if not self.database_url.startswith('postgresql') or self.jobs_mode != 'celery':
                raise ValueError('Production requires PostgreSQL and Celery jobs.')
            if any(not o.startswith('https://') or '*' in o for o in self.origins):
                raise ValueError('Production requires explicit HTTPS origins.')
        return self

@lru_cache
def get_settings():
    return Settings()
