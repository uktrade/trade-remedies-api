from .base import *  # noqa
from .hardening import *  # noqa

LOGGING = ENVIRONMENT_LOGGING

INSTALLED_APPS += [
    "django_audit_log_middleware",
]

MIDDLEWARE += [
    "django_audit_log_middleware.AuditLogMiddleware",
]
