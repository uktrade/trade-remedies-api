import uuid
from django.db import models
from django.conf import settings


class Notice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=500, null=False, blank=False)
    reference = models.CharField(max_length=30, null=False, blank=False)
    case_type = models.ForeignKey("cases.CaseType", null=True, blank=True, on_delete=models.PROTECT)
    review_case = models.ForeignKey(
        "cases.Case", null=True, blank=True, on_delete=models.PROTECT, related_name="review_case"
    )
    published_at = models.DateField(null=True, blank=True)
    terminated_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference}: {self.name}"

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "reference": self.reference,
            "published_at": self.published_at.strftime(settings.API_DATE_FORMAT)
            if self.published_at
            else None,
            "terminated_at": self.terminated_at.strftime(settings.API_DATE_FORMAT)
            if self.terminated_at
            else None,
            "case_type": self.case_type.to_embedded_dict() if self.case_type else None,
            "review_case": self.review_case._to_minimal_dict() if self.review_case else None,
        }

    def to_embedded_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "reference": self.reference,
        }
