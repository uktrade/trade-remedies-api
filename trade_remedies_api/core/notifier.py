import os
import re

from notifications_python_client.notifications import NotificationsAPIClient

from .utils import convert_to_e164


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
    if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("prod") or os.environ.get(
        "DISABLE_NOTIFY_WHITELIST"
    ):
        return True
    whitelist = set(
        [
            "gov.uk",
            "trade.gov.uk",
            "digital.trade.gov.uk",
        ]
    )
    regex_whitelist = []
    _, domain = email.split("@")
    in_whitelist = domain in whitelist or email in whitelist
    if not in_whitelist:
        in_whitelist = any([re.match(pattern, email) for pattern in regex_whitelist])
    return in_whitelist
