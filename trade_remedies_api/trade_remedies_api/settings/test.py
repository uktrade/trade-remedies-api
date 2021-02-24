import os
from .base import *  # noqa

LOGGING = ENVIRONMENT_LOGGING

if os.getenv("CIRCLECI"):
    RUN_ASYNC = False
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", }}
