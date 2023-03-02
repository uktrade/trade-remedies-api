import logging
import datetime

from dateutil.relativedelta import relativedelta
from django.db import models, transaction
from django.db.models import Q, OuterRef, Exists, QuerySet
from django.conf import settings
from django.utils import timezone
from dateutil.parser import parse
from audit.utils import audit_log
from audit import (
    AUDIT_TYPE_EVENT,
    AUDIT_TYPE_NOTIFY,
    AUDIT_TYPE_DELETE,
)
from core.utils import public_login_url
from core.tasks import send_mail
from security.constants import (
    SECURITY_GROUPS_TRA_ADMINS,
    SECURITY_GROUPS_TRA_TOP_LEVEL,
    SECURITY_GROUPS_TRA,
    ROLE_AWAITING_APPROVAL,
    ROLE_APPLICANT,
)
from cases.constants import (
    CASE_TYPE_ANTI_DUMPING,
    CASE_TYPE_SAFEGUARDING,
    CASE_TYPE_ANTI_SUBSIDY,
    ALL_COUNTRY_CASE_TYPES,
    DIRECTION_TRA_TO_PUBLIC,
    DIRECTION_PUBLIC_TO_TRA,
    SUBMISSION_TYPE_APPLICATION,
    SUBMISSION_TYPE_NOTICE_OF_INITIATION,
    SUBMISSION_APPLICATION_TYPES,
    DECISION_TO_INITIATE_KEY,
    EVIDENCE_OF_SUBSIDY_KEY,
    CASE_MILESTONE_DATES,
)
from security.models import (
    OrganisationCaseRole,
    UserCase,
    CaseRole,
    get_role,
)
from security.exceptions import InvalidAccess
from organisations.models import Organisation, get_organisation
from contacts.models import Contact
from core.base import BaseModel
from core.models import SystemParameter
from .casetype import CaseType
from .casestage import CaseStage
from .submission import SubmissionType, Submission
from .submissiondocument import SubmissionDocumentType
from .workflow import CaseWorkflow, CaseWorkflowState

logger = logging.getLogger(__name__)


class CaseOrNotice:
    """An object that has many of the same qualities as a Case but may not be one.

    Used to provide shared functionality to both Notice and Case models without duplicating
    code. Notices share many of the same qualities as a Case, but they do not exist on the TRS system as they were
    created before it was in use.
    """

    def filter_available_review_types(self, milestones: dict, reviews: QuerySet) -> list:
        """Filters through a list of all possible review types to find those which actually apply to this case, based on
        the criteria defined in the review type itself.

        Args:
        milestones: A dictionary of milestones that this object has passed: {milestone_name: date_of_completion}
        reviews: A list of all possible review types (CaseType objects).

        Returns:
            A list of possible reviews for this object after its milestones have been taken into account.
        """
        now = datetime.date.today()
        available_reviews = []

        for review_type in reviews:
            status = "ok"
            review_dict = review_type.to_dict()
            criteria = review_type.meta.get("criteria", [])
            start_date = None
            end_date = None
            for test in criteria:
                criterion = test["criterion"]
                if criterion in ["before", "after"]:
                    # This is a date test, we want to check if a review type can appear based on how far before or after
                    # a particular milestone it currently is - now()
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
                elif criterion == "state_value":
                    # Some review types are only allowed on cases which have reached a certain point in their worflow
                    state_value = self.get_state_key(key=test["key"])
                    if state_value != "pass" and (
                        not state_value or state_value.value != test["value"]
                    ):
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
                available_reviews.append(review_dict)
        return available_reviews

    @property
    def type(self):
        raise NotImplementedError()

    def available_case_review_types(self):  # noqa:C901
        """Return all available review types available for this case.

        These are based on the milestone dates associated with it and the case type criteria.
        Returns a tuple of two lists. The first element contains the available review type models,
        and the second is a list of dicts for all review types, with enhanced properties
        related to the review availability durations.
        """
        milestones = self.case_milestone_index()
        reviews = self.get_reviews()
        return self.filter_available_review_types(milestones, reviews)

    def case_milestone_index(self):
        """Should return a dictionary of all milestones this case-like object has completed"""
        raise NotImplementedError()

    def get_state_key(self, key: str):
        """Should return a WorkFlowState object belong to this object if one matching the key parameter can be found.
        if none can be found, return None"""
        raise NotImplementedError()

    def get_reviews(self):
        """Return all possible review types.

        All review types are case types, but not all case types are review types. This filters CaseType objects to
        those who have been explicitly marked as reviews in their meta {} field"""
        return CaseType.objects.filter(meta__review=True)


