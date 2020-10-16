import os
from .base import *  # noqa: F403

RUN_ASYNC = False

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",}}
