import os
from psycogreen.gevent import patch_psycopg

from config.env import env

accesslog = os.environ.get("GUNICORN_ACCESSLOG", "-")
access_log_format = os.environ.get(
    "GUNICORN_ACCESS_LOG_FORMAT",
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %({X-Forwarded-For}i)s',
)
worker_class = "gevent"
worker_connections = env.GUNICORN_WORKER_CONNECTIONS
workers = env.GUNICORN_WORKERS
