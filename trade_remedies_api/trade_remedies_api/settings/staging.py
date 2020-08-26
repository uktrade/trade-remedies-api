import os
from .base import *
import dj_database_url


DATABASES = {
    "default": {
        **dj_database_url.config(),
        "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"MAX_CONNS": int(os.environ.get("DB_MAX_CONNS", "10")),},
    },
}
