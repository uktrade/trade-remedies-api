from django.contrib.postgres import fields
from django.db import models

from core.decorators import method_cache


class CaseType(models.Model):
    """
    A type of case.
    Each type can have a unique workflow template attached to it which will be assigned
    to the case itself on creation.
    """

    name = models.CharField(max_length=150, null=False, blank=False)
    acronym = models.CharField(max_length=4, null=True, blank=True)
    colour = models.CharField(max_length=16, null=True, blank=True)
    order = models.SmallIntegerField(default=0)
    internal = models.BooleanField(default=False)
    workflow = models.ForeignKey(
        "workflow.WorkflowTemplate", null=True, blank=True, on_delete=models.PROTECT
    )
    meta = models.JSONField(default=dict)

    def __str__(self):
        return self.name

    @method_cache
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "acronym": self.acronym,
            "colour": self.colour,
            "internal": self.internal,
            "meta": self.meta,
            "workflow": (
                {"id": str(self.workflow.id), "name": self.workflow.name} if self.workflow else {}
            ),
        }

    def to_embedded_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "acronym": self.acronym,
            "colour": self.colour,
            "internal": self.internal,
        }

    def criteria_to_kwargs(self):
        if self.meta.get("criteria"):
            kwargs = {}
            for item in self.meta.get("criteria"):
                kwargs[item["key"]]
        return None

    @property
    def document_bundle(self):
        """
        Return the currently live document bundle for this case type
        """
        return self.documentbundle_set.filter(status="LIVE").first()
