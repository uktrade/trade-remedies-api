import logging
from dateutil.parser import parse
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from cases.models import TimeGateStatus, Case
from audit.utils import audit_log
from audit.models import AUDIT_TYPE_EVENT

logger = logging.getLogger(__name__)


@shared_task()
def process_timegate_actions():
    workflow_state_ids = TimeGateStatus.objects.get_to_process().values_list(
        "workflow_state_id", flat=True
    )

    for workflow_state_id in workflow_state_ids:
        logger.info("Processing timegate action: %s", workflow_state_id)
        if settings.RUN_ASYNC:
            process_timegate_action.delay(workflow_state_id)
        else:
            process_timegate_action(workflow_state_id)


@shared_task()
def process_timegate_action(workflow_state_id, user=None):
    status = TimeGateStatus.objects.select_related("workflow_state").get(
        workflow_state_id=workflow_state_id
    )

    case = status.workflow_state.case
    case_state = case.workflow.get_state()
    node_spec = case_state.key_index[status.workflow_state.key]
    status.ack_at = timezone.now()
    status.ack_by = user
    status.save(update_fields=["ack_at", "ack_by"])
    if node_spec.get("outcome_spec"):
        case_state.evaluate_outcome(status.workflow_state.key, case=case, requested_by=user)


@shared_task()
def check_measure_expiry():
    """
    Check all archived cases which are not already set to Measure Expired stage,
    and determine if all their meaures are expired.
    """
    cases = Case.objects.filter(
        initiated_at__isnull=False,
        archived_at__isnull=False,
    ).exclude(stage__key="MEASURES_EXPIRED")
    for case in cases:
        latest_expiry = case.get_state_key("LATEST_MEASURE_EXPIRY")
        if latest_expiry and latest_expiry.value:
            # print( TODO - remove if not needed
            #     timezone.now().date() <= parse(latest_expiry.value).date(),
            #     timezone.now().date(),
            #     parse(latest_expiry.value).date(),
            # )
            if timezone.now().date() >= parse(latest_expiry.value).date():
                case.set_stage_by_key("MEASURES_EXPIRED")
                audit_log(
                    audit_type=AUDIT_TYPE_EVENT,
                    model=case,
                    case=case,
                    milestone=True,
                    data={"message": "Measures expired"},
                )
