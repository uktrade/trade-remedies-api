"""Django settings for trade_remedies_api project."""
import datetime
import os
import sys

import dj_database_url
import environ
import sentry_sdk
from flags import conditions
from flags.conditions import DuplicateCondition
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from config.feature_flags import is_user_part_of_group

# We use django-environ but do not read a `.env` file. Locally we feed
# docker-compose an environment from a local.env file in the project root.
# In our PaaS the service's environment is supplied from Vault.
#
# NB: Some settings acquired using `env()` deliberately *do not* have defaults
# as we want to get an `ImproperlyConfigured` exception to avoid a badly
# configured deployment.

root = environ.Path(__file__) - 4
env = environ.Env(
    DEBUG=(bool, False),
)


def strip_sensitive_data(event, hint):
    """Removing any potential passwords from being sent to Sentry as part of an exception/log"""
    event.get("request", {}).get("data", {}).pop("password", None)
    event.get("request", {}).get("headers", {}).pop("X-Origin-Environment")
    try:
        for each in event.get("exception", {}).get("values", {}):
            for sub_each in each.get("stacktrace", {}).get("frames"):
                if "password" in sub_each.get("vars", {}).get("serializer", ""):
                    sub_each["vars"]["serializer"] = "REDACTED"
    except Exception as exc:
        pass
    return event


SENTRY_ENVIRONMENT = env.str("SENTRY_ENVIRONMENT", default="local")
sentry_sdk.init(
    dsn=env("SENTRY_DSN", default=""),
    integrations=[DjangoIntegration(), CeleryIntegration()],
    environment=SENTRY_ENVIRONMENT,
    before_send=strip_sensitive_data,
)

SITE_ROOT = root()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Must be provided by the environment
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DEBUG", default=False)
DJANGO_ADMIN = env("DJANGO_ADMIN", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])

PASSWORD_RESET_TIMEOUT = 86400

# Application definition
DJANGO_APPS = [
    "django_extensions",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django_countries",
    "phonenumber_field",
    "storages",
]

DRF_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
]

LOCAL_APPS = [
    "audit",
    "cases",
    "contacts",
    "content",
    "core",
    "documents",
    "invitations",
    "notes",
    "organisations",
    "reports",
    "security",
    "tasks",
    "workflow",
]

THIRD_PARTY_APPS = [
    "axes",
    "feedback",
    "flags",
]

INSTALLED_APPS = DJANGO_APPS + DRF_APPS + LOCAL_APPS + THIRD_PARTY_APPS

MIDDLEWARE = [
    "config.middleware.ApiTokenSetter",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "config.middleware.SentryContextMiddleware",
]

if DJANGO_ADMIN:
    MIDDLEWARE = [
        "whitenoise.middleware.WhiteNoiseMiddleware",
    ] + MIDDLEWARE

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "..", "."),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    "config.backends.CustomAxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

WSGI_APPLICATION = "config.wsgi.application"

_VCAP_SERVICES = env.json("VCAP_SERVICES", default={})

if "postgres" in _VCAP_SERVICES:
    _database_uri = f"{_VCAP_SERVICES['postgres'][0]['credentials']['uri']}"
    DATABASES = {
        "default": {
            **dj_database_url.parse(
                _database_uri,
                engine="postgresql",
                conn_max_age=0,
            ),
            "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
            "OPTIONS": {
                "MAX_CONNS": env("DB_MAX_CONNS", default=10),
            },
        }
    }
else:
    default_database = env.db()
    DATABASES = {"default": default_database}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "core.password_validators.UpperAndLowerCase",
    },
    {
        "NAME": "core.password_validators.ContainsSpecialChar",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
STATIC_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "static"))
STATIC_URL = "/static/"

PUBLIC_ROOT_URL = env("PUBLIC_ROOT_URL", default="http://localhost:8001")
CASEWORKER_ROOT_URL = env("CASEWORKER_ROOT_URL", default="http://localhost:8002")