class CaseManager(models.Manager):
    def get_case(self, id, requested_by=None):
        """
        Load a case with all related immediate data
        """
        _case = self.select_related("stage", "type", "archive_reason", "created_by").get(id=id)
        if requested_by:
            _case.set_user_context([requested_by])
        return _case

    @transaction.atomic
    def create_new_case(self, user, organisation_name=None, **kwargs):
        """
        Create a new organisation, case, Application submission and relevant
        records.
        returns a tuple of the organisation, case and submission.
        Only the organisation name is required but some parameters can be provided
        in kwargs to override defaults.
        If there is only one workflow template in the database, attach it to the case now.
        Normally if there are multiple workflows the user will have to select which one to use
        at a later time.
        """
        role = kwargs.get("organisation_role_id") or ROLE_APPLICANT
        submission_type_id = kwargs.get("submission_type_id") or SUBMISSION_TYPE_APPLICATION
        case_type_id = kwargs.get("case_type_id") or CASE_TYPE_ANTI_DUMPING
        contact_name = kwargs.get("contact_name")
        organisation_id = kwargs.get("organisation_id")
        ex_oficio = kwargs.get("ex_oficio")
        case_type = CaseType.objects.get(id=int(case_type_id))
        submission_type = SubmissionType.objects.get(id=int(submission_type_id))
        if organisation_id:
            organisation = Organisation.objects.filter(id=organisation_id).first()
        else:
            organisation = Organisation.objects.create_or_update_organisation(
                user=user,
                name=organisation_name,
                trade_association=kwargs.get("trade_association") or False,
                address=kwargs.get("organisation_address"),
                post_code=kwargs.get("organisation_post_code"),
                assign_user=False,
                gov_body=bool(ex_oficio),
                **kwargs,
            )
        # get a contact to associate with the application
        if contact_name:
            contact_email = kwargs.get("contact_email", "").lower()
            contact = Contact.objects.create(
                organisation=organisation,
                name=contact_name,
                email=contact_email,
                phone=kwargs.get("contact_phone"),
                address=kwargs.get("contact_address"),
                created_by=user,
                user_context=user,
            )
        else:
            contact = user.contact
            contact.set_user_context(user)
        case_created_stage = CaseStage.objects.filter(key="CASE_CREATED").first()
        case = Case.objects.create(
            name=kwargs.get("case_name", kwargs.get("product_name")),
            created_by=user,
            type=case_type,
            stage=case_created_stage,
            user_context=[user],
        )
        # Assign the user to the case
        case.assign_user(user, user, organisation=organisation, relax_security=True)
        # Assign the contact as primary, for the applied-for organisation
        contact.set_primary(case=case, organisation=organisation)
        # Associate the organisation to the case for a specific role (applicant)
        org_case, created = OrganisationCaseRole.objects.assign_organisation_case_role(
            organisation=organisation,
            case=case,
            role=role,
            sampled=True,
            created_by=user,
            approved_by=user,
            approved_at=timezone.now(),
        )
        submission = Submission.objects.create(
            type=submission_type,
            status=submission_type.default_status,
            case=case,
            organisation=organisation,
            contact=contact,
            created_by=user,
        )
        # set initial application documents
        submission.set_application_documents()
        # handle workflow
        CaseWorkflow.objects.snapshot_from_template(case, case.type.workflow, requested_by=user)
        # Generate audit entry
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=user,
            model=case,
            case=case,
            milestone=True,
            data={"message": "Case Created"},
        )
        return organisation, case, submission

    def user_cases(
        self,
        user,
        organisation=None,
        organisation_role=None,
        current=None,
        exclude_organisation_case_role=False,
    ):
        """
        Return all user cases or cases relating to a specific organisation.
        A user can see all cases if they have Owner access for the organisation,
        or are explicitly assigned to the case.
        Optionally when organisation_role is provided, returns all cases where the organisation's
        role is the provided organisation_role
        :param user: User instance
        :param organisation: Organisation instance
        :param organisation_role: CaseRole instance or name
        :param exclude_organisation_case_role: CaseRole instance or name - will exclude cases where the organisation has this role
        """

        if user.is_tra() and not organisation:
            # TODO: Temporarily return all cases for TRA case workers
            cases = self.investigator_cases(user=user, current=current)
        else:
            cases = self.filter(deleted_at__isnull=True, usercase__user=user)
            if organisation_role:
                cases = cases.filter(organisationcaserole__role=get_role(organisation_role))
            if exclude_organisation_case_role:
                cases = cases.exclude(
                    organisationcaserole__role=get_role(exclude_organisation_case_role)
                )
        if current is not None:
            cases = cases.filter(archived_at__isnull=current)
        cases = cases.select_related("type", "stage", "created_by", "archive_reason")
        cases = cases.order_by("sequence")
        return cases

    def all_user_cases(self, user, archived=None, all_cases=False, **kwargs):
        """
        Retrieve all cases for a user across all organisations.
        All users have explicit access to cases.
        If 'archived' is set, either only current or only archived cases will be returned.
        """
        filters = {}
        if user.is_tra():
            cases = self.investigator_cases(user=user, current=not archived)
            return list(cases)
        filters["user"] = user
        if archived is not None:
            filters["case__archived_at__isnull"] = not bool(archived)
        if all_cases and not user.has_perm("core.can_view_all_org_cases"):
            all_cases = False
        elif all_cases:
            user_filter = {"user__in": user.organisation_users}
        case_set = set([])
        user_cases = UserCase.objects.filter(
            case__deleted_at__isnull=True, **filters
        ).select_related(
            "case", "case__stage", "case__created_by", "case__archive_reason", "case__workflow"
        )
        for user_case in user_cases:
            org_role = (
                user_case.case.organisationcaserole_set.filter(organisation=user_case.organisation)
                .select_related("role", "organisation", "case")
                .first()
            )
            if org_role and org_role.approved_at:
                user_case.case.set_organisation_context(org_role.organisation)
                user_case.case.set_user_context([user])
                user_case.case.set_caserole_context(org_role)
                case_set.add(user_case.case)
        return list(case_set)

    def outer_user_cases(self, user, current=True):
        """
        Retrieve all cases for a given organisation, including those no directly associated,
        but connected through a third-party representation.
        """
        user_filter = {"user__in": user.organisation_users}
        user_cases = UserCase.objects.filter(
            case__deleted_at__isnull=True, case__archived_at__isnull=bool(current), **user_filter
        ).select_related(
            "case",
            "case__stage",
            "case__created_by",
            "case__archive_reason",
            "case__workflow",
            "organisation",
        )
        return user_cases

    def investigator_cases(self, user=None, current=None, exclude_partially_created=True):
        """
        Return a case queryset for an investigator

        :param core.User user: The user performing the request.
        :param bool current: If False, only archived cases will be returned.
            If True, only non-archived cases will be returned.
            If None, both archived and non-archived cases are returned.
        :param bool exclude_partially_created: If True, cases that have
            yet to be fully created will be excluded from the results.
            If False, partially created cases will be included.
        """
        _kwargs = {}
        if user and not user.is_tra(with_role=SECURITY_GROUPS_TRA_TOP_LEVEL):
            _kwargs["usercase__user"] = user
        if current is not None:
            _kwargs["archived_at__isnull"] = current
        cases = (
            Case.objects.filter(deleted_at__isnull=True, **_kwargs)
            .select_related("type", "stage", "created_by", "archive_reason", "workflow")
            .order_by("sequence")
        )

        if exclude_partially_created:
            cases = (
                cases.filter(
                    product__isnull=False,
                    organisationcaserole__isnull=False,
                )
                .exclude(Q(exportsource__isnull=True) & ~Q(type__in=ALL_COUNTRY_CASE_TYPES))
                .distinct()
            )
        return cases

    def public_cases(self):
        """
        Return all publicly available cases.
        Only initiated cases are returned.
        """
        return self.filter(
            deleted_at__isnull=True, archived_at__isnull=True, initiated_at__isnull=False
        ).order_by("sequence", "created_at")

    def available_for_regisration_of_intestest(self, requested_by=None):
        """
        Return available cases for registration of interest.
        Excludes case types marked as exclude_for_interest in their meta field.
        """
        roi_open = CaseWorkflowState.objects.filter(
            case=OuterRef("pk"),
            key="REGISTRATION_OF_INTEREST_TIMER",
            value=True,
            case__type__meta__exclude_for_interest__isnull=True,
        ).values("id", "case_id")
        public_cases = self.public_cases()
        # if requested_by:
        #     public_cases = public_cases.exclude(created_by=requested_by)
        return public_cases.annotate(roi_open=Exists(roi_open)).filter(roi_open=True).distinct()


