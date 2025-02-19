import logging
import xml.etree.ElementTree as ET

import redis
import traceback
import requests
import sentry_sdk
from config.celery import app
from django.conf import settings
from django.db import connection

from .decorators import measure_time
from .exceptions import HealthCheckException

logger = logging.getLogger(__name__)


@measure_time
def ping_celery():
    """
    This function pings Celery.
    :return: the task
    """
    i = app.control.inspect()
    availability = i.ping()
    if not availability:
        raise HealthCheckException("Celery not working")
    return availability


@measure_time
def ping_postgres():
    """
    This function pings Database(PostgreSQL).

    :return: None
    """
    connection.ensure_connection()


@measure_time
def ping_redis():
    """
    This function pings Redis.

    :return: None
    """
    redis_conn = redis.StrictRedis.from_url(
        settings.REDIS_BASE_URL, db=settings.REDIS_DATABASE_NUMBER
    )
    redis_conn.ping()


@measure_time
def ping_opensearch():
    """
    This function pings OpenSearch.

    :return: the response from OpenSearch
    """
    print("requesting http")
    requests.get("http://example.com", timeout=20)

    print("requesting https")
    try:
        requests.get("https://example.com", timeout=20)
    except Exception as err:
        print(err)
        print("we're in the example exception")
        traceback.print_tb(err.__traceback__)

    response = requests.get(settings.OPENSEARCH_URI, timeout=20)
    return response


def _pingdom_custom_status_html_wrapper(status_str: str, response_time_value: float) -> str:
    """
    response data format:
    https://documentation.solarwinds.com/en/success_center/pingdom/content/topics/http-custom-check.htm?cshid=pd-rd_115000431709-http-custom-check
    """
    root = ET.Element("pingdom_http_custom_check")
    # status = ET.SubElement(root, "status")
    # status.text = str(status_str)
    # response_time = ET.SubElement(root, "response_time")
    # response_time.text = str(response_time_value)
    xml = ET.tostring(root, encoding="unicode", method="xml")
    return xml


def application_service_health():
    """
    This function checks the health of the application by pinging various
    services (celery, postgres, redis, opensearch) and returns the average response time and status.

    :return: a tuple containing the status (OK or an error message) and the average response time (in seconds)
    """
    services = [
        # ping_celery,
        ping_postgres,
        ping_redis,
        ping_opensearch
    ]
    response_times = []

    # for service_check in services:
    try:
        ping_opensearch()
        # response_times.append(response_time)
    except Exception as err:
        print(err.with_traceback(err.__traceback__))
        print("send to sentry")
        return _pingdom_custom_status_html_wrapper(f"Error: some error", 0)

    return _pingdom_custom_status_html_wrapper("OK", 0)
