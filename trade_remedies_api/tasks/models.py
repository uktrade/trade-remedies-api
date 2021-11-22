from django.db import models
from core.base import BaseModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres import fields
from core.utils import get


class Task(BaseModel):
    """
    Tasks provide an achor for an activity.
    They are assigned to one user at a time, have a due date, a status and can be nested
    Tasks can be anchored to any content type in the system
    """

    reference = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    model_id = models.UUIDField(null=True, blank=True)
    model_key = models.CharField(max_length=250, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.PROTECT)
    due_date = models.DateField(null=True)
    assignee = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        related_name="%(class)s_assignee",
        on_delete=models.SET_NULL,
    )
    priority = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    data = fields.JSONField(null=True, blank=True)

    options = (
        {
            "unique_together": {("case", "reference")},
        },
    )

    class Meta:
        index_together = ["content_type", "model_id"]

    def __str__(self):
        return f"{self.reference}:{self.name or str(self.id)}"

    def reference_string(self):
        return f"{(self.reference or 0):04}"

    @staticmethod
    def for_model(model, descending=True):
        order = "-created_at" if descending else "created_at"
        content_type = ContentType.objects.get_for_model(model)
        return Task.objects.filter(content_type=content_type, model_id=model.id).order_by(order)

    def save(self, *args, **kwargs):
        """
        Inject next task reference number
        """
        if not self.reference:
            self.reference = (
                get(
                    Task.objects.filter(case_id=self.case_id).aggregate(
                        ref=models.Max("reference")
                    ),
                    "ref",
                )
                or 0
            ) + 1
        return super().save(*args, **kwargs)

    def _to_dict(self, fields=None):
        return self.to_dict(fields={"name": 0, "description": 0})