class Case(BaseModel, CaseOrNotice):
    sequence = models.IntegerField(null=True, blank=True, unique=True)
    initiated_sequence = models.IntegerField(null=True, blank=True, unique=True)
    type = models.ForeignKey(CaseType, null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=250, null=True, blank=True)
    stage = models.ForeignKey(CaseStage, null=True, blank=True, on_delete=models.PROTECT)
    initiated_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    archive_reason = models.ForeignKey(
        "cases.ArchiveReason", null=True, blank=True, on_delete=models.PROTECT
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    notice = models.ForeignKey("cases.Notice", null=True, blank=True, on_delete=models.PROTECT)

    objects = CaseManager()

    class Meta:
        permissions = (
            ("create_ex_oficio", "Can create an ex-oficio case"),
            (
                "complete_decision_tasks",
                "Can complete decision tasks like initiation decision, final determination etc.",
            ),
            ("can_assign_team", "Can assign manager and team to the case"),
            (
                "issue_submission_requests",
                "Can issue submission requests (questionnaires, visit report etc.)",
            ),
            ("workflow_editor", "Can access the workflow editor"),
            ("can_generate_audit", "Can generate full audit trail"),
        )

    def __str__(self):
        return f"{self.sequence}: {self.name}"

    def get_next_sequence(self):
        current_sequence = Case.objects.aggregate(sequence=models.Max("sequence"))
        return (current_sequence.get("sequence") or 0) + 1

    def get_next_initiated_sequence(self):
        current_sequence = Case.objects.filter(initiated_sequence__isnull=False).aggregate(
            sequence=models.Max("initiated_sequence")
        )
        return (current_sequence.get("sequence") or 0) + 1

    def set_organisation_context(self, organisation):
        self._organisation = organisation

    def set_caserole_context(self, caserole):
        self._caserole = caserole

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Override save to create the initial sequence number on creation
        """
        if not self.created_at:
            self.sequence = self.get_next_sequence()
        if not self.name:
            self.name = "New application"
        if self.initiated_at and not self.initiated_sequence:
            self.initiated_sequence = self.get_next_initiated_sequence()
        return super().save(*args, **kwargs)

    @property
    def decision_to_initiate(self):
        """
        Return True if there was a decision to initiate this case.
        The decision is stored, as part of the workflow, in the case workflow state store.
        """
        try:
            cws = CaseWorkflowState.objects.get(
                case=self, key=DECISION_TO_INITIATE_KEY, deleted_at__isnull=True
            )
            return cws.value == "yes"
        except CaseWorkflowState.DoesNotExist:
            return False

    @property
    def evidence_of_subsidy(self):
        try:
            cws = CaseWorkflowState.objects.get(
                case=self, key=EVIDENCE_OF_SUBSIDY_KEY, deleted_at__isnull=True
            )
            return cws.value
        except CaseWorkflowState.DoesNotExist:
            return "unknown"

    @evidence_of_subsidy.setter
    def evidence_of_subsidy(self, value):
        cws, created = CaseWorkflowState.objects.get_or_create(
            case=self, key=EVIDENCE_OF_SUBSIDY_KEY, deleted_at=None
        )
        cws.value = value
        cws.save()
        return cws.value

    @property
    def latest_notice_of_initiation_url(self):
        if not hasattr(self, "_latest_noi_url"):
            self._latest_noi_url = "N/A"
            sub = (
                self.submission_set.filter(type__id=SUBMISSION_TYPE_NOTICE_OF_INITIATION)
                .order_by("-created_at")
                .first()
            )
            if sub:
                self._latest_noi_url = (
                    sub.url
                    or f"{settings.PUBLIC_ROOT_URL}/public/case/{self.reference}/submission/{sub.id}/"  # noqa: E501
                )
        return self._latest_noi_url

    @property
    def public_case_file_url(self):
        if self.initiated_sequence:
            return f"{settings.PUBLIC_ROOT_URL}/public/case/{self.reference}/"
        else:
            return "N/A"

    @property
    def reference(self):
        """
        Return the actual reference for this case.
        Uninitiated cases return the sequence (application number).
        Initiated cases return the case type acronym followed by the initiated_sequence number
        """
        if self.initiated_sequence:
            return f"{self.type.acronym}{self.initiated_sequence:04}"
        return f"{self.sequence:04}"

    def set_stage_by_key(self, stage_key):
        """
        Set the case stage by a given stage key
        """
        try:
            stage = CaseStage.objects.get(key=stage_key)
            return self.set_stage(stage)
        except CaseStage.DoesNotExist:
            return None

    def set_stage(self, stage, ignore_flow=False):
        """
        Set the stage of the case, accounting for restricted flow restrictions.
        # TODO: Note optional refactor:
        flow_restrict
            - False: Ignore flow restriction completely. all stages are ok.
            - True: Force flow restriction regardless of configuration
            - None: Adhere to flow restriction as configured in stages.
        """
        last_restricted_stage = self.last_flow_restricted_stage()

        if not ignore_flow and last_restricted_stage and stage.order < last_restricted_stage.order:
            return

        if self.stage != stage:
            self.stage = stage
            self.save()

        if stage.flow_restrict:
            state, _ = CaseWorkflowState.objects.get_or_create(
                case=self, key="LAST_RESTRICTED_FLOW_STAGE_ID"
            )
            state.value = str(stage.id)
            state.save()

        return stage

    def get_status(self):
        """Return a status dict for this case

        Returns:
            dict -- dict detailing the current stage, action ane notice of the case
        """
        status = {
            "stage": self.stage.name if self.stage else None,
            "next_action": None,
            "next_action_due": None,
            "next_notice": None,
            "next_notice_due": None,
        }
        keys = {"CURRENT_ACTION": "next_action", "NEXT_NOTICE": "next_notice"}
        _value_index = CaseWorkflowState.objects.value_index(case=self, keys=list(keys))
        _action_index = CaseWorkflowState.objects.value_index(
            case=self, keys=[v[0] for k, v in _value_index.items()]
        )
        workflow = self.workflow.as_workflow()
        workflow_key_index = workflow.key_index
        for key, name in keys.items():
            _value = _value_index.get(key, [None, None])[0]
            if not _value:
                continue
            action_node = workflow_key_index.get(_value)
            status[name] = action_node.get("label") if action_node else None
            action_due_date = _action_index.get(_value, [None, None])[1]
            if action_due_date:  # action_obj and action_obj.due_date:
                status[f"{name}_due"] = action_due_date.strftime(settings.API_DATETIME_FORMAT)
        return status

    def reset_initiation_decision(self):
        """
        Reset any workflow keys related to initiation decision.
        This call is allowed to fail
        """
        try:
            workflow = self.workflow
            workflow_tree = workflow.as_workflow()
            workflow_tree.key_index["CLOSE_APPEAL"]["active"] = True
            workflow_tree.key_index["CLOSE_CASE"]["active"] = True
            workflow_tree.key_index["CLOSE_REJECT"]["active"] = True
            workflow_tree.key_index[DECISION_TO_INITIATE_KEY]["active"] = True
            workflow.workflow = workflow_tree
            workflow.save()
        except Exception:
            pass

    @property
    def users(self):
        """
        Return all users associated with this case
        """
        return UserCase.objects.filter(case=self)

    def organisation_users(self, organisation):
        """Return all users of a particular organisation assigned to this case

        Arguments:
            organisation {Organisation} -- Organisation model
        """
        return UserCase.objects.filter(case=self, user__organisationuser__organisation=organisation)

    def has_organisation(self, organisation, role=None):
        """
        Returns True if the organisation is a participant of this case.
        If a role is provided also check if organisation has the requested role
        :param organisation: An organisation instance
        :param role: Optional CaseRole instance or name
        """
        return OrganisationCaseRole.objects.has_organisation_case_role(
            organisation, self, role=role
        )

    def assign_organisation_user(self, user, organisation):
        """
        Assign an organisation user to this case explicitly.
        Validates that the user's organisation is a participant in the case
        """
        if not self.has_organisation(organisation):
            raise InvalidAccess(f"User {user}'s organisation is not a participant of this case")
        user_case, created = UserCase.objects.get_or_create(
            user=user, case=self, organisation=organisation
        )
        return True

    @property
    def registration_deadline(self):
        """Return the case's registration deadline date or None if not yet initiated.
        The date is calculated as n days (defined in setttings.CASE_REGISTRATION_DURATION)
        added to the initiation date.

        Returns:
            [datetime] -- [Registration deadline date or None]
        """
        return (
            self.initiated_at + datetime.timedelta(days=settings.CASE_REGISTRATION_DURATION)
            if self.initiated_at
            else None
        )

    def _to_dict(self, organisation=None, user=None, with_submissions=False):
        """
        A dict representation of this model
        """
        if hasattr(self, "_organisation") and not organisation:
            organisation = self._organisation
        if not user and self.user_context:
            user = self.user_context.user
        manager = self.manager
        product = self.product_set.filter().first()
        _sources = self.exportsource_set.filter(deleted_at__isnull=True)
        _applicant = self.applicant
        _dict = self.to_embedded_dict(organisation=organisation, user=user)
        _dict.update(
            {
                "initiated_sequence": self.initiated_sequence,
                "decision_to_initiate": self.decision_to_initiate,
                "evidence_of_subsidy": self.evidence_of_subsidy,
                "notice_of_initiation_url": self.latest_notice_of_initiation_url,
                "submitted_at": self.submitted_at.strftime(settings.API_DATETIME_FORMAT)
                if self.submitted_at
                else None,
                "participant_count": self.participant_count,
                "manager": manager.user.to_embedded_dict() if manager else {},
                "product": product.to_dict() if product else {},
                "sources": [source.to_dict() for source in _sources],
                # 'public_invite': self.public_invite.to_dict(),  TODO: Temporary disabling this
                "user_organisations": [],
                "submissions": [],
                "submission_count": None,
                "parent": self.parent.to_minimal_dict() if self.parent else None,
                "type": self.type.to_dict(),
                "notice": self.notice.to_embedded_dict() if self.notice else None,
            }
        )

        if self.archived_at:
            _dict["archived_at"] = self.archived_at.strftime(settings.API_DATETIME_FORMAT)
            _dict["archive_reason"] = self.archive_reason.to_dict() if self.archive_reason else None

        if _applicant:
            _dict["applicant"] = _applicant.to_dict(case=self)
        if organisation:
            _dict["organisation"] = organisation.to_dict()
            _dict["organisation_users"] = [
                ousr.to_embedded_dict() for ousr in self.organisation_users(organisation)
            ]
            submissions = self.organisation_submissions(organisation)
        else:
            _dict["organisation"] = _applicant.to_dict() if _applicant else None
            submissions = self.submissions
        if with_submissions:
            _dict["submissions"] = [submission.to_embedded_dict() for submission in submissions]
            _dict["submission_count"] = len(submissions)
        else:
            _dict["submission_count"] = self.submission_count  # submissions.count()
        if user:
            _dict["user_organisations"] = self.get_user_organisation_state(user)
        return _dict

    # @method_cache
    def _to_embedded_dict(self, organisation=None, user=None, is_primary_contact=False):
        if hasattr(self, "_organisation") and not organisation:
            organisation = self._organisation
        if not user and self.user_context:
            user = self.user_context.user
        _applicant = self.applicant
        _applicant_dict = _applicant and _applicant.organisation.to_embedded_dict()
        _dict = self.to_minimal_dict()
        _dict.update(
            {
                "type": self.type.to_embedded_dict(),
                "stage": self.stage.to_embedded_dict() if self.stage else None,
                "archived_at": self.archived_at.strftime(settings.API_DATETIME_FORMAT)
                if self.archived_at
                else None,
                "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT)
                if self.created_at
                else None,
                "user_organisations": [],
                "initiated_at": self.initiated_at.strftime(settings.API_DATETIME_FORMAT)
                if self.initiated_at
                else None,
                "registration_deadline": self.registration_deadline,
                "case_status": self.get_status(),
                "organisation": organisation.to_dict() if organisation else _applicant_dict,
            }
        )
        if hasattr(self, "_caserole"):
            _dict["caserole"] = self._caserole.to_embedded_dict()
        if user and not user.is_tra():
            _dict["user_organisations"] = self.get_user_organisation_state(user)
            if is_primary_contact:
                _dict["primary"] = self.casecontact_set.filter(
                    contact=user.contact, primary=True
                ).exists()
        return _dict

    def _to_minimal_dict(self, attrs=None):
        _dict = {
            "id": str(self.id),
            "name": self.name,
            "reference": self.reference,
        }
        if attrs and "initiated_at" in attrs:
            _dict["initiated_at"] = (
                self.initiated_at.strftime(settings.API_DATETIME_FORMAT)
                if self.initiated_at
                else None
            )

        return _dict

    def dumped_or_subsidised(self):
        """
        Returns whether this case is about dumped or subsidised goods.
        Returns a string 'dumped' or 'subsidised'. If neither, returns an empty string.
        Note: This is naive test checking if the word dump or sub appear in the case type.
        """
        if "dump" in self.type.name:
            return "dumped"
        elif "sub" in self.type.name:
            return "subsidised"
        return ""

    def get_user_organisation_state(self, user):
        user_organisations = []
        for org in self.user_organisations(user):
            org_dict = org.to_embedded_dict()
            org_dict["org_state"] = self.organisation_submissions_state(organisation=org)
            user_organisations.append(org_dict)
        return user_organisations

    @property
    def public_invite(self):
        """
        Note: This is potentially deprecated as all cases are public after initiation and
        invites are more explicitly made by customer or TRA
        """
        from invitations.models import Invitation

        try:
            invite = self.invitations.get(contact__isnull=True, organisation__isnull=True)
        except Invitation.DoesNotExist:
            invite = Invitation.objects.create(
                case=self, case_role=CaseRole.objects.get(id=ROLE_AWAITING_APPROVAL)
            )
        return invite

    @property
    def team(self):
        return self.usercase_set.select_related(
            "user",
            "user__userprofile",
            "organisation",
        ).filter(user__groups__name__in=SECURITY_GROUPS_TRA)

    @property
    def manager(self):
        """
        Return the manager assigned to this case.
        """
        manager = self.usercase_set.select_related("user").filter(
            user__groups__name__in=SECURITY_GROUPS_TRA_ADMINS
        )
        return manager.first()

    @property
    def applicant(self):
        # TODO handle multiple applications ?
        if not hasattr(self, "_applicant"):
            self._applicant = None
            application = (
                self.submissions.select_related(
                    "organisation",
                )
                .filter(type__id__in=SUBMISSION_APPLICATION_TYPES)
                .first()
            )
            if application:
                self._applicant = (
                    self.organisationcaserole_set.select_related("organisation", "role")
                    .filter(organisation=application.organisation)
                    .first()
                )
                # Commented out - see TR-2046.
                # use the name of the company when the submission was made
                # self._applicant.organisation.name = application.organisation_name
            if self.applicant:
                self._applicant.organisation.set_case_context(self.case_context)
        return self._applicant

    def get_participants_by_role(self, role):
        return self.organisationcaserole_set.select_related(
            "organisation",
            "role",
        ).filter(role=get_role(role))

    def participants(self, fields=None):
        if not hasattr(self, "_participants"):
            roles = CaseRole.objects.exclude(key="preparing").order_by("order")
            self._participants = {}
            for role in roles:
                self._participants[role.key] = {
                    "case_role_id": role.id,
                    "order": role.order,
                    "allow_cw_create": role.allow_cw_create,
                    "parties": [
                        party.to_dict(case=self, fields=fields)
                        for party in self.get_participants_by_role(role.id)
                    ],
                }
        return self._participants

    @property
    def participant_count(self):
        return self.organisationcaserole_set.exclude(role__key="preparing").count()

    @property
    def case_status(self):
        return self.get_status()

    @property
    def submissions(self):
        """
        Return all submissions for this case
        """
        if not hasattr(self, "_submissions"):
            self._submissions = self.submission_set.filter(archived=False).order_by("created_at")
        return self._submissions

    @property
    def submission_count(self):
        """
        Return the count of all non default submissions or applications in draft
        """
        if not hasattr(self, "_submission_count"):
            self._submission_count = (
                self.submission_set.filter(
                    archived=False,
                    status__sent=False,
                    status__draft=False,
                )
                .filter(
                    Q(type__direction=DIRECTION_TRA_TO_PUBLIC)
                    | Q(type__direction=DIRECTION_PUBLIC_TO_TRA)
                )
                .filter(Q(type__in=SUBMISSION_APPLICATION_TYPES) | Q(status__default=False))
                .count()
            )
        return self._submission_count

    @property
    def application(self):
        return self.submission_set.filter(type_id__in=SUBMISSION_APPLICATION_TYPES).first()

    @property
    def product(self):
        return self.product_set.filter().first()

    @property
    def sources(self):
        _sources = self.exportsource_set.filter(deleted_at__isnull=True)
        return [source.to_dict() for source in _sources]

    def organisation_submissions(self, organisation):
        """
        Return all submissions from an organisation in this case
        """
        return self.submission_set.filter(organisation=organisation).order_by("created_at")

    def organisation_submissions_state(self, organisation):
        # We flag all submissions that sent by the TRA and are not locked -
        # because the customer has to do some more work on them
        org_subs = (
            self.submission_set.filter(
                organisation=organisation,
                deleted_at__isnull=True,
                status__locking=False,
                status__default=False,
            )
            .filter(
                Q(status__sent=True)
                | Q(status__version=True)
                | Q(status__draft=True)  # sadly, this is our only way to detect deficiency notices
            )
            .filter(Q(archived=False))
            .filter(Q(type__direction=DIRECTION_TRA_TO_PUBLIC) | Q(due_at__isnull=False))
            .order_by("due_at")
        )
        count = org_subs.count()
        earliest = org_subs.first()
        return {"submission_count": count, "due_at": earliest.due_at if earliest else None}

    def assign_user(
        self, user, created_by, organisation=None, relax_security=False, confirmed=True
    ):
        """
        Assign a TRA user (team member) to the case.
        """
        if relax_security or created_by.is_tra():
            # Inactive users should be unassigned from case for security purposes
            for usercase in UserCase.objects.filter(case=self, organisation=organisation):
                if not usercase.user.is_active:
                    usercase.delete()
            if user.is_active:
                try:
                    user_case = UserCase.objects.get(
                        user=user, case=self, organisation=organisation
                    )
                except UserCase.DoesNotExist:
                    user_case = UserCase.objects.create(
                        created_by=created_by,
                        user=user,
                        case=self,
                        organisation=organisation,
                        user_context=[created_by],
                    )
                return user_case
        else:
            raise InvalidAccess("Denied: Only TRA users can assign case team members")

    def confirm_user_case(self, user, created_by, organisation):
        """
        Sets the confirm flag on this user-case-org object
        """
        user_case = UserCase.objects.get(user=user, case=self, organisation=organisation)
        user_case.confirmed = True
        user_case.confirmed_at = timezone.now()
        user_case.confirmed_by = created_by
        user_case.save()

    def user_organisations(self, user):
        user_cases = self.usercase_set.filter(user=user)
        organisations = [
            user_case.organisation for user_case in user_cases if user_case.organisation
        ]
        return organisations

    def create_submission_for_documents(
        self, documents, submission_type, created_by, name=None, organisation=None, issued=False
    ):
        """
        Create a subimssion around a document so that it becomes part of the case.
        By defualt the document will not be issued yet to the case until explicitly done so.
        """
        from cases.models.utils import get_submission_type

        submission_type = get_submission_type(submission_type)
        organisation = get_organisation(organisation) if organisation else None
        status_kwargs = {}
        # if this is a global submission, lock it down
        if not organisation:
            status_kwargs["status"] = submission_type.sent_status
        submission = Submission.objects.create(
            created_by=created_by,
            case=self,
            name=name or submission_type.name,
            organisation=organisation,
            type=submission_type,
            **status_kwargs,
        )
        submission_document_type = SubmissionDocumentType.type_by_user(created_by)
        for document in documents:
            submission.add_document(
                document=document,
                document_type=submission_document_type,
                issued=issued,
                issued_by=created_by,
            )
        return submission

    @transaction.atomic
    def remove_user(self, user, created_by, relax_security=False, organisation_id=None):
        """
        Remove a user (team member) from the case.
        If organisation id is provided, only the association to the case for this organisation will
        be removed. Otherwise, all associations will be removed.
        """
        if created_by.is_tra(manager=True) or relax_security:
            user_cases = UserCase.objects.filter(user=user, case=self)
            if organisation_id:
                user_cases = user_cases.filter(organisation__id=organisation_id)
            for user_case in user_cases:
                user_case.delete()
                audit_log(
                    audit_type=AUDIT_TYPE_DELETE,
                    user=created_by,
                    case=self,
                    data={
                        "message": f"User {user} removed from case {self}, "
                        f"representing {user_case.organisation.name}"
                    },
                )
            return True
        else:
            raise InvalidAccess("Denied: Only TRA users can remove case team members")

    def derive_case_name(self):
        from . import Product

        try:
            name = []
            try:
                product = self.product_set.get()
            except Product.DoesNotExist:
                name.append("N/A")
            else:
                name.append(product.name)
            first_export_country = self.exportsource_set.all().order_by("created_at").first()
            if first_export_country:
                name.append("from")
                name.append(first_export_country.country.name)
            return " ".join(name)
        except Exception as exc:
            logger.error("Error deriving case name", exc_info=True)
            return None

    def notify_all_participants(
        self, sent_by, submission=None, organisation_id=None, template_name=None, extra_context=None
    ):
        template_name = template_name or "NOTIFY_UPDATE_TO_CASE"
        notify_template_id = SystemParameter.get(template_name)

        context = {
            "case_name": self.name,
            "case_number": self.reference,
            "case_type": self.type.name,
            "login_url": public_login_url(),
            "public_file": self.public_case_file_url,
            "notice_type": "",
            "notice_of_initiation_url": "",
            "submission_request_name": "",
            "submission_type": "",
            "submission_name": "",
            "actors_full_name": sent_by.name,
        }

        if submission:
            context["notice_type"] = submission.type.name
            context["notice_of_initiation_url"] = submission.case.latest_notice_of_initiation_url
            context["submission_request_name"] = submission.name
            context["submission_type"] = submission.type.name
            context["submission_name"] = submission.name

        if extra_context:
            context.update(extra_context)

        user_cases = (
            self.usercase_set.select_related("user", "user__userprofile__contact", "organisation")
            .filter(organisation__organisationcaserole__case=self)
            .exclude(organisation__organisationcaserole__role__key="rejected")
        )

        if organisation_id:
            user_cases = user_cases.filter(organisation=organisation_id)

        for user_case in user_cases:
            contact = user_case.user.contact
            organisation = user_case.organisation
            _user_contact = context.copy()
            _user_contact["full_name"] = contact.name.strip()
            _user_contact["company_name"] = organisation.name if organisation else ""
            audit_kwargs = {
                "audit_type": AUDIT_TYPE_NOTIFY,
                "case": self,
                "user": sent_by,
                "model": contact,
            }
            send_mail(
                email=contact.email,
                context=_user_contact,
                template_id=notify_template_id,
                audit_kwargs=audit_kwargs,
            )

    def set_next_action(self, next_action):
        if next_action:
            due_date = None
            state, _ = CaseWorkflowState.objects.set_next_action(
                self, next_action, requested_by=self.user_context
            )
            workflow = self.workflow.get_state()
            next_action_obj = workflow.key_index.get(next_action)
            time_gate = next_action_obj.get("time_gate") if next_action_obj else None
            # evaluate the next due date based on this action's time gate
            if state and time_gate:
                state.set_user_context(self.user_context)
                due_date = timezone.now() + datetime.timedelta(days=time_gate)
                # Set case level due date  TODO ? need this?
                state.due_date = due_date
                state.save()
                # Set due date in action.
                state, created = CaseWorkflowState.objects.set_value(
                    self, next_action, None, requested_by=self.user_context
                )
                state.due_date = due_date
                state.save()
            # if a next notice is to be set, do it now
            if next_action_obj.get("next_notice"):
                CaseWorkflowState.objects.set_next_notice(self, next_action, due_date=due_date)
            return next_action_obj, state
        return None, None

    def last_flow_restricted_stage(self):
        """
        Check the case state to see if a marker for the last restricted flow stage
        that was set against the case. Anything below that order-wise will not be accepted.
        """
        try:
            stage_id = CaseWorkflowState.objects.get(
                case=self, key="LAST_RESTRICTED_FLOW_STAGE_ID"
            ).value
            if stage_id:
                return CaseStage.objects.get(id=stage_id)
            else:
                return None
        except CaseWorkflowState.DoesNotExist:
            return None

    def determine_case_type(self, all_countries, evidence_of_subsidy, requested_by=None):
        """
        Based on whether all countries or evidence of subsidy were determined,
        set the case type accordingly as well as re-set any application documents.
        This can only occur on non initiated cases
        Returns a tuple of the case type id and a boolean indication if a change occured
        """
        if self.initiated_at:
            raise Exception("Case type cannot change after initiation")
        case_type_id = self.type.id or CASE_TYPE_ANTI_DUMPING
        original_case_type = self.type
        modified = False
        if all_countries is True and self.type.id == CASE_TYPE_ANTI_DUMPING:
            case_type_id = CASE_TYPE_SAFEGUARDING
            self.evidence_of_subsidy = None
        elif evidence_of_subsidy is True:
            case_type_id = CASE_TYPE_ANTI_SUBSIDY
            self.evidence_of_subsidy = "yes"
        modified = self.modify_case_type(case_type_id, requested_by=requested_by)
        return self.type, modified

    def modify_case_type(self, case_type_id, requested_by):
        """
        Modify the case type if it is different then the one provided,
        and reset the workflow and application documents as required.
        """
        modified = case_type_id != self.type.id
        if modified:
            self.type = CaseType.objects.get(id=case_type_id)
            self.save()
            CaseWorkflow.objects.snapshot_from_template(
                self, self.type.workflow, requested_by=requested_by
            )
            self.application.set_application_documents()
        return modified

    def set_milestone(self, milestone_type, date, set_by):
        if isinstance(date, (datetime.datetime, datetime.date)):
            date = date.strftime(settings.API_DATE_FORMAT)
        state, created = CaseWorkflowState.objects.set_value(
            case=self, key=milestone_type, value=date, requested_by=set_by, mutate=False
        )
        return state

    def case_milestone_index(self):
        """
        return a dict of important case milestone dates
        """
        keys = CASE_MILESTONE_DATES.keys()
        state = CaseWorkflowState.objects.value_index(case=self, keys=keys)
        index = {}
        for key in state:
            value = state[key][0] if state[key] else None
            if value:
                index[key] = parse(value).date()
        return index

    def get_state_key(self, key):
        return self.caseworkflowstate_set.filter(key=key, deleted_at__isnull=True).first()

    def workflow_state(self, **kwargs):
        return CaseWorkflowState.objects.value_index(case=self)
