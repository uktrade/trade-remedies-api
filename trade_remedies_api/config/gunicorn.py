import os
from psycogreen.gevent import patch_psycopg

from trade_remedies_api.config.env import env

accesslog = os.environ.get("GUNICORN_ACCESSLOG", "-")
access_log_format = os.environ.get(
    "GUNICORN_ACCESS_LOG_FORMAT",
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %({X-Forwarded-For}i)s',
)
worker_class = "gevent"
worker_connections = env.GUNICORN_WORKER_CONNECTIONS
workers = env.GUNICORN_WORKERS


def post_fork(server, worker):
    """
    Called just after a worker has been forked.

    Enables async processing in Psycopg2 if GUNICORN_ENABLE_ASYNC_PSYCOPG2 is set.
    """
    patch_psycopg()
    worker.log.info("Enabled async Psycopg2")
