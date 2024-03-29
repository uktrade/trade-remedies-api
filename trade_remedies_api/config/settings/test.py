from v2_api_client.shared.logging import PRODUCTION_LOGGING

from .base import *  # noqa

LOGGING = PRODUCTION_LOGGING

# This module is also referenced when executing tests in CircleCI, the below
# settings cater for that (expedites test execution). However in the PaaS `test`
# env, we don't want them as they break document upload.
if os.getenv("CIRCLECI"):
    RUN_ASYNC = False
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

TESTING = True
