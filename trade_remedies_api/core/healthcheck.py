import redis
import requests
import concurrent.futures
import xml.etree.ElementTree as ET
from celery.result import AsyncResult
from django.db import connection
from django.conf import settings

from .decorators import measure_time


@measure_time
def ping_celery():
    """
    This function pings Celery.
    :return: the task
    """

    task = AsyncResult("dummy-task-id")
    return task


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
    response = requests.get(settings.OPENSEARCH_URI, timeout=30)
    return response


def _pingdom_custom_status_html_wrapper(status_str: str, response_time_value: float) -> str:
    """
    response data format:
    https://documentation.solarwinds.com/en/success_center/pingdom/content/topics/http-custom-check.htm?cshid=pd-rd_115000431709-http-custom-check
    """
    root = ET.Element("root")
    pingdom_http_custom_check = ET.SubElement(root, "pingdom_http_custom_check")
    status = ET.SubElement(pingdom_http_custom_check, "status")
    strong = ET.SubElement(status, "strong")
    strong.text = str(status_str)
    response_time = ET.SubElement(pingdom_http_custom_check, "response_time")
    strong = ET.SubElement(response_time, "strong")
    strong.text = str(response_time_value)
    xml = ET.tostring(root, encoding="unicode", method="xml")
    return xml


def application_service_health():
    """
    This function checks the health of the application by pinging various
    services (celery, postgres, redis, opensearch) and returns the average response time and status.

    :return: a tuple containing the status (OK or an error message) and the average response time (in seconds)
    """
    services = [ping_celery, ping_postgres, ping_redis, ping_opensearch]
    response_times = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(service) for service in services]
        for future in concurrent.futures.as_completed(futures):
            try:
                _, response_time = future.result()
                response_times.append(response_time)
            except Exception as err:
                return _pingdom_custom_status_html_wrapper(f"Error: {str(err)}", 0)

    avg_response_time = sum(response_times) / len(response_times)
    return _pingdom_custom_status_html_wrapper("OK", avg_response_time)