API_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DATETIME_FORMAT": API_DATETIME_FORMAT,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_RENDERER_CLASSES": [
        "config.renderers.DefaultAPIRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# Redis - Trade remedies uses different redis database numbers for the Django Cache
# for each service, and for Celery.
# API:        0
# Caseworker: 1
# Public:     2
# Celery:     3
REDIS_DATABASE_NUMBER = env("REDIS_DATABASE_NUMBER", default=0)
CELERY_DATABASE_NUMBER = env("CELERY_DATABASE_NUMBER", default=3)
if "redis" in _VCAP_SERVICES:
    uri = _VCAP_SERVICES["redis"][0]["credentials"]["uri"]
    REDIS_BASE_URL = uri
    CELERY_BROKER_URL = f"{uri}/{CELERY_DATABASE_NUMBER}?ssl_cert_reqs=required"
else:
    REDIS_BASE_URL = env("REDIS_BASE_URL", default="redis://redis:6379")
    uri = env("CELERY_BROKER_URL", default="redis://redis:6379")
    CELERY_BROKER_URL = f"{uri}/{CELERY_DATABASE_NUMBER}"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_BASE_URL}/{REDIS_DATABASE_NUMBER}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_WORKER_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s] [%(name)s] %(message)s"

# Axes
AXES_ENABLED = env("AXES_ENABLED", default=True)
# Axes sits behind a proxy
AXES_BEHIND_REVERSE_PROXY = True
# Number of login/2fa attempts
AXES_FAILURE_LIMIT = env("AXES_FAILURE_LIMIT", default=3)
# Number of hours for failed login lock cool-off
AXES_COOLOFF_TIME = datetime.timedelta(minutes=env("FAILED_LOGIN_COOLOFF", default=10))
# Tell Axes the username field is 'email'
AXES_USERNAME_FORM_FIELD = "email"
# Reset the lock count on successful login
AXES_RESET_ON_SUCCESS = True
# Look at these http headers for axes IP address
AXES_META_PRECEDENCE_ORDER = ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR")
# Use the user agent for Axes lockouts
AXES_USE_USER_AGENT = True
# Axes only check by user name (explicit disable)
AXES_ONLY_USER_FAILURES = False
# Use a combination of username and ip for axes
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True

# Opensearch host and port. OPENSEARCH HOST/PORT are offered as
# fallback when VCAP is not set by the environment
OPENSEARCH_HOST = env("OPENSEARCH_HOST", default=None)
OPENSEARCH_PORT = env("OPENSEARCH_PORT", default=None)
OPENSEARCH_URI = None
opensearch_vcap_config = _VCAP_SERVICES.get("opensearch")
if opensearch_vcap_config:
    OPENSEARCH_URI = opensearch_vcap_config[0]["credentials"]["uri"]
# OpenSearch index mapping  by doc_type
OPENSEARCH_INDEX = {
    "document": "main",
}

DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_DEFAULT_ACL = None

