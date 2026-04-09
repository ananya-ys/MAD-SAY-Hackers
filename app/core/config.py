"""
app/core/config.py
Centralised settings via pydantic-settings.
All env-var reading goes through this class — never os.environ elsewhere.
"""
from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class ValidationLevelEnum(str, Enum):
    BASIC = "BASIC"
    ENDPOINT = "ENDPOINT"
    TESTS = "TESTS"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: AppEnv = AppEnv.development
    secret_key: str = "dev-secret-change-me-in-production-min-32"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./autofix_dev.db"

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_max_tokens: int = 4096
    llm_circuit_breaker_threshold: int = 3

    # Rate limits
    rate_limit_user_per_min: int = 10
    rate_limit_org_per_min: int = 100

    # Repair engine
    default_max_iterations: int = 5
    default_validation_level: ValidationLevelEnum = ValidationLevelEnum.BASIC
    sandbox_timeout_seconds: int = 30
    max_concurrent_sandboxes: int = 50
    stack_trace_max_bytes: int = 51200

    # Cache
    l1_cache_maxsize: int = 1000
    l1_cache_ttl_seconds: int = 3600

    # Confidence thresholds
    confidence_auto_use: float = 0.80
    confidence_warn: float = 0.60
    confidence_eviction: float = 0.20
    confidence_sre_alert: float = 0.50

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Observability
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str = ""

    # Wiki
    wiki_dir: str = "debug_wiki/errors"

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.production

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
