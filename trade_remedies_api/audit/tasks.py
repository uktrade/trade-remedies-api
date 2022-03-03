import logging

from celery import shared_task
from django.db.utils import OperationalError, IntegrityError
from core.notifier import get_client
from audit import AUDIT_TYPE_DELIVERED
from audit.models import Audit
from notifications_python_client.errors import HTTPError

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def audit_log_task(self, audit_dict):
    """
    Celery task to asynchronously create an audit record.
    """
    audit = Audit(**audit_dict)
    try:
        audit.save()
    except (OperationalError, IntegrityError) as err:
        self.retry(countdown=60, max_retries=15, exc=err)


@shared_task
def check_notify_send_status():
    """
    Task to evaluate the send status of notify emails, and update the status
    when available from notify service

    Query from below made clearer:

    SELECT
        parent.id,
        parent.data,
        parent.created_by_id,
        parent.case_id,
        parent.model_id,
        parent.content_type_id
    FROM
        audit_audit parent
    LEFT JOIN
        audit_audit child
    ON
        parent.id=child.parent_id
    WHERE
        parent.type = 'NOTIFY'
    AND
        parent.parent_id is null
    AND (
            child.id is null
        OR
            child.data->>'status' NOT IN (
                'delivered',
                'unknown',
                'permanent-failure',
                'temporary-failure'
            )
        )
    ORDER BY
        parent.created_at
    DESC;
    """
    SQL = """
    SELECT a.id, a.data, a.created_by_id, a.case_id, a.model_id, a.content_type_id
    FROM audit_audit a LEFT JOIN audit_audit b
    ON a.id=b.parent_id
    WHERE a.type = 'NOTIFY'
    AND a.parent_id is null
    AND (
        b.id is null OR b.data->>'status'
        NOT IN ('delivered', 'unknown', 'permanent-failure', 'temporary-failure')
    )
    ORDER BY a.created_at DESC
    """
    audits = Audit.objects.raw(SQL)
    logger.debug(f"Total pending audits: {len(audits)}")
    notify = get_client()
    for audit in audits:
        delivery_id = audit.data.get("send_report", {}).get("id")
        if delivery_id:
            try:
                status = notify.get_notification_by_id(delivery_id)
            except Exception as e:
                if isinstance(e, HTTPError):
                    # The GOV.NOTIFY service cannot find a message with this delivery_id. Let's mark it as
                    # 'lost' so the service is not constantly bombarded with requests from this scheduled task.

                    # Updating the potential child object(s) to mark the status as 'unknown' so the parent is
                    # not looped over again and again in the future.
                    for child_audit in Audit.objects.filter(parent=audit):
                        # We know that we're not overwriting any delivered...etc. values in the 'status' key because if
                        # they were, they wouldn't have shown up in the big audit query
                        child_audit.data['status'] = 'unknown'
                        child_audit.save()
                status = {
                    "status": "unknown",
                    "sent_at": None,
                    "completed_at": None,
                }

            # In the case where the notification is no longer be on the GOV.NOTIFY service, the child Audit objects
            # still exist, but they're stuck on 'sending'
            delivery_exists = Audit.objects.filter(parent=audit).exists()
            if not delivery_exists:
                delivery_audit = Audit.objects.create(
                    type=AUDIT_TYPE_DELIVERED,
                    parent=audit,
                    created_by=audit.created_by,
                    case_id=audit.case_id,
                    model_id=audit.model_id,
                    content_type=audit.content_type,
                    data={
                        "status": status.get("status"),
                        "sent_at": status.get("sent_at"),
                        "completed_at": status.get("completed_at"),
                    },
                )
                logger.info(f"Created {delivery_audit} / {delivery_audit.data}")
