from django.db import models
from django.utils import timezone
from cases.outcomes import register_outcomes


class TimeGateStatusManager(models.Manager):
    def get_to_process(self):
        return TimeGateStatus.objects.filter(
            ack_at__isnull=True,
            workflow_state__due_date__isnull=False,
            workflow_state__due_date__lte=timezone.now(),
        )


class TimeGateStatus(models.Model):
    workflow_state = models.OneToOneField(
        "cases.CaseWorkflowState", on_delete=models.PROTECT, primary_key=True
    )
    ack_at = models.DateTimeField(null=True, blank=True)
    ack_by = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.PROTECT)

    objects = TimeGateStatusManager()


register_outcomes()
