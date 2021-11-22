from django.db import models
from core.decorators import method_cache


class SubmissionStatus(models.Model):
    """
    A status of a submission. Each submission type can have their own set of status
    indicators. Certain statuses can be designated as "locking", which will cause the
    underlying submission to go into a locked state.
    'version', when true will archive the submission and clone it as a new version.
    This denotes deficiency.
    'duration' specifies the number of days from setting the status of the due date.
    'default designates this status to be the default status for new submissions of this type.
    'sufficient' designates this status denotes sufficiency to proceed when true.
    'sent' denotes a "sent to customer" status
    'received' denotes a "received from customer" status
    'draft' denotes that a submission is being drafted (files added or removed)
    by customer since it was last sent.
    """

    id = models.IntegerField(primary_key=True)
    type = models.ForeignKey(
        "cases.SubmissionType", null=False, blank=False, on_delete=models.PROTECT
    )
    name = models.CharField(max_length=100, null=False, blank=False)
    public_name = models.CharField(max_length=100, null=True, blank=True)
    order = models.SmallIntegerField(default=0)
    locking = models.BooleanField(default=False)  # submission locks
    version = models.BooleanField(default=False)  # setting this status will trigger reversioning
    duration = models.SmallIntegerField(
        null=True, blank=True
    )  # days to trigger time gate from setting this
    default = models.BooleanField(default=False)  # default status
    sent = models.BooleanField(default=False)  # submission sent to customer
    received = models.BooleanField(default=False)  # submission sent to and received by TRA
    sufficient = models.BooleanField(default=False)  # submission was sufficient
    review = models.BooleanField(default=False)  # submission in review
    review_ok = models.BooleanField(default=False)  # Sufficient review
    draft = models.BooleanField(default=False)  # submission is being drafted
    send_confirmation_notification = models.CharField(max_length=100, null=False, blank=True)

    def __str__(self):
        locking_indicator = "*" if self.locking else ""
        return f"{self.type.name}: {self.name}{locking_indicator}"

    @method_cache
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "public_name": self.public_name,
            "order": self.order,
            "locking": self.locking,
            "version": self.version,
            "default": self.default,
            "sent": self.sent,
            "received": self.received,
            "sufficient": self.sufficient,
            "review": self.review,
            "review_ok": self.review_ok,
            "draft": self.draft,
            "type": self.type.to_dict(),
            "deficiency_notice": self.deficiency_notice,
            "evaluate_deficiency": self.evaluate_deficiency,
        }

    @property
    def evaluate_deficiency(self):
        """
        Based on this status, is the submission ready for evaluation
        """
        return self.received or self.review  # and not self.sufficient

    @property
    def deficiency_notice(self):
        """
        Based on this status, is a deficiency notice able to be sent?
        """
        return (self.version or self.review) and not self.sufficient
