from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings
from audit import AUDIT_TYPE_DELIVERED
from audit.models import Audit
from audit.tasks import audit_log_task


def new_audit_record_to_dict(
    audit_type, user=None, assisted_by=None, case=None, model=None, data=None, milestone=False
):
    """
    Convert the parameters for a new audit record to a dictionary suitable
    for sending to a celery broker.
    """

    audit_dict = {
        "type": audit_type,
        "created_by_id": None,
        "created_at": timezone.now(),
        "assisted_by_id": None,
        "case_id": None,
        "content_type_id": None,
        "model_id": None,
        "data": data,
        "milestone": milestone,
    }

    if user:
        audit_dict["created_by_id"] = user.id
    if assisted_by:
        audit_dict["assisted_by_id"] = assisted_by.id
    if case:
        audit_dict["case_id"] = case.id
    if model:
        content_type = ContentType.objects.get_for_model(model)
        audit_dict["content_type_id"] = content_type.id
        audit_dict["model_id"] = model.id

    return audit_dict


def audit_log(
    audit_type, user=None, assisted_by=None, case=None, model=None, data=None, milestone=False
):
    """
    Create an audit record.

    :param int audit_type: An AUDIT_TYPE_* constant.
    :param core.User user: An optional user generating the audit log.
    :param core.User asssisted_by: An optional additional user.
    :param cases.Case case: An optional associated case.
    :param model: An optional instance of any django model.
    :param data: Optional data that can be JSON serialized.
    :param bool milestone: True if the record is a milestone. Defaults to False.
    """
    audit_dict = new_audit_record_to_dict(
        audit_type,
        user=user,
        assisted_by=assisted_by,
        case=case,
        model=model,
        data=data,
        milestone=milestone,
    )

    if settings.RUN_ASYNC:
        audit_log_task.delay(audit_dict)
    else:
        audit_log_task(audit_dict)


def get_notify_fail_report(case=None, detail=False):
    audits = Audit.objects.filter(
        type=AUDIT_TYPE_DELIVERED, data__status__in=["permanent-failure", "temporary-failure"]
    ).exclude(data__ack__isnull=False)
    if case:
        audits = audits.filter(case_id=case.id)
    report = {}
    for audit in audits:
        report.setdefault(key, {"permanent-failure": [], "temporary-failure": []})
        key = str(audit.case_id)
        sub_key = audit.data.get("status")
        if not detail:
            report[key][sub_key].append(audit.parent_id)
        else:
            contact = audit.parent.get_model()
            if contact:
                report[key][sub_key].append({"id": str(contact.id), "email": contact.email})
    return report
