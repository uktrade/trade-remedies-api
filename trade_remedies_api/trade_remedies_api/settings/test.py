import os
from .base import *  # noqa

LOGGING = ENVIRONMENT_LOGGING

if os.getenv("CIRCLECI"):
    RUN_ASYNC = False
