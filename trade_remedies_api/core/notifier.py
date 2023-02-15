import os
import re
import requests
import redis
import concurrent.futures
from celery.result import AsyncResult
from django.db import connection
from django.conf import settings
from notifications_python_client.notifications import NotificationsAPIClient

from .utils import convert_to_e164
from .decorators import measure_time


def get_client():
    """
    Return a Notification client
    """
    return NotificationsAPIClient(os.environ["GOV_NOTIFY_API_KEY"])


def send_mail(email, context, template_id, reference=None):
    if is_whitelisted(email):
        client = get_client()
        send_report = client.send_email_notification(
            email_address=email,
            template_id=template_id,
            personalisation=get_context(context),
            reference=reference,
        )
    else:
        send_report = {
            "content": {},
            "whitelist": False,
        }
    send_report["to_email"] = email
    send_report["template_id"] = template_id
    return send_report


def notify_footer(email=None):
    """Build notify footer with specified email.

    :param (str) email: contact email for footer.
    :returns (str): NOTIFY_BLOCK_FOOTER system parameter value
      with email appended, if any.
    """

    footer = "Investigations Team\r\nTrade Remedies Authority"
    if email:
        return "\n".join([footer, f"Contact: {email}"])
    return footer


def notify_contact_email(case_number=None):
    """Build notify email address.

    If a case is specified build contact email with it.

    :param (str) case_number: e.g. 'TD0001'
    :returns (str): A case contact email if case number specified, otherwise
      value of TRADE_REMEDIES_EMAIL system parameter.
    """
    if case_number:
        return f"{case_number}@traderemedies.gov.uk"  # /PS-IGNORE
    return "contact@traderemedies.gov.uk"  # /PS-IGNORE


def get_context(extra_context=None):
    from core.models import SystemParameter

    extra_context = extra_context or {}
    email = notify_contact_email(extra_context.get("case_number"))
    footer = notify_footer(email)
    context = {
        "footer": footer,
        "email": email,
        "guidance_url": SystemParameter.get("LINK_HELP_BOX_GUIDANCE"),
    }
    context.update(extra_context)
    return context


def get_template(template_id):
    client = get_client()
    return client.get_template(template_id)


def get_preview(template_id, values):
    client = get_client()
    return client.post_template_preview(
        template_id=template_id, personalisation=get_context(values)
    )


def send_sms(number, context, template_id, country=None, reference=None):
    client = get_client()
    return client.send_sms_notification(
        phone_number=convert_to_e164(number, country=country),
        template_id=template_id,
        personalisation=context,
        reference=reference,
    )


def is_whitelisted(email):
    """
    Temporary measure to restrict notify emails to certain domains.
    disabled on production.
    """
    if (
        os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("prod")
        or settings.DISABLE_NOTIFY_WHITELIST
    ):
        return True

    whitelist = {"gov.uk", "trade.gov.uk", "digital.trade.gov.uk"}
    regex_whitelist = []
    _, domain = email.split("@")
    in_whitelist = domain in whitelist or email in whitelist
    if not in_whitelist:
        in_whitelist = any([re.match(pattern, email) for pattern in regex_whitelist])
    return in_whitelist


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
    This function pings PostgreSQL.

    :return: None
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


@measure_time
def ping_redis():
    """
    This function pings Redis.

    :return: None
    """
    redis_conn = redis.Redis(
        host=settings.REDIS_BASE_URL, port=6379, db=settings.REDIS_DATABASE_NUMBER
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


def _pingdom_custom_status_html_wrapper(status: str, response_time: float) -> str:
    """
    response data format:
    https://documentation.solarwinds.com/en/success_center/pingdom/content/topics/http-custom-check.htm?cshid=pd-rd_115000431709-http-custom-check
    """
    html = """
    <br/>
        <pingdom_http_custom_check>
            <status>
                <strong>{}</strong>
            </status>
            <response_time>
                <strong>{}</strong>
            </response_time>
        </pingdom_http_custom_check>
    <br/>
    <br/>
    """.format(
        status, response_time
    )
    return html


def application_service_health():
    """
    This function checks the health of the application by pinging various
    services (celery, postgres, redis, opensearch) and returns the average response time and status.

    :return: a tuple containing the status (OK or an error message) and the average response time (in seconds)
    """
    services = [ping_celery, ping_postgres, ping_redis, ping_opensearch]
    response_times = []
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(service) for service in services]
            for future in concurrent.futures.as_completed(futures):
                _, response_time = future.result()
                response_times.append(response_time)
    except Exception as err:
        return _pingdom_custom_status_html_wrapper(f"Error: {err}", 0)

    avg_response_time = sum(response_times) / len(response_times)
    return _pingdom_custom_status_html_wrapper("OK", avg_response_time)
