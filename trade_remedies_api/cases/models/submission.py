import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from titlecase import titlecase

from audit import AUDIT_TYPE_NOTIFY
from cases.constants import (
    CASE_TYPE_SAFEGUARDING,
    SUBMISSION_DOCUMENT_TYPE_TRA,
    SUBMISSION_TYPE_APPLICATION,
    TRA_ORGANISATION_ID,
)
from contacts.models import Contact
from core.base import BaseModel
from core.models import SystemParameter, User
from core.tasks import send_mail
from core.utils import public_login_url
from notes.models import Note
from security.constants import SECURITY_GROUPS_PUBLIC, SECURITY_GROUPS_TRA
from security.models import OrganisationCaseRole
from .submissiondocument import SubmissionDocument, SubmissionDocumentType
from .submissiontype import SubmissionType
from .workflow import CaseWorkflowState


class SubmissionManager(models.Manager):
    def get_submission(self, id, case=None):
        """
        Get a submission by ID with optional case filtering and result caching.
    
        Args:
            id: The submission ID
            case: Optional case to filter by
        
        Returns:
            Submission object with related fields preloaded
        """
        # Import cache module inside the method to avoid circular imports
        from django.core.cache import cache

        query_kwargs = {"id": id}
        if case:
            query_kwargs["case"] = case

        # Generate a cache key based on submission ID and case ID (if provided)
        cache_key = f"submission_{id}_{case.id if case else 'none'}"

        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        

        submission = self.select_related(
            "case",
            "organisation",
            "type",
            "status",
            "contact",
            "sent_by",
            "created_by",
            "case_role",
            "issued_by",
        ).get(**query_kwargs)

        # Cache the result for future queries (cache for 10 mins)
        cache.set(cache_key, submission, 60 * 10)

        return submission

    def get_submissions(
        self,
        case,
        requested_by,
        requested_for=None,
        private=True,
        submission_id=None,
        show_global=False,
        show_archived=False,
        sampled_only=False,
        submission_type_id=None,
    ):
        """
        Get all case submissions as requested by a user, for a specific organisation.
        if private is True, show only submissions created by/for this organisation,
        otherwise get all submissions not directly related to this organisation and
        that either have no files or have at least one issued document.
        When incoming is True, only incoming submissions will be shown
        """
        from .utils import get_case

        case = get_case(case)
        submissions = self.filter(case=case, deleted_at__isnull=True).select_related(
            "type",
            "status",
            "organisation",
            "contact",
            "case",
            "case__type",
            "case__stage",
            "created_by",
            "sent_by",
            "received_from",
            "issued_by",
            "contact__userprofile",
            "contact__userprofile__user",
            "parent",
        )

        submissions = submissions.prefetch_related(
            "submissiondocument_set__document",
            "submissiondocument_set__type",
            "invitations__contact",
            models.Prefetch(
                "organisation__organisationcaserole_set",
                queryset=OrganisationCaseRole.objects.filter(case=case),
            ),
        )

        if submission_type_id:
            _sub_type = SubmissionType.objects.get(id=submission_type_id)
            submissions = submissions.filter(type=_sub_type)
        if requested_for:
            if submission_id:
                submissions = submissions.filter(id=submission_id)
            elif private:
                submissions = (
                    submissions.filter(organisation=requested_for)
                    .filter(
                        Q(created_by__groups__name__in=SECURITY_GROUPS_PUBLIC)
                        | Q(status__default=False)
                    )
                    .distinct()
                )
            else:
                # Public case record. All submissions with docs that are issued
                submissions = submissions.exclude(issued_at__isnull=True)
        elif submission_id:
            submissions = submissions.filter(id=submission_id)

        # TRA users filter by global (sent to all orgs) submissions
        if not show_global and not submission_id and requested_by.is_tra():
            submissions = submissions.exclude(organisation__isnull=True)
        # latest_version = submissions.filter(id=OuterRef('id'), version=models.Max)
        if not show_archived and not submission_id:
            submissions = submissions.filter(archived=False)
        if sampled_only:
            submissions = submissions.filter(
                Q(
                    organisation__organisationcaserole__case=case,
                    organisation__organisationcaserole__sampled=bool(sampled_only),
                )
                | Q(organisation__isnull=True)
            ).distinct()
        # TODO: Exclude drafts from CW (include in public - needs switch)
        # submissions = submissions.exclude(
        # type=SUBMISSION_TYPE_REGISTER_INTEREST, status=SUBMISSION_STATUS_REGISTER_INTEREST_DRAFT
        # )
        submissions = submissions.order_by("-created_at")
        return submissions


