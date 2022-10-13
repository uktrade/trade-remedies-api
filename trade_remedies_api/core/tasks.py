import logging

from email.utils import formataddr
from smtplib import SMTP_SSL, SMTPException
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from botocore.exceptions import ClientError
from celery import shared_task
from django.conf import settings
from notifications_python_client.errors import HTTPError

from audit import AUDIT_TYPE_NOTIFY
from audit.tasks import audit_log_task
from audit.utils import new_audit_record_to_dict
from core.notifier import get_client, send_mail as sync_send_mail
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
        if settings.RUN_ASYNC:
            check_email_delivered.apply_async(
                countdown=300, kwargs={"delivery_id": send_report["id"], "context": context}
            )
        else:
            check_email_delivered(delivery_id=send_report["id"], context=context)
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


@shared_task(bind=True)
def check_email_delivered(self, delivery_id, context):
    notify = get_client()
    email = notify.get_notification_by_id(delivery_id)
    delivery_status = email[
        "status"
    ]  # one of: sending / delivered / permanent-failure / temporary-failure / technical-failure
    if delivery_status in ["sending", "temporary-failure"]:
        # The email is still pending, let's schedule this function to run again soon
        if self.request.retries >= self.max_retries:
            # We've reached the max retries, let's log this and give up
            delivery_status = "unknown"
        else:
            # Let's schedule this task to happen again in the future,
            # maybe then it would have delivered
            self.retry(
                countdown=settings.AUDIT_EMAIL_RETRY_COUNTDOWN,
                max_retries=settings.AUDIT_EMAIL_MAX_RETRIES,
            )

    # Now let's send the audit email

    # Let's get the HTML of the email
    html_email = notify.post_template_preview(
        template_id=email["template"]["id"], personalisation=context
    )

    # Now let's send a new audit email with that HTML
    # todo - use the Amazon SES here with the endpoint provided by SRE:
    # https://ditdigitalteam.slack.com/archives/C1Q2EKZK3/p1664888037480459  #/PS-IGNORE
    # https://readme.trade.gov.uk/docs/howtos/service-email.html
    email_subject = f"{delivery_status.capitalize()} - {email['subject']}"
    email_html = html_email["html"]
    to_address = "chrispettinga@gmail.com"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = email_subject
    msg['From'] = formataddr((settings.AUDIT_EMAIL_FROM_NAME, settings.AUDIT_EMAIL_FROM_ADDRESS))
    msg['To'] = to_address
    part1 = MIMEText(email["body"], 'plain')
    part2 = MIMEText(email_html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    try:
        with SMTP_SSL(settings.AUDIT_EMAIL_SMTP_HOST, settings.AUDIT_EMAIL_SMTP_PORT) as server:
            server.login(settings.AUDIT_EMAIL_SMTP_USERNAME, settings.AUDIT_EMAIL_SMTP_PASSWORD)
            server.sendmail(settings.AUDIT_EMAIL_FROM_ADDRESS, to_address, msg.as_string())
            server.close()
            print("Email sent!")

    except SMTPException as e:
        print("Error: ", e)
    print("asd")
