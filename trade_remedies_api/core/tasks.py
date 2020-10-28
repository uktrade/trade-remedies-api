import logging

from celery import shared_task

from django.conf import settings

from notifications_python_client.errors import HTTPError

from audit import AUDIT_TYPE_NOTIFY
from audit.tasks import audit_log_task
from audit.utils import new_audit_record_to_dict
from core.notifier import send_mail as sync_send_mail
from core.utils import extract_error_from_api_exception


logger = logging.getLogger(__name__)

SEND_MAIL_MAX_RETRIES = 30
SEND_MAIL_COUNTDOWN = 60


def send_mail(email, context, template_id, reference=None, audit_kwargs=None):
    """
    Send an email asynchronously.

    :param str email: The recipients email address.
    :param dict context: The context / personalisation data with which the
        email template should be rendered.
    :param str template_id: The Nofify id of the template.
    :param str reference: An optional unique reference with which to identify
        the notification.
    :param dict audit_kwargs: An optional dictionary to be used when generating
        an audit log record. The valid keys and values correspond to the
        keyword arguments defined for `audit.utils.audit_log`.
    """
    if audit_kwargs:
        audit_kwargs.setdefault("audit_type", AUDIT_TYPE_NOTIFY)
        audit_kwargs = new_audit_record_to_dict(**audit_kwargs)

    if settings.RUN_ASYNC:
        send_mail_task.delay(email, context, template_id, reference, audit_kwargs)
    else:
        send_mail_task(email, context, template_id, reference, audit_kwargs)

    return {
        "email": email,
        "context": context,
        "template_id": template_id,
    }


@shared_task(bind=True)
def send_mail_task(self, email, context, template_id, reference=None, audit_kwargs=None):
    """
    Task to send email asynchronously and handle logging to the audit trail.
    """
    error_report = None
    audit_data = {}
    try:
        send_report = sync_send_mail(email, context, template_id, reference)
        logger.info(f"Send email: {send_report}")
    except HTTPError as err:
        error_report, error_status = extract_error_from_api_exception(err)
        if error_status in (500, 503):
            if self.request.retries >= self.max_retries:
                error_report["messages"].append("Failed")
            else:
                self.retry(
                    countdown=SEND_MAIL_COUNTDOWN, max_retries=SEND_MAIL_MAX_RETRIES, exc=err
                )

        if error_report:
            send_report = {
                "email": email,
                "values": context,
                "template_id": template_id,
                "error": error_report.get("messages")
                if isinstance(error_report, dict)
                else error_report,
            }
            logger.error("Notify request failed: %s", send_report)

    if audit_kwargs:
        audit_data = audit_kwargs.get("data", {})
        if not isinstance(audit_data, dict):
            audit_data = {"_data": audit_data}
        audit_data["send_report"] = send_report
    else:
        audit_kwargs = {}
        audit_data = send_report

    audit_kwargs["data"] = audit_data

    if settings.RUN_ASYNC:
        audit_log_task.delay(audit_kwargs)
    else:
        audit_log_task(audit_kwargs)