class Submission(BaseModel):
    """
    A collection of data being submitted to the case, either by a customer or caseworker.
    Applications, Questionnaire bundles and their responses, etc. are all "submissions" to the case.
    Submissions can have a parent submission they are in response to.
    The organisation field designates which organisation this belongs to.
    The parent field contains the top level original submission which is the parent of this
    and other versions of the submission. To get the direct previous version use previous_version
    """

    type = models.ForeignKey(
        "cases.SubmissionType", null=False, blank=False, on_delete=models.PROTECT
    )
    status = models.ForeignKey(
        "cases.SubmissionStatus", null=True, blank=True, on_delete=models.PROTECT
    )
    name = models.CharField(max_length=500, null=True, blank=True)
    organisation_name = models.CharField(max_length=500, null=True, blank=True)
    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.PROTECT)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.PROTECT
    )
    contact = models.ForeignKey("contacts.Contact", null=True, blank=True, on_delete=models.PROTECT)
    review = models.BooleanField(null=True)
    documents = models.ManyToManyField("documents.Document", through="SubmissionDocument")
    doc_reviewed_at = models.DateTimeField(null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    version = models.SmallIntegerField(default=1)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_sent_by",
        on_delete=models.SET_NULL,
    )
    received_at = models.DateTimeField(null=True, blank=True)
    received_from = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_received_from",
        on_delete=models.SET_NULL,
    )
    due_at = models.DateTimeField(null=True, blank=True)
    deficiency_sent_at = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    case_role = models.ForeignKey(
        "security.CaseRole", null=True, blank=True, on_delete=models.PROTECT
    )
    url = models.CharField(max_length=2000, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    time_window = models.SmallIntegerField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_issued_by",
        on_delete=models.SET_NULL,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    deficiency_notice_params = models.JSONField(null=True, blank=True)
    primary_contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        related_name="submission_primary_contacts",
        on_delete=models.PROTECT,
    )

    objects = SubmissionManager()

    class Meta:

        permissions = (
            ("send_deficiency_notice", "Can send deficiency notices"),
            ("publish_public", "Can issue to the public case record"),
            ("publish_public_tasklist", "Can complete the public publish tasklist"),
            (
                "publish_non_conf_interested_parties",
                "Can publish the non confidentials of interested parties",
            ),
            ("close_case_tasks", "Can complete close case tasks"),
            ("case_admin", "Can access case admin panel"),
        )

    def __str__(self):
        version_ind = f" (v{self.version})" if self.version > 1 else ""
        if self.name:
            return f"{self.type}: {self.case}: {self.name}{version_ind}"
        return f"{self.type}: {self.case}{version_ind}"

    @property
    def organisation_case_role_name(self):
        """
        Returns the organisation case role name for the submission
        """
        try:
            organisation_case_role = self.case.organisationcaserole_set.get(
                organisation=self.organisation
            )
            return organisation_case_role.role.name
        except OrganisationCaseRole.DoesNotExist:
            # Perhaps the Organisation is the TRA in which case an OrganisationCaseRole
            # will not exist.
            if self.organisation and (
                self.organisation.gov_body or self.organisation.name == "Trade Remedies Authority"
            ):
                # it's the TRA/Secretary of State
                return "Trade Remedies Authority"

    @transaction.atomic
    def delete(self, purge=False):
        """
        If purging data, e.g., when a submission is cancelled by the user,
        ensure that documents relating to bundles submitted by the case workers are first
        detached before other documents are purged.
        In the same way, any invites associated are also deleted
        """
        if purge:
            self.submissiondocument_set.filter(document__documentbundle__isnull=False).delete()
            for document in self.documents.all():
                document.set_user_context(self.user_context)
                document.delete(purge=True, delete_file=True)
            self.invitations.all().delete()
        super().delete(purge=purge)

    def save(self, *args, **kwargs):
        is_new_instance = self.is_new_instance
        if is_new_instance and self.status and self.status.duration and not self.time_window:
            self.time_window = self.status.duration

        if is_new_instance:
            # This code forces the due_date at save based on the submission type
            # which is not desirable behaviour
            due_at = (
                CaseWorkflowState.objects.filter(case=self.case, key=self.type.time_window_key)
                .values_list("due_date", flat=True)
                .first()
            )
            if due_at:
                self.due_at = due_at
            # denormalise the name of the organisation
            if not self.organisation_name and self.organisation:
                self.organisation_name = self.organisation.name
        super().save(*args, **kwargs)
        if is_new_instance:
            # Add the case documents  to the submission on creation
            # if there is a matching sub type for this case
            # First, find the right bundle
            document_bundle = self.type.documentbundle_set.filter(
                case_id=self.case.id, status="LIVE"
            ).first()
            if document_bundle:
                submission_document_type = SubmissionDocumentType.objects.get(
                    id=SUBMISSION_DOCUMENT_TYPE_TRA
                )
                # copy the documents into the new submission
                for document in document_bundle.documents.all():
                    self.add_document(document=document, document_type=submission_document_type)

    @property
    def locked(self):
        return self.status.locking if self.status else False

    @property
    def previous_version(self):
        if self.parent and self.version > 2:
            return Submission.objects.filter(parent=self.parent, version=self.version - 1).first()
        elif self.parent and self.version == 2:
            return self.parent
        return None

    @property
    def deficiency_documents(self):
        """
        Return the deficiency documents on THIS submission instance.
        Note that when a submission is set to be deficient, the deficiency
        documents are associated with it, and then a NEW version is cloned which
        does include all the documents of the original submission except the deficiency
        ones. Therefore to get the deficiency document of a submission, we normally
        want those associated with it's parent, since it was the parent which was
        deficient and the current version is the one created to correct that deficiency.
        """
        return SubmissionDocument.objects.select_related(
            "document",
            "submission",
            "type",
        ).filter(submission=self, type__key="deficiency", deleted_at__isnull=True)

    def get_parent_deficiency_documents(self):
        """
        If available, return the deficiency documents associated with the parent submission.
        Otherwise, return None
        """
        if self.previous_version:
            return self.previous_version.deficiency_documents
        return []

    def submission_documents(self, requested_by=None, requested_for=None):
        """Documents for a submission.

        :param (core.models.User) requested_by: Requesting user
        :param (organisations.models.Organisation) requested_for: for organisation
        :returns (QuerySet): QuerySet of this submission's SubmissionDocuments
        """
        documents = SubmissionDocument.objects.select_related(
            "document",
            "submission",
            "type",
            "issued_by",
        ).filter(submission=self, document__deleted_at__isnull=True)
        if requested_by and requested_for and requested_for != self.organisation:
            documents = documents.filter(
                document__confidential=False, submission__issued_at__isnull=False
            )
        if requested_by and requested_by.is_tra():
            documents = documents.filter(
                Q(created_by__groups__name__in=SECURITY_GROUPS_TRA)
                | Q(submission__status__draft=False)
            ).distinct()
        return documents

    def add_document(self, document, document_type, issued=False, issued_by=None):
        """
        Add a document to this submission.
        A document added must have a type designating it's purpose. It needs to be one of the
        registered submission document types.
        """
        try:
            sub_doc = SubmissionDocument.objects.get(
                type=document_type, submission=self, document=document
            )
            if issued_by:
                sub_doc.set_user_context(issued_by)
        except SubmissionDocument.DoesNotExist:
            sub_doc = SubmissionDocument.objects.create(
                type=document_type,
                submission=self,
                document=document,
                created_by=issued_by,
                user_context=issued_by,
            )
        if issued:
            sub_doc.set_issued_at(issued_by)
            sub_doc.save()
        return sub_doc

    def transition_status(self, status):
        """
        Transition the status of this submission to a given status.
        If the new status mandates versioning, creates a clone of the submission and
        updates the status of the clone leaving the original unchanged.
        If a duration is set, set the due date on the clone or the original submission.
        """
        from cases.models.utils import get_submission_status

        new_status = get_submission_status(status)
        clone = None
        self.status = new_status
        latest = self

        if self.status.version:
            self.save()
            clone = self.clone()
            latest = clone

        if (
            self.case.type.id == CASE_TYPE_SAFEGUARDING
            and self.type.id == SUBMISSION_TYPE_APPLICATION
            and self.status == self.type.received_status
        ):
            self.case.set_user_context(self.user_context)
            self.case.set_next_action("INIT_ASSESS")

        # This bit of code is overriding the due_at that's getting set on submissions
        # on a change of status.
        # I don't think it's any use now - so I've removed the config.
        # latest.due_at = timezone.now() + datetime.timedelta(days=new_status.duration)
        # if new_status.duration else None
        latest.save()
        latest.refresh_from_db()
        return self, clone

    def remove_document(self, document, requested_by):
        """
        Remove a document from this submission.
        TODO: Currently the document relationship to the submission is deleted. Consider if to
              just mark deleted.
        """
        try:
            sub_doc = SubmissionDocument.objects.get(document=document, submission=self)
            sub_doc.set_user_context(requested_by)
            sub_doc.delete()
        except SubmissionDocument.DoesNotExist:
            pass
        return None

    def organisation_case_role(self, outer=None):
        role = None
        if self.organisation:
            # supress if it's the TRA as we don't want the TRA to show as 'applicant'
            # in ex-officio cases
            if not self.organisation.gov_body:
                role = OrganisationCaseRole.objects.get_organisation_role(
                    self.case, self.organisation, outer=outer
                )
        return role

    @property
    def versions(self):
        """
        Return all previous versions of this submission (including parent)
        """
        if self.parent:
            return Submission.objects.filter(Q(parent=self.parent) | Q(id=self.parent.id)).order_by(
                "version"
            )
        else:
            # If we are the first version
            return Submission.objects.filter(Q(parent=self) | Q(id=self.id)).order_by("version")

    def _prepare_documents(self, **kwargs):
        """Prepare submission documents.

        Builds a dictionary representation of submission docs (optionally by a
        requested user/for a requesting organisation).

        :param (dict) **kwargs: Arbitrary keyword arguments as follows:
          :with_documents (bool): If True build documents else return an empty list.
          :requested_by (core.models.User): User object.
          requested_for (organisations.models.Organisation): Organisation object.
        :returns (list): A list of submission documents as dicts.
        """
        if not kwargs.get("with_documents", True):
            return []
        requested_by = kwargs.get("requested_by")
        documents = self.submission_documents(
            requested_by=requested_by, requested_for=kwargs.get("requested_for")
        )
        submission_docs = [doc.to_dict(user=requested_by) for doc in documents]
        return submission_docs

    def _needs_review(self):
        """Needs investigator review.

        Flag if the submission should be considered 'new'. This is determined
        as follows:
          - The submission's status is not an initial one (default)
          - The submission is not version 1
          - The document was created by a customer (not TRA)
          - At least one document is flagged as needing review (i.e. safe,
            not sufficient and not deficient)

        :returns (bool): True if the submission is considered 'new' and requires
          review, False otherwise.
        """
        if self.status and self.status.default and self.version == 1:
            return False
        needs_review = False
        for doc in self.submission_documents():
            if doc.created_by is None:
                continue
            if doc.created_by.is_tra():
                continue
            if doc.needs_review:
                needs_review = True
                break
        return needs_review

    def _to_dict(self, **kwargs):
        _previous_versions = [
            {
                "id": str(version.id),
                "type": self.type.name,
                "name": version.name,
                "version": version.version,
                "deficiency_sent_at": (
                    version.deficiency_sent_at.strftime(settings.API_DATETIME_FORMAT)
                    if version.deficiency_sent_at
                    else None
                ),
            }
            for version in self.versions
        ]
        _previous_version = _previous_versions[-1] if _previous_versions else None
        _is_latest_version = (
            _previous_version is None or str(self.id) == _previous_versions[-1]["id"]
        )
        out = self.to_embedded_dict(**kwargs)
        # if this is not the latest version lock the submission regardless.
        if not _is_latest_version:
            out["status"]["locking"] = True
        organisation = (
            self.organisation.to_dict(case=self.case, with_contacts=True)
            if self.organisation
            else {"id": ""}
        )
        out.update(
            {
                "organisation": organisation,
                "description": self.description,
                "contact": self.contact.to_embedded_dict(self.case) if self.contact else None,
                "review": self.review,
                "documents": self._prepare_documents(**kwargs),
                "url": self.url if self.url else None,
                "sent_by": self.sent_by.to_embedded_dict() if self.sent_by else None,
                "time_window": self.time_window,
                "archived": self.archived,
                "doc_reviewed_at": (
                    self.doc_reviewed_at.strftime(settings.API_DATETIME_FORMAT)
                    if self.doc_reviewed_at
                    else None
                ),
                "contacts": [_contact.to_embedded_dict() for _contact in self.contacts()],
                "versions": _previous_versions,  # all previous versions
                "previous_version": _previous_version,  # direct previous version
                "latest_version": _is_latest_version,
            }
        )
        return out

    def _to_embedded_dict(self, **kwargs):  # noqa
        downloaded_count = self.submissiondocument_set.filter(downloads__gt=0).count()
        out = self.to_minimal_dict()
        invitations = [
            {
                "id": invite.id,
                "name": str(invite),
                "invited_user_name": invite.contact.name if invite.contact else "",
                "deleted_at": invite.deleted_at,
            }
            for invite in self.invitations.all()
        ]
        out.update(
            {
                # how many documents were downloaded at least once
                "downloaded_count": downloaded_count,
                "is_new_submission": self._needs_review(),
                "locked": self.locked,
                "deficiency_sent_at": (
                    self.deficiency_sent_at.strftime(settings.API_DATETIME_FORMAT)
                    if self.deficiency_sent_at
                    else None
                ),
                "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
                "created_by": {
                    "id": str(self.created_by.id) if self.created_by else "",
                    "name": self.created_by.name if self.created_by else "",
                },
                "issued_by": self.issued_by.to_embedded_dict() if self.issued_by else None,
                "received_from": (
                    self.received_from.to_embedded_dict() if self.received_from else None
                ),
                "parent_id": str(self.parent_id) if self.parent_id else None,
                "deficiency_notice_params": self.deficiency_notice_params,
                "invitations": invitations,
            }
        )
        return out

    def to_minimal_dict(self, **kwargs):
        org_case_role = self.organisation_case_role()
        org_case_role_outer = self.organisation_case_role(True)
        created_by_tra = self.created_by.is_tra() if self.created_by is not None else True
        if self.organisation:  # noqa
            organisation = self.organisation.to_embedded_dict()
            organisation["companies_house_id"] = self.organisation.companies_house_id
            organisation["address"] = {
                "address": self.organisation.address,
                "post_code": self.organisation.post_code,
                "country": self.organisation.country.name,
            }
        else:
            organisation = {"id": ""}

        case_dict = self.case.to_minimal_dict()
        case_dict["initiated_at"] = (
            self.case.initiated_at.strftime(settings.API_DATETIME_FORMAT)
            if self.case.initiated_at
            else None
        )

        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type.to_dict(),
            "status": self.status.to_dict() if self.status else {},
            "case": case_dict,
            "version": self.version,
            "sent_at": (
                self.sent_at.strftime(settings.API_DATETIME_FORMAT) if self.sent_at else None
            ),
            "received_at": (
                self.received_at.strftime(settings.API_DATETIME_FORMAT)
                if self.received_at
                else None
            ),
            "due_at": self.due_at.strftime(settings.API_DATETIME_FORMAT) if self.due_at else None,
            "organisation": organisation,
            "organisation_name": self.organisation_name,
            "organisation_case_role": org_case_role.to_dict() if org_case_role else None,
            "organisation_case_role_outer": (
                org_case_role_outer.to_dict(self.case) if org_case_role_outer else None
            ),
            "is_tra": str(self.organisation and self.organisation.id) == TRA_ORGANISATION_ID,
            "tra_editable": created_by_tra or not (self.status and self.status.default),
            "issued_at": (
                self.issued_at.strftime(settings.API_DATETIME_FORMAT) if self.issued_at else None
            ),
            "last_modified": (
                self.last_modified.strftime(settings.API_DATETIME_FORMAT)
                if self.last_modified
                else None
            ),
            "locked": self.locked,
            "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
        }

    # single property dictionary methods
    @property
    def tra_editable(self):
        return self.created_by.is_tra() or not (self.status and self.status.default)

    def is_tra(self):
        return str(self.organisation and self.organisation.id) == TRA_ORGANISATION_ID

    def _dict_organisation(self):
        if self.organisation:  # noqa
            organisation = self.organisation.to_embedded_dict()
            organisation["companies_house_id"] = self.organisation.companies_house_id
            organisation["address"] = {
                "address": self.organisation.address,
                "post_code": self.organisation.post_code,
                "country": self.organisation.country.name,
            }
        else:
            organisation = {"id": ""}
        return organisation

    def _dict_organisation_case_role(self):
        org_case_role = self.organisation_case_role()
        return org_case_role and org_case_role.to_dict()

    def organisation_case_role_outer(self):
        org_case_role_outer = self.organisation_case_role(True)
        return org_case_role_outer and org_case_role_outer.to_dict()

    def set_due_date(self, force=False):
        """
        Sets the due_at attribute if not currently set and a time_window is assigned
        """
        try:
            if (force or not self.due_at) and self.time_window:
                self.due_at = timezone.now() + datetime.timedelta(days=int(self.time_window))
        except Exception:
            pass

    @property
    def issued_documents(self):
        try:
            return self.__issued_documents
        except AttributeError:
            self.__issued_documents = SubmissionDocument.objects.filter(
                submission=self, issued_at__isnull=False, document__confidential=False
            )
            return self.__issued_documents

    @staticmethod
    def document_exists(document):
        """
        Returns True if this document has any relationship to any other submission
        """
        return SubmissionDocument.objects.filter(document=document).exists()

    def notify_received(self, user, template_id=None):
        """
        Notify the contact associated with the user that the submission has been received.
        """
        template_id = template_id or self.status.send_confirmation_notification
        if template_id:
            context = {
                "full_name": self.contact.name.strip() if self.contact else "",
                "company_name": titlecase(self.organisation.name) if self.organisation else "",
                "case_number": self.case.reference,
                "case_name": self.case.name,
                "case_type": self.case.type.name,
                "submission_type": self.type.name,
            }
            self.notify(
                sent_by=user, contact=user.contact, context=context, template_id=template_id
            )

    def notify(self, sent_by, contact=None, context=None, template_id=None, new_status=None):
        """
        Notify the contact about this submission using the given template

        :param core.User sent_by: The user performing an action on the submission.
        :param contacts.Contact contact: An optional contact to be notified.
            Defaults to the submission's designated contact.
        :param dict context: An optional dictionary of parameters to be made
            available to the template.
        :param str template_id: An optional string representing the key of a
            Notify template in the System Parameters.
            Defaults to NOTIFY_QUESTIONNAIRE
        :param str new_status: An optional status that the submission will be
            moved to after sending the notification.
            This value should correspond to the property of the SubmissionType
            excluding the `_status` suffix eg:
                - `sent` -> self.type.sent_status
                - `received` -> self.type.received_status
            Defaults to None ie the submission status will not change.
        """
        contact = contact or self.contact
        template_id = template_id or "NOTIFY_QUESTIONNAIRE"
        if template_id == "NOTIFY_APPLICATION_SUCCESSFUL":
            template_id = "NOTIFY_APPLICATION_SUCCESSFUL_V2"
        notify_template_id = SystemParameter.get(template_id)
        export_sources = self.case.exportsource_set.filter(deleted_at__isnull=True)
        export_countries = [src.country.name for src in export_sources]
        product = self.case.product_set.first()
        case_name = self.case.name
        company_name = titlecase(self.organisation.name)
        values = {
            "company": self.organisation.name,
            "investigation_type": self.case.type.name,
            "product": product.name if product else "",
            "case_name": case_name,
            "case_number": self.case.reference,
            "case_type": self.case.type.name,
            "full_name": contact.name.strip() if contact else "N/A",
            "country": ", ".join(export_countries) if export_countries else "N/A",
            "organisation_name": company_name,
            "company_name": company_name,
            "login_url": public_login_url(),
            "submission_type": self.type.name,
            "deadline": self.due_at.strftime(settings.FRIENDLY_DATE_FORMAT) if self.due_at else "",
            "dumped_or_subsidised": self.case.dumped_or_subsidised(),
            "case_title": case_name,  # TODO: merge the two identicals
            "notice_url": self.case.latest_notice_of_initiation_url,  # TODO: remove
            "notice_of_initiation_url": self.case.latest_notice_of_initiation_url,
        }

        audit_kwargs = {
            "audit_type": AUDIT_TYPE_NOTIFY,
            "user": sent_by,
            "case": self.case,
            "model": contact,
        }
        send_mail(contact.email, values, notify_template_id, audit_kwargs=audit_kwargs)
        if new_status:
            self.status = getattr(self.type, f"{new_status}_status")
            if new_status == "sent":
                self.sent_at = timezone.now()
                self.set_due_date()
            self.save()

    def notify_deficiency(self, sent_by, contact=None, context=None, template_id=None):
        """
        Notify the contact about a deficiency to this submission using the given template.
        If no template is provided, the type's default is used falling
        back to the default deficiency template.
        """
        contact = contact or self.contact
        template_id = "NOTIFY_SUBMISSION_DEFICIENCY"
        if context.get("submission_type", "") == "Application":
            template_id = "NOTIFY_APPLICATION_INSUFFICIENT_V2"
        notify_template_id = SystemParameter.get(template_id)
        product = self.case.product_set.first()
        product_name = product.name if product else ""
        case_name = self.case.name
        company_name = titlecase(self.organisation.name)
        # set the due date on this submission
        self.set_due_date(force=True)
        values = {
            "company": company_name,
            "investigation_type": self.case.type.name,
            "product": product_name,
            "full_name": contact.name.strip() if contact else "N/A",
            "organisation_name": company_name,
            "case_number": self.case.reference,
            "case_name": case_name,
            "tra_contact_name": "us",
            "submission_type": self.type.name,
            "login_url": public_login_url(),
            "deadline": (
                self.due_at.strftime(settings.FRIENDLY_DATE_FORMAT) if self.due_at else "N/A"
            ),
        }
        if context:
            values.update(context)
        audit_kwargs = {
            "audit_type": AUDIT_TYPE_NOTIFY,
            "user": sent_by,
            "case": self.case,
            "model": contact,
        }
        send_mail(contact.email, values, notify_template_id, audit_kwargs=audit_kwargs)

        self.deficiency_sent_at = timezone.now()
        self.sent_at = timezone.now()
        self.save()

    @transaction.atomic
    def clone(self, created_by=None, deficient_document_ids=None):
        """
        Create a new version of this submission, linking it back to this parent
        and upping the version number.
        """

        from invitations.models import Invitation

        deficient_document_ids = map(str, deficient_document_ids) if deficient_document_ids else []
        created_by = created_by or self.created_by
        clone = Submission.objects.get(id=self.id)
        clone.id = None
        clone.deficiency_sent_at = None
        clone.sent_at = None
        clone.sent_by = None
        clone.created_by = created_by
        clone.created_at = timezone.now()
        clone.last_modified = None
        clone.modified_by = None
        clone.deleted_at = None
        clone.doc_reviewed_at = None
        clone.parent = self.parent or self  # all versions have the same parent
        clone.version += 1
        clone.due_at = None
        clone.time_window = None
        clone.received_from = None
        clone.received_at = None
        clone.review = None
        if clone.deficiency_notice_params:
            clone.load_attributes(clone.deficiency_notice_params)
        clone.deficiency_notice_params = None
        clone.set_due_date()
        clone.save()
        self.archived = True
        # Copy invites
        invites = Invitation.objects.filter(submission=self)
        for invite in invites:
            invite.id = invite.code = None
            invite.submission = clone
            invite.save()
        self.save()
        # copy all documents, except deficiency ones
        submission_documents = SubmissionDocument.objects.filter(submission=self).exclude(
            type__key="deficiency"
        )
        # clone document deficiency states
        for subdoc in submission_documents:
            subdoc.id = None
            subdoc.submission = clone
            if str(subdoc.document.id) in deficient_document_ids:
                subdoc.deficient = True
            subdoc.save()
        return clone

    def contacts(self):
        _contacts = []
        if self.organisation:
            _contacts = list(self.organisation.contacts)
        return _contacts

    @transaction.atomic
    def set_application_documents(self):
        """
        Based on the current case type, assign the application documents to this submission.
        This will reset existing application documents and should be applied against
        application submissions only.
        """
        document_templates = None
        if self.type.id == SUBMISSION_TYPE_APPLICATION:
            document_bundle = self.case.type.document_bundle
            if document_bundle:
                submission_document_type = SubmissionDocumentType.objects.get(
                    id=SUBMISSION_DOCUMENT_TYPE_TRA
                )
                document_templates = document_bundle.documents.all()
                self.submissiondocument_set.filter(type=submission_document_type).delete()
                for document in document_templates:
                    self.add_document(document=document, document_type=submission_document_type)
        return document_templates

    @transaction.atomic
    def set_case_documents(self, created_by):
        """
        Based on the submission type, if any case documents are to be applied
        on creation of a new submission, set them.
        """
        case_bundle = self.type.documentbundle_set.filter(case=self.case, status="LIVE").first()
        if not case_bundle:
            case_bundle = (
                self.type.documentbundle_set.filter(
                    case__isnull=True, case_type__isnull=True, status="LIVE"
                )
                .order_by("-version")
                .first()
            )
        case_documents = case_bundle.documents.all() if case_bundle else []
        submission_document_type = SubmissionDocumentType.objects.get(
            id=SUBMISSION_DOCUMENT_TYPE_TRA
        )
        for case_document in case_documents:
            self.add_document(
                document=case_document,
                document_type=submission_document_type,
                issued=False,
                issued_by=created_by,
            )

    def add_note(self, message, created_by=None):
        """
        add a note to this submission
        """
        note = Note(
            case=self.case,
            created_by=created_by,
            model_id=self.id,
            content_type=ContentType.objects.get_for_model(type(self)),
            user_context=created_by,
            data={"system": True},
            note=message,
        )
        note.save()
        return note

    def update_status(self, new_status: str, requesting_user: User) -> bool:
        """
        Updates the status of a submission object.

        Deals with sending any notifications that need to happen if a status is changed, and also
        updating any timestamp fields on the submission where necessary.

        Parameters
        ----------
        new_status : str - the new status, e.g. sent, received...etc.
        requesting_user : User - the user who is changing the status

        Returns
        -------
        bool
        """
        status_object = getattr(self.type, f"{new_status}_status")
        self.transition_status(status_object)

        # We want to update the status_at and status_by fields if applicable.
        # e.g. received_at and received_from
        if new_status == "received":
            self.received_at = timezone.now()
            self.received_from = requesting_user
            self.save()

        if new_status == "sent":
            self.sent_at = timezone.now()
            self.sent_by = requesting_user
            if self.time_window:
                self.due_at = timezone.now() + datetime.timedelta(days=self.time_window)
            self.save()

        # Now we want to send the relevant confirmation notification message if applicable.
        if status_object.send_confirmation_notification:
            submission_user = (
                self.contact.userprofile.user if self.contact and self.contact.has_user else None
            )
            self.notify_received(user=submission_user or requesting_user)

        return True
