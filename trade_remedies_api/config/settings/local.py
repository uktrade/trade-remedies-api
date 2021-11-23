from .base import *  # noqa


INSTALLED_APPS += [  # F405
    "api_test",
]

ROOT_URLCONF = "api_test.urls"
