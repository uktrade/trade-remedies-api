from .base import *  # noqa


INSTALLED_APPS += [
    "api_test",
]

ROOT_URLCONF = "api_test.urls"
