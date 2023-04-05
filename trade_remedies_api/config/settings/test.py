from rest_framework.permissions import IsAuthenticated

from core.services.base import GroupPermission
from .base import *  # noqa

LOGGING = ENVIRONMENT_LOGGING

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
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = ()

    def return_true():
        return True
    IsAuthenticated = return_true
    GroupPermission = return_true

TESTING = True
