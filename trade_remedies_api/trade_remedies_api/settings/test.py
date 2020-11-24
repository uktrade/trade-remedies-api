import os
from .base import *

RUN_ASYNC = False

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",}}
