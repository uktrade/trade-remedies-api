import datetime
from dateutil.relativedelta import relativedelta
from django.db import models
from django.contrib.postgres import fields
from django.conf import settings
from core.decorators import method_cache


class CaseTypeManager(models.Manager):
    def available_case_review_types(self, case):  # noqa:C901
        """
        Return all available review case types available for a given case,
        based on the milestone dates associated with it and the case type criteria.
        Returns a tuple of two lists. The first element contains the available review type models,
        and the second is a list of dicts for all review types, with enhanced properties
        reltaed to the review availability durations.
        """
        milestones = case.case_milestone_index()
        now = datetime.date.today()
        reviews = []
        for review_type in self.filter(meta__review=True):
            status = "ok"
            review_dict = review_type.to_dict()
            criteria = review_type.meta.get("criteria", [])
            start_date = None
            end_date = None
            for test in criteria:
                criterion = test["criterion"]
                if criterion in ["before", "after"]:
                    duration_unit = test["unit"]
                    duration_value = test["value"]
                    offset = relativedelta(**{duration_unit: duration_value})
                    milestone = test["milestone"]
                    if milestone not in milestones:
                        status = "milestone_missing"
                        break
                    rel_date = milestones[milestone] + offset
                    if criterion == "after":
                        start_date = (
                            rel_date if not start_date or (rel_date > start_date) else start_date
                        )
                    else:
                        end_date = rel_date if not end_date or (rel_date < end_date) else end_date
                elif criterion == "parent_case_types":
                    acronym = case.type.acronym
                    if acronym not in test.get("value", []):
                        status = "invalid_case_type"
                elif criterion == "state_value":
                    state_value = case.get_state_key(key=test["key"])
                    if not state_value or state_value.value != test["value"]:
                        status = "invalid_case_type"
            if status == "ok":
                if start_date and now < start_date:
                    status = "before_start"
                if end_date and now > end_date:
                    status = "after_end"
                review_dict["dates"] = {
                    "start": start_date.strftime(settings.API_DATETIME_FORMAT)
                    if start_date
                    else None,
                    "end": end_date.strftime(settings.API_DATETIME_FORMAT) if end_date else None,
                    "status": status,
                }
                reviews.append(review_dict)
        return reviews


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

    objects = CaseTypeManager()

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
            "workflow": {"id": str(self.workflow.id), "name": self.workflow.name}
            if self.workflow
            else {},
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
