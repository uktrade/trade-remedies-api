import os
from .base import *


DATABASES = {
    "default": {
        "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"MAX_CONNS": int(os.environ.get("DB_MAX_CONNS", "10")),},
    },
}


# S3_CLIENT = 'minio'
