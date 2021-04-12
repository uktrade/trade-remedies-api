from django.db import models
from django.utils import timezone
from django.conf import settings
from logging import getLogger
from core.base import SimpleBaseModel
from core.decorators import method_cache
from cases.constants import (
    SUBMISSION_DOCUMENT_TYPE_CUSTOMER,
    SUBMISSION_DOCUMENT_TYPE_TRA,
    SUBMISSION_DOCUMENT_TYPE_DEFICIENCY,
)

logger = getLogger(__name__)


class SubmissionDocumentType(models.Model):
    name = models.CharField(max_length=250, null=False, blank=False)
    key = models.CharField(max_length=20, null=False, blank=False)

    def __str__(self):
        return self.name

    @method_cache
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
        }

    @staticmethod
    def type_by_user(user):
        if user.is_tra():
            return SubmissionDocumentType.objects.get(id=SUBMISSION_DOCUMENT_TYPE_TRA)
        else:
            return SubmissionDocumentType.objects.get(id=SUBMISSION_DOCUMENT_TYPE_CUSTOMER)


class SubmissionDocument(SimpleBaseModel):
    """
    Links a document to a submission
    """

    type = models.ForeignKey(
        SubmissionDocumentType, null=True, blank=True, on_delete=models.PROTECT
    )
    submission = models.ForeignKey(
        "cases.Submission", null=False, blank=False, on_delete=models.CASCADE
    )
    document = models.ForeignKey(
        "documents.Document", null=False, blank=False, on_delete=models.CASCADE
    )
    downloads = models.SmallIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    issued = models.BooleanField(default=False, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.PROTECT)
    deficient = models.BooleanField(default=False)
    sufficient = models.BooleanField(default=False)

    def __str__(self):
        _conf = "[C]" if self.document.confidential else ""
        return f"{_conf}{self.document} @ {self.submission}"

    def set_issued_at(self, user):
        """
        Set the attributes to make this document issued to the public case record.
        """
        self.issued_at = timezone.now()
        self.issued = True  # TODO: Remove
        self.issued_by = user

    def issue_to_submission(self, user):
        """
        Set issued_at flags and save.
        """
        self.set_issued_at(user)
        self.save()
        return self

    def to_dict(self, user=None, with_submissions=False):
        _dict = self.document.to_embedded_dict()
        _dict.update(
            {
                "type": self.type.to_dict(),
                "downloads": self.downloads,
                "deficient": self.deficient,
                "sufficient": self.sufficient,
                "needs_review": self.needs_review,
                "issued": self.issued,
                "issued_at": self.issued_at.strftime(settings.API_DATETIME_FORMAT)
                if self.issued_at
                else None,
                "issued_by": self.issued_by.to_embedded_dict() if self.issued_by else None,
                "downloadable": self.downloadable_by(user) if user else None,
            }
        )
        if with_submissions and self.submission:
            role = self.submission.organisation_case_role()
            _dict.update(
                {
                    "submission": {
                        "id": self.submission.id,
                        "version": self.submission.version,
                        "type": {"name": self.submission.type.name,},
                        "organisation": {
                            "name": self.submission.organisation
                            and self.submission.organisation.name,
                            "id": self.submission.organisation and self.submission.organisation.id,
                        },
                        "organisation_case_role": {"name": role and role.name},
                    }
                }
            )
        return _dict

    @method_cache
    def to_minimal_dict(self):
        _dict = {
            "type": self.type.to_dict(),
            "submission_id": str(self.submission_id),
            "downloads": self.downloads,
        }
        _dict.update(self.document.to_minimal_dict())
        return _dict

    @property
    def needs_review(self):
        return all([not self.deficient, not self.sufficient, self.document.safe])

    @property
    def case(self):
        return self.submission.case

    def downloadable_by(self, user):
        # TODO: Temp fix - remove later:
        if not self.submission.status:
            logger.warning("Submission type '%s' has no default status", self.submission.type.name)
            self.submission.status = self.submission.type.default_status
            self.submission.save()
        non_conf = not self.document.confidential
        own = self.document.created_by.id == user.id
        published = self.submission.issued_at
        not_locked = not self.submission.locked
        is_case_document = self.type.id in (
            SUBMISSION_DOCUMENT_TYPE_TRA,
            SUBMISSION_DOCUMENT_TYPE_DEFICIENCY,
        )
        return is_case_document or non_conf or (own and not_locked)
