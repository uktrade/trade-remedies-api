from django.db import models
from django.db.models import Q, OuterRef, Subquery
from django.utils import timezone
from django.contrib.postgres import fields
from .workflow import CaseWorkflowState
from .submissionstatus import SubmissionStatus


class SubmissionTypeManager(models.Manager):
    def get_available_submission_types_for_case(self, case, direction_kwargs):
        open_time_windows = CaseWorkflowState.objects.filter(
            Q(due_date__isnull=True) | Q(due_date__gte=timezone.now()),
            case=case,
            key=OuterRef("time_window_key"),
        ).values_list("key", flat=True)
        return (
            self.filter(**direction_kwargs)
            .filter(time_window_key__in=Subquery(open_time_windows))
            .order_by("order", "name")
        )


class SubmissionType(models.Model):
    """
    A type of submission.
    The key is a string that determines which representations the submission type should use.
    (i.e., which templates, routes, logic etc. For example, Ex Officion applications and Applications
    should use the same templates and logic).
    A type can require another type to exist in the case. For example, Response to statement of
    essential facts can be created by customers only if the Statement of essential facts was
    published to the case.
    Submissions can have a direction which determines the potential source and target of the submissio.
    Some can be created by Public to the TRA, some the other way around and some are bi-directional.
    Most submissions will use a standard Notify template to alert deficiencies or success to the customer.
    However, if deficiency/success_template are defined (as a system parameter key holding the actual notify id),
    they will be used instead.
    """

    name = models.CharField(max_length=150, null=False, blank=False)
    key = models.CharField(max_length=50, null=True, blank=True)
    requires = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    direction = models.IntegerField(
        choices=((-1, "None"), (0, "Both"), (1, "Public -> TRA"), (2, "Public <- TRA"),), default=0
    )
    deficiency_template = models.CharField(max_length=100, null=True, blank=True)
    success_template = models.CharField(max_length=100, null=True, blank=True)
    notify_template = models.CharField(max_length=100, null=True, blank=True)
    time_window_key = models.CharField(max_length=100, blank=True)
    order = models.SmallIntegerField(default=0)
    meta = fields.JSONField(default=dict)

    objects = SubmissionTypeManager()

    def __str__(self):
        return self.name

    # @method_cache
    def to_dict(self, case=None):
        _dict = {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "direction": self.direction,
            "requires": self.requires.to_dict() if self.requires else None,
            "has_requirement": False,
            "notify_template": self.notify_template,
            "meta": self.meta,
        }
        if case:
            _dict["has_requirement"] = self.has_requirement(case)
        return _dict

    @property
    def default_status(self):
        """
        Return the default submission status for this submission type
        """
        try:
            return self.submissionstatus_set.get(default=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def sent_status(self):
        """
        Return the `sent` submission status for this submission type
        """
        try:
            return self.submissionstatus_set.get(sent=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def received_status(self):
        """
        Return the received submission status for this submission type
        """
        try:
            return self.submissionstatus_set.get(received=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def review_status(self):
        """
        Return the review submission status for this submission type
        """
        try:
            return self.submissionstatus_set.get(review=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def sufficient_status(self):
        """
        Return the sufficient submission status for this submission type
        """
        try:
            return self.submissionstatus_set.get(sufficient=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def deficient_status(self):
        """
        Return the deficient submission status for this submission type.
        Not sufficient and set to version.
        """
        try:
            return self.submissionstatus_set.exclude(sufficient=True).get(version=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def draft_status(self):
        """
        Return the update submission status for this submission type.
        """
        try:
            return self.submissionstatus_set.get(draft=True)
        except SubmissionStatus.DoesNotExist:
            return None

    @property
    def review_ok_status(self):
        """
        Return the review ok submission status for this submission type.
        """
        try:
            return self.submissionstatus_set.get(review_ok=True)
        except SubmissionStatus.DoesNotExist:
            return None

    def has_requirement(self, case):
        """
        If this submission type specifies requirement of another type to exist,
        check if the case has that submission type published to qualify.
        """
        if self.requires:
            return case.submission_set.filter(type=self.requires).exists()
        return True

    @staticmethod
    def submission_status_map():
        """
        Return a map of all submission statuses per type, by their function
        """
        sub_types = {}
        for subtype in SubmissionType.objects.all():
            yes, no = subtype.sufficient_status, subtype.deficient_status
            yes_id = yes.id if yes else None
            no_id = no.id if no else None
            sub_types[str(subtype.id)] = {"YES": yes_id, "NO": no_id, "keys": [yes_id, no_id]}
        return sub_types