# Add the EU as a country
COUNTRIES_OVERRIDE = {
    "EU": "European Customs Union",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": env("ROOT_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": [
                "stdout",
            ],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.server": {
            "handlers": [
                "stdout",
            ],
            "level": env("DJANGO_SERVER_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": [
                "stdout",
            ],
            "level": env("DJANGO_REQUEST_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": [
                "stdout",
            ],
            "level": env("DJANGO_DB_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ------------------------------------------------------------------------------
# The TRS Zone - very specifically TRS settings.
# ------------------------------------------------------------------------------
API_PREFIX = "api/v1"
API_V2_PREFIX = "api/v2"
API_V2_ENABLED = env.bool("API_V2_ENABLED", default=False)
AUTH_TOKEN_MAX_AGE_MINUTES = env.int("AUTH_TOKEN_MAX_AGE_MINUTES", default=60)
if API_V2_ENABLED:
    AUTH_USER_MODEL = "authentication.User"
    ANON_USER_TOKEN = "change-me"
else:
    AUTH_USER_MODEL = "core.User"
# TODO-V2: Consolidate with REST_FRAMEWORK settings above
if API_V2_ENABLED:
    classes = [
        "authentication.ExpiringTokenAuthentication",
    ]
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = classes

ORGANISATION_NAME = env("ORGANISATION_NAME", default="Organisation name placeholder")
ORGANISATION_INITIALISM = env("ORGANISATION_INITIALISM", default="PLACEHOLDER")

# AWS
AWS_ACCESS_KEY_ID = AWS_S3_ACCESS_KEY_ID = env("S3_STORAGE_KEY", default=None)
AWS_SECRET_ACCESS_KEY = AWS_S3_SECRET_ACCESS_KEY = env("S3_STORAGE_SECRET", default=None)
AWS_STORAGE_BUCKET_NAME = env("S3_BUCKET_NAME", default=None)
AWS_S3_REGION_NAME = env("AWS_REGION", default="eu-west-2")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ENCRYPTION = True
# S3 client library to use
S3_CLIENT = "boto3"
# S3 Root directory name
S3_DOCUMENT_ROOT_DIRECTORY = "documents"
# Time before S3 download links expire
S3_DOWNLOAD_LINK_EXPIRY_SECONDS = env.int("S3_DOWNLOAD_LINK_EXPIRY_SECONDS", default=3600)
# Max upload size - 2GB
MAX_UPLOAD_SIZE = 2 * (1024 * 1024 * 1024)
# FILE DOWNLOAD CHUNK SIZE
STREAMING_CHUNK_SIZE = 8192
# Max life of password reset code in hours
PASSWORD_RESET_CODE_AGE_HOURS = env("PASSWORD_RESET_CODE_AGE", default=2)

# Two factor authentication is mandated
TWO_FACTOR_AUTH_REQUIRED = env.bool("TWO_FACTOR_AUTH_REQUIRED", default=True)
# Two factor authentication validity duration in days
TWO_FACTOR_AUTH_VALID_DAYS = env("TWO_FACTOR_AUTH_VALID_DAYS", default=14)
# Lockout time for two factor failures
TWO_FACTOR_LOCK_MINUTES = 5
# Two factor authentication code validity (SMS delivery type) in minutes
TWO_FACTOR_CODE_SMS_VALID_MINUTES = 10
# Two factor authentication code validity (Email delivery type) in minutes
TWO_FACTOR_CODE_EMAIL_VALID_MINUTES = 20
# Number of two factor authentication attempts allowed before locking
TWO_FACTOR_MAX_ATTEMPTS = 3
# How long do users have to wait before users can request another 2fa code (SECONDS)
TWO_FACTOR_RESEND_TIMEOUT_SECONDS = env("TWO_FACTOR_RESEND_TIMEOUT_SECONDS", default=20)

# Time to cache method
METHOD_CACHE_DURATION_MINUTES = 2

# Organisation user invite life time before expiry (in hours)
ORGANISATION_INVITE_DURATION_HOURS = 24 * 3
# Full application assessment days on receipt
DEADLINE_AFTER_ASSESSMENT_RECEIPT_DAYS = 40
# Email verify code regenerate after n minutes
EMAIL_VERIFY_CODE_REGENERATE_TIMEOUT = 15
# Id for the SOS organisation (fixed)
SECRETARY_OF_STATE_ORGANISATION_ID = "8850d091-e119-4ab5-9e21-ede5f0112bef"

# Companies House API
COMPANIES_HOUSE_API_KEY = env("COMPANIES_HOUSE_API_KEY", default=None)

# GOV Notify
GOV_NOTIFY_API_KEY = env.str("GOV_NOTIFY_API_KEY", default=None)
GOV_NOTIFY_TESTING_KEY = env.str("GOV_NOTIFY_TESTING_KEY", default=None)
DISABLE_NOTIFY_WHITELIST = env.bool("DISABLE_NOTIFY_WHITELIST", default=False)

# ------------------------------------------------------------------------------
# The Crud Zone - things likely to be refactored out.
# ------------------------------------------------------------------------------
API_DATE_FORMAT = "%Y-%m-%d"
FRIENDLY_DATE_FORMAT = "%-d %B %Y"
API_CACHE_TIMEOUT = 3  # Cache timeout in minutes
DEFAULT_QUERYSET_PAGE_SIZE = 20
TRUSTED_USER_EMAIL = env("HEALTH_CHECK_USER_EMAIL")
RUN_ASYNC = env.bool("RUN_ASYNC", default=True)
# The ENVIRONMENT_KEY settings are superfluous (they sought to link Public/CW
# portal calls to a "security group"), because we plan to use django-guardian
# for object level permissions. In the new `authentication` package we will
# only expect ANON_USER_TOKEN in the request, meaning only bearers of THAT
# token will be allowed to use any unauthenticated views (e.g. `/auth/login`).
CASE_WORKER_ENVIRONMENT_KEY = env("CASE_WORKER_ENVIRONMENT_KEY")
PUBLIC_ENVIRONMENT_KEY = env("PUBLIC_ENVIRONMENT_KEY")
# Allowed origins
ALLOWED_ORIGINS = (CASE_WORKER_ENVIRONMENT_KEY, PUBLIC_ENVIRONMENT_KEY)
# Days of registration window for a case
CASE_REGISTRATION_DURATION = 15
# Geckoboard API
# So much wrong with this - and operational assurance is taken care of by SRE
# capabilities like ELK and Grafana (and visible to devs in prod, which this
# is not). Bin it.
GECKOBOARD_API_KEY = env("GECKOBOARD_API_KEY", default=None)
GECKOBOARD_ENV = env("GECKOBOARD_ENV", default="dev")

# Variable so we know if we're running in testing mode or not, this is True in the test.py settings
TESTING = False

# ------------------- FEATURE FLAGS -------------------
try:
    conditions.register("PART_OF_GROUP", fn=is_user_part_of_group)
except DuplicateCondition:
    # During deployment, this can sometimes be ran twice causing a DuplicateCondition error
    pass
FEATURE_FLAG_PREFIX = "FEATURE_FLAG"
FLAGS = {
    f"{FEATURE_FLAG_PREFIX}_UAT_TEST": [
        {"condition": "PART_OF_GROUP", "value": True, "required": True},
    ],
    f"{FEATURE_FLAG_PREFIX}_INVITE_JOURNEY": [
        {"condition": "PART_OF_GROUP", "value": True, "required": True},
    ],
}

# ------------------- GOV.NOTIFY AUDIT COPY EMAILS -------------------
AUDIT_EMAIL_ENABLED = env.bool("AUDIT_EMAIL_ENABLED", False)
AUDIT_EMAIL_GIVE_UP_SECONDS = env.int("AUDIT_EMAIL_GIVE_UP_SECONDS", default=259200)
AUDIT_EMAIL_RETRY_COUNTDOWN = env.int("AUDIT_EMAIL_RETRY_COUNTDOWN", default=1200)
AUDIT_EMAIL_FROM_ADDRESS = env.str(
    "AUDIT_EMAIL_FROM_ADDRESS", default="notify.copy@traderemedies.gov.uk"  # /PS-IGNORE
)
AUDIT_EMAIL_FROM_NAME = env.str("AUDIT_EMAIL_FROM_NAME", default="TRS Notify Copy")
AUDIT_EMAIL_IAM_USER = env.str("AUDIT_EMAIL_IAM_USER")
AUDIT_EMAIL_SMTP_USERNAME = env.str("AUDIT_EMAIL_SMTP_USERNAME")
AUDIT_EMAIL_SMTP_PASSWORD = env.str("AUDIT_EMAIL_SMTP_PASSWORD")
AUDIT_EMAIL_SMTP_HOST = env.str(
    "AUDIT_EMAIL_SMTP_HOST", default=f"email-smtp.{AWS_S3_REGION_NAME}.amazonaws.com"
)
AUDIT_EMAIL_SMTP_PORT = env.int("AUDIT_EMAIL_SMTP_PORT", default=587)
AUDIT_EMAIL_TO_ADDRESS = env.str("AUDIT_EMAIL_TO_ADDRESS")

# ------------------- API RATE LIMITING -------------------
API_RATELIMIT_ENABLED = env.bool("API_RATELIMIT_ENABLED", default=True)
if API_RATELIMIT_ENABLED:
    MIDDLEWARE = MIDDLEWARE + [
        "django_ratelimit.middleware.RatelimitMiddleware",
    ]

API_RATELIMIT_RATE = env.str("API_RATELIMIT_RATE", default="50/m")
RATELIMIT_VIEW = "config.ratelimit.ratelimited_error"

# ------------------- API PROFILING -------------------
PYINSTRUMENT_PROFILE_DIR = "profiles"
PROFILING_ENABLED = env.bool("PROFILING_ENABLED", default=False)
if PROFILING_ENABLED:
    MIDDLEWARE = [
        "config.middleware.StatsMiddleware",
    ] + MIDDLEWARE
    MIDDLEWARE = MIDDLEWARE + [
        "pyinstrument.middleware.ProfilerMiddleware",
    ]
