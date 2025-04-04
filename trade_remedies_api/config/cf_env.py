import dj_database_url
import environ

from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings


env_obj = environ.Env()


class VCAPServices(BaseModel):
    model_config = ConfigDict(extra="ignore")

    postgres: list[dict[str, Any]] = Field(alias="postgres", default=[])
    redis: list[dict[str, Any]] = Field(alias="redis", default=[])
    aws_s3_bucket: list[dict[str, Any]] = Field(alias="aws-s3-bucket", default=[])
    opensearch: list[dict[str, Any]] = Field(alias="opensearch", default=[])


class CloudFoundrySettings(BaseSettings):
    ALLOWED_HOSTS: str = ""
    API_PORT: str = "8000"
    API_RATELIMIT_ENABLED: bool = False
    AUDIT_EMAIL_ENABLED: bool = False
    AUDIT_EMAIL_FROM_ADDRESS: str = "notify.copy@traderemedies.gov.uk"
    AUDIT_EMAIL_FROM_NAME: str = "TRS Notify Copy"
    AUDIT_EMAIL_IAM_USER: Optional[str] = None
    AUDIT_EMAIL_SMTP_PASSWORD: Optional[str] = None
    AUDIT_EMAIL_SMTP_USERNAME: Optional[str] = None
    AUDIT_EMAIL_TO_ADDRESS: Optional[str] = None
    AUDIT_EMAIL_SMTP_HOST: Optional[str] = None
    AV_SERVICE_PASSWORD: Optional[str] = None
    AV_SERVICE_URL: Optional[str] = None
    AV_SERVICE_USERNAME: Optional[str] = None
    AWS_REGION: str = "eu-west-2"
    CASEWORKER_ROOT_URL: str = "http://localhost:8002"
    CASE_WORKER_ENVIRONMENT_KEY: str
    CELERY_LOGLEVEL: str = "INFO"
    CELERY_BROKER_URL: str = "redis://redis:6379"
    COMPANIES_HOUSE_API_KEY: Optional[str] = None
    DB_MAX_CONNS: int = 10
    DEBUG: bool = False
    DISABLE_COLLECTSTATIC: int = 1
    DISABLE_NOTIFY_WHITELIST: bool = False
    DJANGO_ADMIN: bool = False
    DJANGO_DB_LOG_LEVEL: str = "INFO"
    DJANGO_LOG_LEVEL: str = "INFO"
    DJANGO_REQUEST_LOG_LEVEL: str = "INFO"
    DJANGO_SECRET_KEY: str
    DJANGO_SERVER_LOG_LEVEL: str = "INFO"
    DJANGO_SETTINGS_MODULE: str
    FAILED_LOGIN_COOLOFF: int = 10
    GECKOBOARD_API_KEY: Optional[str] = None
    GOV_NOTIFY_API_KEY: Optional[str] = None
    GUNICORN_WORKERS: int = 1
    GUNICORN_WORKER_CONNECTIONS: int = 10
    HEALTH_CHECK_USER_EMAIL: str = "health_check@localhost"
    HEALTH_CHECK_USER_TOKEN: str = "health_check_token"
    MASTER_ADMIN_EMAIL: str = "admin@localhost"
    MASTER_ADMIN_PASSWORD: str = "password"
    ORGANISATION_INITIALISM: str = "PLACEHOLDER"
    ORGANISATION_NAME: str = "Organisation name placeholder"
    PUBLIC_ENVIRONMENT_KEY: str
    PUBLIC_ROOT_URL: str = "http://localhost:8001"
    REDIS_DATABASE_NUMBER: int = 0
    RUN_ASYNC: bool = True
    S3_BUCKET_NAME: Optional[str] = None
    AWS_STORAGE_BUCKET_NAME: Optional[str] = None
    S3_DOWNLOAD_LINK_EXPIRY_SECONDS: int = 3600
    S3_STORAGE_KEY: Optional[str] = None
    S3_STORAGE_SECRET: Optional[str] = None
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "local"
    SENTRY_ENABLE_TRACING: bool = False
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    CELERY_DATABASE_NUMBER: int = 3
    CELERY_TASK_ALWAYS_EAGER: bool = False
    AXES_ENABLED: bool = True
    AXES_FAILURE_LIMIT: int = 3
    OPENSEARCH_HOST: Optional[str] = None
    OPENSEARCH_PORT: Optional[int] = 9200
    ROOT_LOG_LEVEL: str = "INFO"
    API_V2_ENABLED: bool = False
    AUTH_TOKEN_MAX_AGE_MINUTES: int = 60
    PASSWORD_RESET_CODE_AGE: int = 2
    TWO_FACTOR_AUTH_REQUIRED: bool = True
    TWO_FACTOR_AUTH_VALID_DAYS: int = 14
    TWO_FACTOR_RESEND_TIMEOUT_SECONDS: int = 20
    GOV_NOTIFY_TESTING_KEY: Optional[str] = None
    GECKOBOARD_ENV: str = "dev"
    AUDIT_EMAIL_GIVE_UP_SECONDS: int = 259200
    AUDIT_EMAIL_RETRY_COUNTDOWN: int = 1200
    AUDIT_EMAIL_SMTP_PORT: int = 587
    API_RATELIMIT_RATE: str = "500/m"
    PROFILING_ENABLED: bool = False
    VCAP_SERVICES: Optional[VCAPServices] = {}
    REDIS_BASE_URL: str = "redis://redis:6379"

    def get_allowed_hosts(self) -> list[str]:
        return self.ALLOWED_HOSTS.split(",") if self.ALLOWED_HOSTS else ["localhost"]

    def get_database_config(self) -> dict:
        if "postgresql" in self.VCAP_SERVICES:
            _database_uri = f"{self.VCAP_SERVICES['postgres'][0]['credentials']['uri']}"
            return {
                "default": {
                    **dj_database_url.parse(
                        _database_uri,
                        engine="postgresql",
                        conn_max_age=0,
                    ),
                    "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
                    "OPTIONS": {
                        "MAX_CONNS": self.DB_MAX_CONNS,
                    },
                }
            }
        return {"default": env_obj.db()}

    def get_s3_bucket_config(self) -> dict:
        """Return s3 bucket config that matches keys used in CF"""

        return {
            "aws_region": self.AWS_REGION,
            "bucket_name": self.S3_BUCKET_NAME or self.AWS_STORAGE_BUCKET_NAME or "",
        }

    def get_redis_url(self) -> str:
        if "redis" in self.VCAP_SERVICES:
            return self.VCAP_SERVICES["redis"][0]["credentials"]["uri"]
        return self.REDIS_BASE_URL
