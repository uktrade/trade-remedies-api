import datetime
import json
import re
from dateutil import parser
from core.services.base import TradeRemediesApiView, ResponseSuccess
from core.services.exceptions import (
    InvalidRequestParams,
    NotFoundApiExceptions,
    AccessDenied,
    InvalidFileUpload,
)
from django.db.models import Q
from django.db import transaction, models
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from cases.models import (
    Case,
    CaseType,
    CaseStage,
    Submission,
    SubmissionStatus,
    SubmissionType,
    SubmissionDocument,
    SubmissionDocumentType,
    get_case,
    get_submission_type,
    get_submission_status,
    Sector,
    Product,
    HSCode,
    ExportSource,
    ArchiveReason,
    CaseWorkflow,
    CaseWorkflowState,
    Notice,
)
from trade_remedies_api.constants import (
    STATE_INCOMPLETE,
    STATE_COMPLETE,
)
from cases.constants import (
    ALL_COUNTRY_CASE_TYPES,
    SUBMISSION_NOTICE_TYPES,
    SUBMISSION_NOTICE_TYPE_INVITE,
    SUBMISSION_NOTICE_TYPE_DEFICIENCY,
    SUBMISSION_TYPE_REGISTER_INTEREST,
    SUBMISSION_TYPE_INVITE_3RD_PARTY,
    SUBMISSION_TYPE_APPLICATION,
    SUBMISSION_STATUS_APPLICATION_SUBMIT_REVIEW,
    SUBMISSION_APPLICATION_TYPES,
    DIRECTION_BOTH,
    DIRECTION_TRA_TO_PUBLIC,
    SUBMISSION_DOCUMENT_TYPE_DEFICIENCY,
    DECISION_TO_INITIATE_KEY,
    TRA_ORGANISATION_ID,
    SECRETARY_OF_STATE_ORG_NAME,
    CASE_MILESTONE_DATES,
)
from core.utils import (
    key_by,
    deep_index_items_by,
    pluck,
)
from core.models import User, SystemParameter
from core.constants import (
    TRUTHFUL_INPUT_VALUES,
    SAFE_COLOURS,
)
from contacts.models import Contact
from security.models import UserCase, OrganisationCaseRole, CaseRole
from security.constants import (
    SECURITY_GROUPS_TRA,
    ROLE_PREPARING,
)
from security.exceptions import InvalidAccess
from organisations.models import Organisation, get_organisation
from documents.models import Document
from documents.exceptions import InvalidFile
from audit import AUDIT_TYPE_EVENT
from audit.utils import audit_log
from workflow.models import WorkflowTemplate
from django_countries import countries
from django.utils import timezone


class PublicCaseView(APIView):
    def get(self, request, case_number=None, *args, **kwargs):
        match = re.search("([A-Za-z]{1,3})([0-9]+)", case_number)
        case = Case.objects.get(
            type__acronym__iexact=match.group(1),
            initiated_sequence=match.group(2),
            deleted_at__isnull=True,
        )
        return ResponseSuccess({"result": case.to_dict()})


class PublicNoticeView(APIView):
    """
    Return a list of the most recently published public submissions,
    up to the supplied limit
    """

    def get(self, request, *args, **kwargs):
        limit = int(request.query_params.get("limit", "1000"))
        submissions = (
            Submission.objects.filter(
                type__key="public", issued_at__isnull=False, type__id__in=SUBMISSION_NOTICE_TYPES
            )
            .order_by("issued_at")
            .reverse()[:limit]
        )
        return ResponseSuccess(
            {
                "results": [
                    {
                        "name": submission.name,
                        "id": submission.id,
                        "url": submission.url,
                        "issued_at": submission.issued_at,
                        "type": submission.type.name,
                        "case": submission.case.to_minimal_dict(),
                        "case_initiated": bool(submission.case.initiated_at),
                    }
                    for submission in submissions
                ]
            }
        )


class CaseStateAPI(APIView):
    """
    Return a selected set of states from one case or a set of cases
    Pass a list of state fields to retrieve.
    Special field - 'LAST_PUBLICATION' gets the last issued submission.

    """

    def get(self, request, case_id=None, *args, **kwargs):
        if not case_id:
            cases = request.query_params.getlist("cases", [])
        else:
            cases = [case_id]

        fields = request.query_params.getlist("fields", [])
        result = {}

        if "LAST_PUBLICATION" in fields:
            # We are being asked for the latest submission issue date for each case in the list
            last_updates = (
                Submission.objects.filter(
                    case_id__in=cases, issued_at__isnull=False, deleted_at__isnull=True
                )
                .values("case_id")
                .annotate(last_publish=models.Max("issued_at"))
            )
            for last_update in last_updates:
                last_publish = last_update.get("last_publish")
                if last_publish:
                    case_id = str(last_update.get("case_id"))
                    result.setdefault(case_id, {})
                    result[case_id]["LAST_PUBLICATION"] = last_publish

        states = CaseWorkflowState.objects.filter(case_id__in=cases, key__in=fields)
        for state in states:
            case_id = str(state.case_id)
            result.setdefault(case_id, {})
            result[case_id][state.key] = {"value": state.value, "due": state.due_date}

        return ResponseSuccess({"result": result})


class CasesAPIView(TradeRemediesApiView):
    """
    Return all cases for a user/organisation

    `GET /cases/organisation/{ORGANISATION_ID}/`
    Return all cases of a given organisation this user has access to

    `GET /case/{CASE_ID}/organisation/{ORGANISATION_ID}/`
    Return a specific case for a given organisation

    `GET /case/{CASE_ID}/`
    Return a sepecific case if user has sufficient access


    `POST /cases/organisation/{ORGANISATION_ID}/`
    Create a new case

    #### Params
        `organisation_role` Applicant | Respondent
        `name` The case name

    """

    public = False
    all_cases = False  # set by the url def. to denote all cases

    def get(  # noqa: C901
        self, request, organisation_id=None, case_id=None, user_id=None, *args, **kwargs,
    ):
        archived = request.query_params.get("archived", "false")
        new_cases = request.query_params.get("new_cases", "false") in TRUTHFUL_INPUT_VALUES
        all_cases = request.query_params.get("all", self.all_cases)
        outer_org_cases = request.query_params.get("outer")
        all_initiated = request.query_params.get("initiated", True) in TRUTHFUL_INPUT_VALUES
        all_investigator_cases = request.query_params.get("all_investigator")
        registration_of_interest = request.query_params.get("registration-of-interest")
        exclude_types = request.query_params.get("exclude_types")
        fields = request.query_params.get("fields")
        _kwargs = {
            "archived": None
            if archived == "all"
            else archived and (archived.lower() in TRUTHFUL_INPUT_VALUES)
        }
        cases = []
        if all_cases in TRUTHFUL_INPUT_VALUES and all_initiated and organisation_id is None:
            cases = Case.objects.filter(
                deleted_at__isnull=True, archived_at__isnull=True, initiated_at__isnull=False
            )
            if exclude_types:
                cases = cases.exclude(type__id__in=exclude_types.split(","))
            cases = cases.select_related(
                "type", "stage", "archive_reason", "created_by", "workflow"
            ).order_by("sequence")
        elif archived in TRUTHFUL_INPUT_VALUES:
            cases = (
                Case.objects.filter(
                    deleted_at__isnull=True, archived_at__isnull=False, initiated_at__isnull=False
                )
                .select_related("type", "stage", "archive_reason", "created_by",)
                .order_by("sequence")
            )
        elif new_cases in TRUTHFUL_INPUT_VALUES:
            cases = (
                Case.objects.filter(
                    deleted_at__isnull=True, archived_at__isnull=True, initiated_at__isnull=True,
                )
                .exclude(usercase__user__groups__name__in=SECURITY_GROUPS_TRA)
                .select_related("type", "stage", "archive_reason", "created_by",)
                .order_by("sequence")
            )
        elif all_investigator_cases in TRUTHFUL_INPUT_VALUES:
            user_cases = Case.objects.all_user_cases(user=request.user, **_kwargs)
            all_investigator_cases = Case.objects.investigator_cases(current=True).order_by(
                "sequence"
            )
            cases_dict_list = []
            for case in all_investigator_cases:
                _dict = case.to_embedded_dict(fields=fields)
                _dict["user_case"] = case in user_cases
                cases_dict_list.append(_dict)
            return ResponseSuccess({"results": cases_dict_list})

        elif registration_of_interest in TRUTHFUL_INPUT_VALUES:
            cases = Case.objects.available_for_regisration_of_intestest(request.user)
        elif organisation_id is None and case_id is None:
            user = request.user
            if outer_org_cases:
                # Get the user-org-case objects for all users/cases in this user's org
                # e.g. all the cases a law-firm has been involved in
                user_cases = Case.objects.outer_user_cases(user=request.user)
                # need to get orgs that don't have a usercase yet - so just look at the createdby.
                user_organisations = Organisation.objects.filter(
                    created_by__in=user.organisation_users, deleted_at__isnull=True
                )
                organisations = {}
                for organisation in user_organisations:
                    organisations[str(organisation.id)] = 1
                for user_case in user_cases:
                    organisations[str(user_case.organisation.id)] = 1
                # Now link up the caseroles for each usercase
                caseroles = OrganisationCaseRole.objects.filter(
                    organisation__id__in=organisations.keys()
                )
                org_case_idx = {}
                for caserole in caseroles:
                    org_case_idx[
                        str(caserole.case.id) + ":" + str(caserole.organisation.id)
                    ] = caserole.role
                results = []
                for user_case in user_cases:
                    _dict = user_case.to_embedded_dict()
                    caserole = org_case_idx.get(
                        str(user_case.case.id) + ":" + str(user_case.organisation.id)
                    )
                    if caserole:
                        _dict.update({"role": caserole.to_dict()})
                    results.append(_dict)
                return ResponseSuccess({"results": results})
            user = User.objects.get(id=user_id) if user_id else user
            cases = Case.objects.all_user_cases(user=user, **_kwargs)
            results = [
                case.to_embedded_dict(user=user, is_primary_contact=True, fields=fields)
                for case in cases
            ]
            return ResponseSuccess({"results": results})
        elif case_id and self.organisation:
            case = Case.objects.select_related(
                "type", "stage", "archive_reason", "created_by", "workflow"
            ).get(
                id=case_id
            )  # usercase__user=request.user, usercase__organisation=self.organisation
            case.set_organisation_context(self.organisation)
            case.set_user_context([request.user])
            return ResponseSuccess(
                {"result": case.to_dict(organisation=self.organisation, fields=fields)}
            )
        elif organisation_id is not None:
            if outer_org_cases:
                cases = self.organisation.related_cases(
                    initiated_only=all_initiated, requested_by=request.user
                )
                return ResponseSuccess({"results": cases})
            elif all_cases:
                for ocr in OrganisationCaseRole.objects.case_prepared(organisation_id):
                    case_dict = ocr.to_embedded_dict()
                    case_dict.update(ocr.case.to_embedded_dict(organisation=self.organisation))
                    cases.append(case_dict)
                return ResponseSuccess({"results": cases})
            cases = UserCase.objects.filter(
                user=request.user, organisation_id=organisation_id
            ).select_related(
                "case", "case__stage", "case__created_by", "case__archive_reason", "case__workflow",
            )
            if case_id:
                try:
                    case = cases.get(case__id=case_id).case
                    return ResponseSuccess(
                        {"result": case.to_dict(organisation=self.organisation, fields=fields)}
                    )
                except Case.DoesNotExist:
                    raise NotFoundApiExceptions("Invalid case id or access is denied")
            else:
                cases = set([usercase.case for usercase in cases])
        elif case_id:
            try:
                if request.user.is_tra():
                    case = Case.objects.investigator_cases(request.user).get(id=case_id)
                else:
                    case = Case.objects.get_case(id=case_id)
                case.set_case_context(case)
                return ResponseSuccess({"result": case.to_dict(fields=fields)})
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Invalid case id or access is denied")
        return ResponseSuccess(
            {
                "results": [
                    case.to_embedded_dict(organisation=self.organisation, fields=fields)
                    for case in cases
                ]
            }
        )

    @transaction.atomic
    def post(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        role = request.data.get("organisation_role")
        case_fields = [
            "name",
            "initiated_at",
            "archived_at",
            "archive_reason_id",
            "submitted_at",
            "type_id",
            "parent_id",
        ]
        if case_id:
            case = Case.objects.get_case(id=case_id, requested_by=request.user)
            if request.data:
                was_initiated = bool(case.initiated_at)
                _data_dict = request.data.dict()
                reset_init_decision = _data_dict.pop("reset_initiation_decision", None)
                case.load_attributes(_data_dict, case_fields)
                case.save()
                if reset_init_decision:
                    try:
                        CaseWorkflowState.objects.get(
                            case=case, key=DECISION_TO_INITIATE_KEY, deleted_at__isnull=True
                        ).delete()
                    except CaseWorkflowState.DoesNotExist:
                        pass
                    finally:
                        # reset any workflow related switches to control exit path
                        case.reset_initiation_decision()
                if (
                    was_initiated
                    and not case.initiated_at
                    or case.initiated_at
                    and not was_initiated
                ):
                    initiation_action = (
                        "un-initiated" if was_initiated and not case.initiated_at else "initiated"
                    )
                    initiation_change_message = f"Case {initiation_action} by Administrator"
                    audit_log(
                        audit_type=AUDIT_TYPE_EVENT,
                        user=request.user,
                        model=case,
                        case=case,
                        milestone=True,
                        data={"message": initiation_change_message},
                    )
                if request.data.get("stage_id"):
                    ignore_flow = request.data.get("ignore_flow") == "true" and request.user.is_tra(
                        manager=True
                    )
                    case_stage = CaseStage.objects.get(id=request.data["stage_id"])
                    new_stage = case.set_stage(case_stage, ignore_flow=ignore_flow)
                # Reset the workflow if the type has changed
                if (
                    not case.initiated_at
                    and request.data.get("type_id")
                    and request.data.get("type_id") != str(case.type.id)
                ):
                    CaseWorkflow.objects.snapshot_from_template(
                        case, case.type.workflow, requested_by=self.user
                    )
                if request.data.get("next_action"):
                    case.set_next_action(request.data["next_action"])
                case.refresh_from_db()
        else:
            # create a new case
            case = Case.objects.create(name=request.data.get("name"), created_by=request.user)
            org_case, created = OrganisationCaseRole.objects.assign_organisation_case_role(
                organisation=self.organisation, case=case, role=role, created_by=request.user
            )
        return ResponseSuccess({"result": case.to_dict()}, http_status=status.HTTP_201_CREATED)


class CasesCountAPIView(TradeRemediesApiView):
    """
    Counts cases because it's more efficient that way
    Crteria as for CasesApiView
    """

    def get(self, request, organisation_id=None, case_id=None, user_id=None, *args, **kwargs):

        not_archived = not request.query_params.get("archived")
        not_initiated = not request.query_params.get("initiated")
        count = Case.objects.filter(
            deleted_at__isnull=True,
            archived_at__isnull=not_archived,
            initiated_at__isnull=not_initiated,
        ).count()
        return ResponseSuccess({"result": count}, http_status=status.HTTP_201_CREATED)


class CaseInitiationAPIView(TradeRemediesApiView):
    @transaction.atomic  # noqa: C901
    def post(self, request, *args, **kwargs):
        product = None
        export_source = None
        case_id = request.data.get("id")
        request_params = request.data.dict()
        case_name = request.data.get("case_name")
        # case_type_id = request.data.get("case_type_id")
        product_name = request.data.get("product_name")
        product_description = request.data.get("product_description")
        sector_id = request.data.get("sector_id")
        export_country_codes = request.data.getlist("export_country_code")
        hs_codes = request.data.getlist("hs_code")
        ex_oficio = request_params.pop("ex_oficio", None) in TRUTHFUL_INPUT_VALUES
        if not request_params.get("organisation_name") and not request_params.get(
            "organisation_id"
        ):
            if request.user.is_tra():
                if not request_params.get("organisation_id"):
                    request_params["organisation_name"] = SECRETARY_OF_STATE_ORG_NAME
                else:
                    request_params.pop("organisation_name", None)
            else:
                raise InvalidRequestParams("Missing required parameters")
        organisation, case, submission = Case.objects.create_new_case(
            user=request.user, ex_oficio=ex_oficio, **request_params
        )
        case.set_next_action("ASSIGN_MANAGER")
        if product_description and sector_id:
            product = Product.objects.create(
                name=product_name,
                case=case,
                created_by=request.user,
                sector=Sector.objects.get(id=int(sector_id)),
                description=product_description,
                user_context=[request.user],
            )
        if export_country_codes:
            for export_country_code in export_country_codes:
                if export_country_code:
                    if not ExportSource.objects.filter(
                        case=case, country=export_country_code
                    ).exists():
                        export_source = ExportSource.objects.create(
                            case=case,
                            country=export_country_code,
                            created_by=request.user,
                            user_context=[request.user],
                        )
        if product and hs_codes:
            Product.objects.set_hs_codes(product, hs_codes)

        case_name = case_name or case.derive_case_name()
        if case_name:
            case.name = case_name
            case.save()
        submission.deficiency_notice_params = submission.deficiency_notice_params or {}
        submission.deficiency_notice_params["organisation_role"] = request_params.get(
            "organisation_role"
        )
        submission.save()
        return ResponseSuccess(
            {
                "result": {
                    "submission": submission.to_dict(),
                    "case": case.to_dict(),
                    "organisation": organisation.to_dict(),
                    "product": product.to_dict() if product else None,
                    "export_source": export_source.to_dict() if export_source else None,
                }
            },
            http_status=status.HTTP_201_CREATED,
        )


class CaseUsersAPI(TradeRemediesApiView):
    def get(self, request, case_id):
        if not request.user.is_tra(manager=True):
            raise InvalidAccess("This endpoint is restricted to TRA managers only")
        case = Case.objects.get(id=case_id)
        case_users = [user.to_dict() for user in case.users]
        users_by_function = deep_index_items_by(case_users, "user/tra")
        return ResponseSuccess(
            {
                "results": {
                    "tra_users": users_by_function.get("true", []),
                    "public_users": users_by_function.get("", []),
                }
            }
        )


class CaseParticipantsAPI(TradeRemediesApiView):
    def get(self, request, case_id, *args, **kwargs):
        fields = request.query_params.get("fields")
        case = Case.objects.get(id=case_id)
        return ResponseSuccess({"results": case.participants(fields=fields),})


class CaseInterestAPI(TradeRemediesApiView):
    """
    Create a "Register interest" submission to an ongoing case

    GET
        Query parameters:
        - archived (true|[false]): whether to show archived submissions
        - preparing (true|[false]): whether to show submissions in preparation

    """

    def get(self, request, *args, **kwargs):
        show_archived = request.query_params.get("archived", "false") == "true"
        show_preparing = request.query_params.get("preparing", "false") == "true"
        all_interests = request.query_params.get("all", "false") == "true"
        interest_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        # TODO: Clean up role_keys
        # role_keys = ['awaiting_approval', 'rejected']
        user_filter = {"created_by": request.user}
        # if show_preparing:
        #     role_keys.append('preparing')
        if all_interests and request.user.has_perm("core.can_view_all_org_cases"):
            user_filter = {"created_by__in": request.user.organisation_users}
        submissions = Submission.objects.select_related(
            "case", "status", "type", "organisation", "created_by",
        ).filter(
            type=interest_type,
            deleted_at__isnull=True,
            organisation__organisationcaserole__case=models.F("case"),
            organisation__organisationcaserole__organisation=models.F("organisation"),
            organisation__organisationcaserole__approved_at__isnull=True,
            **user_filter,
        )
        if not show_archived:
            submissions = submissions.exclude(archived=True)
        submissions = submissions.distinct().order_by("created_at")
        return ResponseSuccess(
            {"results": [submission.to_embedded_dict() for submission in submissions]}
        )

    @transaction.atomic
    def post(self, request, case_id, *args, **kwargs):
        organisation_name = request.data.get("organisation_name")
        representing = request.data.get("representing", "own")
        organisation_id = request.data.get("organisation_id")
        case = Case.objects.get_case(id=case_id, requested_by=self.user)
        if representing == "other" and organisation_name:
            params = pluck(
                request.data,
                [
                    "organisation_name",
                    "companies_house_id",
                    "vat_number",
                    "eori_number",
                    "duns_number",
                    "organisation_website",
                ],
            )
            organisation = Organisation.objects.create_or_update_organisation(
                user=request.user,
                name=organisation_name.upper(),
                country=request.data.get("organisation_country"),
                address=request.data.get("organisation_address"),
                post_code=request.data.get("organisation_post_code"),
                **params,
            )
        elif (representing in ["own", "previous"]) and organisation_id:
            organisation = get_organisation(request.data.get("organisation_id"))
        else:
            raise InvalidRequestParams("Either organisation name or id are required")

        contact = request.user.contact
        contacts = list(organisation.contacts)
        # check if a reg interest already exists for this org by the same user
        existing = Submission.objects.filter(
            organisation=organisation,
            case=case,
            deleted_at__isnull=True,
            # created_by=request.user
        )
        if existing.exists():
            link = None
            for roi in existing:
                if roi.created_by.id == request.user.id:
                    link = (
                        f"/case/{roi.case.id}/organisation/"
                        f"{roi.organisation.id}/submission/{roi.id}/"
                    )
            if link:
                raise InvalidRequestParams(
                    f"You have already registered interest in this case on behalf of: "
                    f'{organisation.name}. <a href="{link}">View your registration</a>'
                )
            raise InvalidRequestParams(
                f"The organisation {organisation.name} "
                f"has already registered interest in this case."
            )
        # make this contact primary in the case
        contact.set_primary(case=case, organisation=organisation, request_by=self.user)
        org_case, created = OrganisationCaseRole.objects.assign_organisation_case_role(
            organisation=organisation,
            case=case,
            role=CaseRole.objects.get(id=ROLE_PREPARING),
            sampled=True,
            created_by=request.user,
        )
        submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        submission = Submission.objects.create(
            name=submission_type.name,
            type=submission_type,
            status=submission_type.default_status,
            case=case,
            organisation=organisation,
            contact=contact,
            created_by=self.user,
            user_context=self.user,
        )
        return ResponseSuccess(
            {
                "result": {
                    "submission": submission.to_dict(),
                    "case": case.to_dict(),
                    "organisation": organisation.to_dict(),
                    "contacts": [contact.to_embedded_dict() for contact in contacts],
                }
            },
            http_status=status.HTTP_201_CREATED,
        )


class CaseUserAssignAPI(TradeRemediesApiView):
    """
    Assign a user to a case. This API call is restricted to TRA members only.

    `GET /api/v1/case/{case_id}/users/`
    Get all case TRA users

    `POST /api/v1/case/{case_id}/users/assign/{user_id}/`
    Assign a TRA user to the case

    `DELETE /api/v1/case/{case_id}/users/assign/{user_id}/`
    Remove a TRA user from a case
    """

    def get(self, request, case_id, *args, **kwargs):
        try:
            case = Case.objects.get_case(id=case_id)
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("invalid case id")
        results = []
        for member in case.team:
            dict = member.to_dict()
            dict["user"] = member.user.to_dict()
            results.append(dict)

        return ResponseSuccess({"results": results})

    @transaction.atomic
    def post(self, request, case_id, user_id=None, *args, **kwargs):
        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("invalid case id")
        if user_id:
            user_ids = [user_id]
        else:
            user_ids = request.data.getlist("user_id")
            UserCase.objects.filter(case=case, user__groups__name__in=SECURITY_GROUPS_TRA).delete()
        users = User.objects.filter(id__in=user_ids)
        existing_team = case.team
        try:
            for user in users:
                case.assign_user(user=user, created_by=request.user)
            if existing_team:
                log_message = f"Team updated ({len(users)} members)"
            else:
                log_message = f"Team assigned ({len(users)} members)"
            audit_log(
                audit_type=AUDIT_TYPE_EVENT,
                user=request.user,
                model=case,
                case=case,
                milestone=True,
                data={"message": log_message},
            )
        except InvalidAccess:
            raise AccessDenied("User cannot perform this action")
        return ResponseSuccess(
            {"result": {"user_ids": map(str, user_ids), "case_id": str(case.id),}},
            http_status=status.HTTP_201_CREATED,
        )

    def delete(self, request, case_id, user_id, *args, **kwargs):
        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("invalid case id")
        user = User.objects.get(id=user_id)
        try:
            case.remove_user(user=user, created_by=request.user)
        except InvalidAccess:
            raise AccessDenied("User cannot perform this action")
        return ResponseSuccess({"result": {"deleted": True}}, http_status=status.HTTP_201_CREATED)


class SubmissionsAPIView(TradeRemediesApiView):
    """
    Return all submissions for a user/organisation and/or a specific case

    `GET /cases/{ORGANISATION_ID}/`
    Return all submissions for an organisation across multiple cases

    `GET /cases/{ORGANISATION_ID}/{CASE_ID}/submissions/`
    Return all organisation submissions for a single case

    `POST /cases/{ORGANISATION_ID}/{CASE_ID}/submissions/`
    Create a new submission for this case

    #### Params
        `submission_type` Application | Questionnaire
        `private` true/false - get only own org submissions (true) or all allowed.
        'sampled' [true]/false - return ony sampled participants

    """

    show_global = False

    def get(self, request, organisation_id=None, case_id=None, submission_id=None, *args, **kwargs):
        case = None
        private = request.query_params.get("private", "false").lower() in ("true", "1", "t", "y")
        self.show_global = self.show_global or request.query_params.get(
            "global", "false"
        ).lower() in ("true", "1", "t", "y")
        sampled_only = (
            request.query_params.get("sampled", "false") in ("true", "1", "Y") and not submission_id
        )
        fields = request.query_params.get("fields")
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Case not found or access denied")
        submissions = Submission.objects.get_submissions(
            case=case,
            requested_by=request.user,
            requested_for=self.organisation,
            private=private,
            submission_id=submission_id,
            show_global=self.show_global,
            sampled_only=sampled_only,
        )
        if submission_id:
            if submissions:
                submission = submissions.get(id=submission_id)
                return ResponseSuccess(
                    {
                        "result": submission.to_dict(
                            requested_by=request.user,
                            requested_for=self.organisation,
                            with_documents=True,
                            fields=fields,
                        )
                    }
                )
            else:
                raise NotFoundApiExceptions("Submission not found or invalid access")
        submissions = submissions.order_by("created_at")
        _result_list = [
            submission.to_embedded_dict(
                requested_by=request.user, requested_for=self.organisation, fields=fields
            )
            for submission in submissions
        ]
        return ResponseSuccess({"results": _result_list})

    @transaction.atomic
    def post(
        self, request, organisation_id=None, case_id=None, submission_id=None, *args, **kwargs
    ):
        case = get_case(str(case_id))
        _is_tra = request.user.is_tra()
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id, case=case)
            submission.set_user_context(request.user)
            submission.load_attributes(
                request.data,
                [
                    "name",
                    "contact_id",
                    "doc_reviewed_at",
                    "due_at",
                    "time_window",
                    "url",
                    "description",
                    "deficiency_notice_params",
                    "organisation_id",
                ],
            )
            new_type = request.data.get("submission_type_id")
            if new_type:
                submission.type = SubmissionType.objects.get(id=new_type)
            if submission.url and not submission.url.startswith("http"):
                submission.url = f"https://{submission.url}"
            submission.save()
            submission.refresh_from_db()
            return ResponseSuccess(
                {"result": {"submission": submission.to_dict()}},
                http_status=status.HTTP_201_CREATED,
            )

        submission_type = request.data.get("submission_type")
        submission_status_id = request.data.get("submission_status_id")
        submission_type = get_submission_type(submission_type)
        if not submission_status_id:
            submission_status = submission_type.default_status
        else:
            submission_status = get_submission_status(submission_status_id)
        deficiency_notice_params = json.loads(request.data.get("deficiency_notice_params") or "{}")
        send_to = deficiency_notice_params.get("send_to")
        # If the organisation isn't set, an it's a public submission, it's the TRA
        if not self.organisation and request.data.get("public") and _is_tra:
            self.organisation = Organisation.objects.get(id=TRA_ORGANISATION_ID)

        if submission_type and case:
            clone = None
            user_contact = request.data.get("contact_id")
            # if not user_contact and _is_tra:
            #    primary_contact = self.organisation.primary_contact(case)
            #    user_contact = primary_contact.id if primary_contact else None
            if not user_contact and not _is_tra:
                user_contact = request.user.contact.id if request.user.contact else None
            submission = Submission.objects.create(
                type=submission_type,
                status=submission_status,
                case=case,
                name=request.data.get("name"),
                organisation=self.organisation,
                contact_id=user_contact,
                created_by=request.user,
                deficiency_notice_params=deficiency_notice_params,
            )
            if submission_status_id:
                submission, clone = submission.transition_status(submission_status_id)
            if not clone:  # new submission, assign case documents if applicable
                submission.set_case_documents(request.user)
            return ResponseSuccess(
                {
                    "result": {
                        "original": submission.to_dict() if clone else None,
                        "submission": clone.to_dict() if clone else submission.to_dict(),
                    }
                },
                http_status=status.HTTP_201_CREATED,
            )
        else:
            raise InvalidRequestParams("Submission type and case id are required")

    @transaction.atomic
    def delete(
        self, request, case_id, submission_id, organisation_id=None,
    ):
        case = get_case(str(case_id))
        submission = Submission.objects.get_submission(id=submission_id, case=case)
        submission.set_user_context(request.user)
        # Tidy up any loose ends
        # If the case is not initiated, and this application is the only submission,
        # delete the case as well
        if submission.case.stage.key in ["CASE_CREATED"] and len(submission.case.submissions) == 1:
            submission.case.delete()
        # If this is a registration of interest, we need to remove the caserole too
        if submission.type.key == "interest" and organisation_id:
            OrganisationCaseRole.objects.revoke_organisation_case_role(organisation_id, case)
        purge = submission.status == submission.type.default_status
        submission.delete(purge=purge)
        notify_template = (
            "NOTIFY_APPLICATION_CANCELLED"
            if submission.type.id in SUBMISSION_APPLICATION_TYPES
            else "DRAFT_SUBMISSION_CANCELLED"
        )
        if organisation_id:
            case.notify_all_participants(
                request.user,
                submission=submission,
                organisation_id=organisation_id,
                template_name=notify_template,
            )
        return ResponseSuccess({"result": {"deleted": True, "submission_id": submission_id}})


class SubmissionDocumentsAPI(TradeRemediesApiView):
    """
    Return all documents for a submission
    """

    def get(self, request, case_id, submission_id, organisation_id=None):
        all_versions = request.query_params.get("all_versions")
        try:
            case = Case.objects.get(id=case_id)
            submission = Submission.objects.get_submission(id=submission_id, case=case)
        except (Case.DoesNotExist, Submission.DoesNotExist):
            raise NotFoundApiExceptions("Invalid case or submission id")
        organisation = get_organisation(organisation_id) if organisation_id else None

        if all_versions:
            docs = []
            sub_list = submission.versions
            for loop_sub in sub_list:
                doclist = loop_sub.submission_documents(
                    requested_by=request.user, requested_for=organisation
                )
                docs.append(
                    {
                        "id": loop_sub.id,
                        "version": loop_sub.version,
                        "documents": [doc.to_dict(user=request.user) for doc in doclist],
                    }
                )
                # docs[str(loop_sub.id)] = [doc.to_dict(user=request.user) for doc in doclist]
            return ResponseSuccess(
                {
                    "result": {
                        "documents": docs,
                        "deficiency_documents": [
                            defdoc.to_minimal_dict() for defdoc in submission.deficiency_documents
                        ],
                    }
                }
            )
        docs = submission.submission_documents(
            requested_by=request.user, requested_for=organisation
        )
        return ResponseSuccess(
            {
                "result": {
                    "documents": [doc.to_dict(user=request.user) for doc in docs],
                    "deficiency_documents": [
                        defdoc.to_minimal_dict()
                        for defdoc in submission.get_parent_deficiency_documents()
                    ],
                }
            }
        )


class SubmissionExistsAPI(TradeRemediesApiView):
    def get(self, request, case_id, organisation_id, submission_type_id):
        submission_qry = Submission.objects.filter(
            case__id=case_id,
            organisation__id=organisation_id,
            type__id=submission_type_id,
            status__draft=True,
        )
        submission = submission_qry.first()
        exists = submission_qry.exists()
        return ResponseSuccess(
            {
                "result": {
                    "exists": exists,
                    "submission": submission.to_dict() if submission else None,
                }
            }
        )


class SubmissionOrganisationAPI(TradeRemediesApiView):
    """
    Return the organisation and contact for a submission
    """

    def get(self, request, case_id, submission_id):
        try:
            case = Case.objects.get(id=case_id)
            submission = Submission.objects.get_submission(id=submission_id, case=case)
        except (Case.DoesNotExist, Submission.DoesNotExist):
            raise NotFoundApiExceptions("Invalid case or submission id")
        organisation = submission.organisation
        return ResponseSuccess({"result": organisation.to_dict(case=case, with_contacts=True)})


class SubmissionNotifyAPI(TradeRemediesApiView):
    def post(
        self, request, case_id, organisation_id, submission_id, notice_type=None, *args, **kwargs
    ):
        notice_type = notice_type or SUBMISSION_NOTICE_TYPE_INVITE
        case = get_case(case_id)
        contact_id = request.data.get("contact_id")
        submission = Submission.objects.get_submission(id=submission_id, case=case)
        if not submission.organisation:
            raise InvalidRequestParams("No organisation for submission")
        if contact_id:
            contact = Contact.objects.select_related("userprofile", "organisation").get(
                id=contact_id,
                casecontact__case=case,
                casecontact__organisation=submission.organisation,
            )
        else:
            contact = submission.organisation.primary_contact(submission.case)
        if not contact:
            raise InvalidRequestParams(
                'No contact for organisation "' + submission.organisation.name + '"'
            )

        values = {key: request.data.get(key) for key in request.data.keys()}
        # if a timewindow is set but no due date, set it now on notify time
        if submission.time_window and not submission.due_at:
            submission.due_at = timezone.now() + datetime.timedelta(days=submission.time_window)
            submission.save()
        if notice_type == SUBMISSION_NOTICE_TYPE_INVITE:
            submission.notify(
                sent_by=request.user,
                context=values,
                contact=contact,
                new_status="sent",
                template_id=submission.type.notify_template,
            )
        elif notice_type == SUBMISSION_NOTICE_TYPE_DEFICIENCY:
            submission.notify_deficiency(sent_by=request.user, context=values, contact=contact)
        return ResponseSuccess()


class SubmissionCloneAPIView(TradeRemediesApiView):
    """
    Clone a submission replacing given fields and return clone
    """

    @transaction.atomic
    def post(self, request, case_id=None, submission_id=None, *args, **kwargs):
        submission = Submission.objects.get_submission(id=submission_id)
        submission.id = None
        submission.load_attributes(
            request.data, ["name", "contact_id", "deficiency_notice_params", "organisation_id"]
        )
        submission.save()
        # Now clone all the submission document objects
        for sub_doc in SubmissionDocument.objects.filter(submission_id=submission_id):
            sub_doc.id = None
            sub_doc.submission_id = submission.id
            sub_doc.save()

        return ResponseSuccess({"result": submission.to_dict()})


class SubmissionStatusAPIView(TradeRemediesApiView):
    """
    Get or set a submission status.
    """

    def get(self, request, organisation_id=None, case_id=None, submission_id=None, *args, **kwargs):
        statuses = SubmissionStatus.objects.filter()
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id)
            statuses = statuses.filter(type=submission.type)
        statuses = statuses.order_by("order")
        return ResponseSuccess({"results": [status.to_dict() for status in statuses]})

    @transaction.atomic  # noqa: C901
    def post(
        self, request, organisation_id=None, case_id=None, submission_id=None, *args, **kwargs
    ):
        """
        Either status id or context can be provided. A context is one of sent|received|default
        and will trigger the relevant status for the submission type where applicable.
        A deficiency document can be attached at this point as well if applicable.
        """

        deficiency_documents = request.FILES and request.FILES.getlist("deficiency_documents", None)
        deficient_document_ids = request.data.getlist("deficient_document_id", None)
        sufficient_document_ids = request.data.getlist("sufficient_document_id", None)
        submission_status_id = request.data.get("submission_status_id")
        submission_status_context = request.data.get("status_context")
        issue_submission = request.data.get("issue")

        # TODO: Leaving these two subsequent lines here for now, but commenting out from front end
        stage_change_if_sufficient = request.data.get("stage_change_if_sufficient")
        stage_change_if_deficient = request.data.get("stage_change_if_deficient")
        if submission_status_context and submission_status_context not in (
            "received",
            "review",
            "sent",
            "default",
            "draft",
            "deficient",
            "sufficient",
        ):
            raise InvalidRequestParams(
                'Invalid status context "' + (submission_status_context or "empty") + '"'
            )
        case = get_case(case_id)
        case.set_user_context(request.user)
        submission = Submission.objects.get_submission(id=submission_id, case=case)
        submission.set_user_context(request.user)
        clone = None
        submission_status = None
        original_submission_status = submission.status
        was_in_review = original_submission_status.review if original_submission_status else False
        # If the submission status is sufficient but submission was previously in review,
        # adjust to review_ok
        if submission_status_context == "sufficient" and was_in_review:
            submission_status_context = "review_ok"
        submission_user = (
            submission.contact.userprofile.user
            if submission.contact and submission.contact.has_user
            else None
        )
        if deficiency_documents:
            for deficiency_document in deficiency_documents:
                try:
                    document = Document.objects.create_document(
                        file=deficiency_document, user=request.user, case=case
                    )
                except InvalidFile as ifex:
                    raise InvalidFileUpload(ifex.message)
                submission.add_document(
                    document=document,
                    document_type=SubmissionDocumentType.objects.get(
                        id=SUBMISSION_DOCUMENT_TYPE_DEFICIENCY
                    ),
                    issued=False,
                    issued_by=request.user,
                )

            submission.save()
        if submission_status_id:
            submission_status = SubmissionStatus.objects.get(id=submission_status_id)
            if submission_status.version and not submission_status.sufficient:
                submission_status_context = "sent"
        elif submission_status_context:
            try:
                submission_status = getattr(submission.type, f"{submission_status_context}_status")
            except AttributeError:
                pass
        # only transition status if it has actually changed
        if submission_status and submission_status != submission.status:
            submission, clone = submission.transition_status(submission_status)
            # if we're provided a stage change directive, action it now
            if submission_status.sufficient and stage_change_if_sufficient:
                case.stage = CaseStage.objects.get(key=stage_change_if_sufficient)
                case.save()
            elif (
                submission_status.version
                and not submission_status.sufficient
                and stage_change_if_deficient
            ):
                case.stage = CaseStage.objects.get(key=stage_change_if_deficient)
                case.save()
            if clone and submission_status.version and not submission_status.sufficient:
                clone.sent_at = timezone.now()
                clone.sent_by = request.user
                clone._disable_audit = True
                clone.save()
            if submission_status_context == "sent":
                submission.sent_at = timezone.now()
                submission.sent_by = request.user
                if submission.time_window:
                    submission.due_at = timezone.now() + datetime.timedelta(
                        days=submission.time_window
                    )
                submission.save()
            if submission_status_context == "received":
                submission.received_at = timezone.now()
                submission.received_from = request.user
                submission.save()
            # If the submission came out of review, has a notification preset,
            # or a final application success, notify the user
            # if was_in_review:
            #     submission.notify_received(user=submission_user,
            #     template_id='NOTIFY_DRAFT_APPLICATION_REVIEWED')
            # el
            if submission.status.send_confirmation_notification:
                submission.notify_received(user=submission_user or request.user)
                if submission.type_id == SUBMISSION_TYPE_APPLICATION:
                    due_date = timezone.now() + datetime.timedelta(
                        days=settings.DEADLINE_AFTER_ASSESSMENT_RECEIPT_DAYS
                    )
                    CaseWorkflowState.objects.set_value(
                        case, "INITIATION_TASKS", None, due_date=due_date, requested_by=request.user
                    )
                    CaseWorkflowState.objects.set_next_notice(
                        case, "INITIATION_TASKS", due_date=due_date, requested_by=request.user
                    )
                    audit_log(
                        audit_type=AUDIT_TYPE_EVENT,
                        user=request.user,
                        model=submission,
                        case=case,
                        milestone=True,
                        data={"message": "Full application submitted"},
                    )
            elif submission.type_id == SUBMISSION_TYPE_APPLICATION and submission.status.sufficient:
                submission.notify_received(
                    user=submission_user, template_id="NOTIFY_APPLICATION_SUCCESSFUL"
                )
        elif not submission_status and not issue_submission:
            raise InvalidRequestParams("Status id or context are required.")

        # do we need to issue (or un-issue) the submission?
        if issue_submission:
            if ((issue_submission == "issue") and not submission.issued_at) or (
                (issue_submission == "un-issue") and submission.issued_at
            ):
                submission.issued_at = None if submission.issued_at else timezone.now()
                submission.issued_by = request.user if submission.issued_at else None
                submission.save()
                if issue_submission == "issue":
                    submission.case.notify_all_participants(request.user, submission=submission)
                submission.add_note(
                    "Submission published"
                    if issue_submission == "issue"
                    else "Submission withdrawn",
                    request.user,
                )

        # if deficiency document ids supplied, set each to deficient
        if deficient_document_ids:
            subdocs = submission.submissiondocument_set.filter(
                document_id__in=deficient_document_ids
            )
            for subdoc in subdocs:
                subdoc.deficient = True
                subdoc.save()
        if sufficient_document_ids:
            for subdoc in subdocs:
                subdoc.sufficient = True
                subdoc.save()
        # if submission_status and not submission_status.draft
        # and submission_status.send_confirmation_notification:
        #     submission.notify_received(user=request.user)

        result = {
            "original": submission.to_dict() if clone else None,
            "submission": clone.to_dict() if clone else submission.to_dict(),
        }

        return ResponseSuccess({"result": result})


class SubmissionDocumentStatusAPI(TradeRemediesApiView):
    """
    Set the status of a specific submission document to deficient or sufficient
    """

    def post(self, request, case_id, submission_id, document_id, *args, **kwargs):
        doc_status = request.data.get("status")
        if doc_status not in ("deficient", "sufficient"):
            raise InvalidRequestParams("status should be either sufficient or deficient")

        block_from_public_file = (
            request.data.get("block_from_public_file", False) in TRUTHFUL_INPUT_VALUES
        )
        block_reason = request.data.get("block_reason", "")

        case = get_case(case_id)
        submission = Submission.objects.get_submission(id=submission_id, case=case)
        try:
            submission_document = SubmissionDocument.objects.get(
                submission=submission, document__deleted_at__isnull=True, document_id=document_id
            )
            submission_document.deficient = doc_status == "deficient"
            submission_document.sufficient = doc_status == "sufficient"

            submission_document.document.block_from_public_file = block_from_public_file
            submission_document.document.block_reason = block_reason

            if block_from_public_file:
                submission_document.document.blocked_at = timezone.now()
                submission_document.document.blocked_by = request.user

            submission_document.document.save()

            submission_document.save()

        except SubmissionDocument.DoesNotExist:
            raise NotFoundApiExceptions("Document not found in this submission")
        return ResponseSuccess(
            {"result": submission_document.to_dict()}, http_status=status.HTTP_201_CREATED
        )


class SectorsAPIView(TradeRemediesApiView):
    """
    Return all available industry sectors

    `GET /sectors/`
    Return all industry sectors
    """

    def get(self, request, *args, **kwargs):
        sectors = Sector.objects.all().order_by("id")
        return ResponseSuccess({"results": [sector.to_dict() for sector in sectors]})


class ProductsAPIView(TradeRemediesApiView):
    """
    Get and create product iformation

    `GET /cases/{CASE_ID}/organisation/{ORGANISATION_ID}/submission/{SUBMISSION_ID}/product/`
    Return product information for this submission


    """

    def get(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        case = None
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Case not found or access denied")
        try:
            product = Product.objects.get(case=case)
        except Product.DoesNotExist:
            product = None
        return ResponseSuccess({"result": product.to_dict() if product else {}})

    @transaction.atomic
    def post(self, request, organisation_id=None, case_id=None, product_id=None, *args, **kwargs):
        case = get_case(str(case_id))
        if product_id:
            product = Product.objects.get(case=case, id=product_id)
        else:
            product = Product(case=case, created_by=request.user)
        sector_id = request.data.get("sector_id")
        description = request.data.get("description")
        product_name = request.data.get("product_name")
        sector = Sector.objects.get(id=int(sector_id))
        product.name = product_name
        product.sector = sector
        product.description = description
        product.save()
        if request.data.get("hs_codes"):
            Product.objects.set_hs_codes(product, request.data.getlist("hs_codes"))
        derived_case_name = case.derive_case_name()
        if derived_case_name:
            case.name = derived_case_name
            case.save()
        return ResponseSuccess({"result": product.to_dict()}, http_status=status.HTTP_201_CREATED)


class ProductHSCodeAPI(TradeRemediesApiView):
    def delete(self, request, case_id, organisation_id, product_id, code_id, *args, **kwargs):
        product = Product.objects.get(id=product_id)
        code = HSCode.objects.get(id=code_id)
        product.remove_hs_code(code)
        return ResponseSuccess({"result": product.to_dict()})


class ExportSourceAPIView(TradeRemediesApiView):
    """
    Get and create export source iformation

    `GET /cases/{CASE_ID}/organisation/{ORGANISATION_ID}/submission/{SUBMISSION_ID}/exportsource/`
    Return export source information for this submission


    """

    def get(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        case = None
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Case not found or access denied")
        export_sources = ExportSource.objects.filter(case=case, deleted_at__isnull=True)
        return ResponseSuccess(
            {"results": [export_source.to_dict() for export_source in export_sources]}
        )

    @transaction.atomic
    def post(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        case = get_case(str(case_id))
        original_case_type = case.type
        sources = request.data.get("sources")
        evidence_of_subsidy = request.data.get("evidence_of_subsidy")
        export_sources = []
        if sources and isinstance(sources, str):
            sources = json.loads(sources)
        all_countries = False
        for source in sources:
            if source == "ALL":
                ExportSource.objects.filter(case=case).delete()
                all_countries = True
                break
            else:
                country = source.get("country")
                if country:
                    try:
                        ExportSource.objects.get(case=case, country=country)
                    except ExportSource.DoesNotExist:
                        export_source = ExportSource(
                            case=case,
                            created_by=request.user,
                            user_context=[request.user],
                            country=country,
                        )
                        export_source.save()
                        export_sources.append(export_source.to_dict())
                elif source.get("id"):
                    ExportSource.objects.get(case=case, id=source["id"]).delete()
        # evaluate if a change in case type is required
        case_type, case_type_modified = case.determine_case_type(
            all_countries=all_countries,
            evidence_of_subsidy=evidence_of_subsidy == "yes",
            requested_by=self.user,
        )
        derived_case_name = case.derive_case_name()
        if derived_case_name:
            case.name = derived_case_name
            case.save()
        # if original_case_type != case.type:
        #     case.application.set_application_documents()
        return ResponseSuccess({"results": export_sources}, http_status=status.HTTP_201_CREATED)


class ReviewTypeAPIView(TradeRemediesApiView):
    """
    Post of review type and reference case
    """

    @transaction.atomic
    def post(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        reference_case_id = request.data.get("reference_case")
        case_type_id = request.data.get("case_type")
        case = get_case(str(case_id))
        if case_type_id:
            case.modify_case_type(case_type_id, requested_by=request.user)
        if reference_case_id:
            if reference_case_id.startswith("notice:"):
                case.notice = Notice.objects.get(id=reference_case_id)
            else:
                case.parent = get_case(str(reference_case_id))
            case.save()
        return ResponseSuccess({"results": case.to_dict()}, http_status=status.HTTP_201_CREATED)


class ApplicationStateAPIView(TradeRemediesApiView):
    """
    Return a data structure representing the current state of an application
    """

    def get(self, request, organisation_id=None, case_id=None, submission_id=None, *args, **kwargs):
        case = None
        if case_id:
            case = get_case(str(case_id))
        submission_type = get_submission_type("Application")
        application_submission = None
        product = None
        source = None
        export_source = None
        documents = []
        if not submission_id:
            # TODO: handle multiple application submissions? Only one active?
            application_submission = (
                Submission.objects.select_related(
                    "case", "type", "status", "organisation", "created_by"
                )
                .filter(case=case, type=submission_type)
                .first()
            )
        if application_submission:
            product = Product.objects.filter(case=case).first()
            source = ExportSource.objects.filter(case=case).first()
            documents = application_submission.get_documents()
        source_task = STATE_INCOMPLETE
        if source or (case.type.id in ALL_COUNTRY_CASE_TYPES and not source):
            source_task = STATE_COMPLETE
        state = {
            "status": {
                "organisation": STATE_COMPLETE if self.organisation else STATE_INCOMPLETE,
                "product": STATE_COMPLETE if product else STATE_INCOMPLETE,
                "source": source_task,
                "documents": STATE_COMPLETE if documents else STATE_INCOMPLETE,
                "review": STATE_COMPLETE
                if application_submission and application_submission.review
                else STATE_INCOMPLETE,
            },
            "organisation": self.organisation.to_dict(),
            "case": case.to_dict(),
            "submission": application_submission.to_dict() if application_submission else None,
            "product": product.to_dict() if product else None,
            "source": source.to_dict() if source else None,
            "documents": [document.to_embedded_dict() for document in documents],
        }

        return ResponseSuccess({"result": state})


class RequestReviewAPIView(TradeRemediesApiView):
    """
    Return a data structure representing the current state of an application
    """

    @transaction.atomic
    def post(
        self,
        request,
        organisation_id=None,
        case_id=None,
        submission_id=None,
        review=None,
        *args,
        **kwargs,
    ):
        case = get_case(str(case_id))
        submission = Submission.objects.get_submission(id=submission_id, case=case)
        submission.status = SubmissionStatus.objects.get(
            id=SUBMISSION_STATUS_APPLICATION_SUBMIT_REVIEW
        )
        submission.received_at = timezone.now()
        submission.received_from = request.user
        submission.review = bool(review)
        submission.save()
        workflow_meta = case.workflow.meta
        case.stage = CaseStage.objects.filter(key="DRAFT_RECEIVED").first()
        case.save()
        # get some workflow meta data
        _draft_received_key = workflow_meta.get("draft_received_key", "DRAFT_RECEIVED")
        _draft_review_key = workflow_meta.get("draft_review_key", "DRAFT_REVIEW")
        _draft_review_days = workflow_meta.get("draft_review_days", 14)
        due_date = timezone.now() + datetime.timedelta(days=_draft_review_days)
        CaseWorkflowState.objects.set_value(case, _draft_received_key, "yes", due_date=due_date)
        CaseWorkflowState.objects.set_next_action(case, _draft_review_key, due_date=due_date)
        # Notify the user the application is in review:
        submission.notify_received(user=request.user)
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=request.user,
            model=case,
            case=case,
            milestone=True,
            data={"message": "Draft submitted for review"},
        )
        return ResponseSuccess({"result": submission.to_dict()})


class TemplateDownloadAPIView(TradeRemediesApiView):
    def get(self, request, case_id, organisation_id, submission_id, document_id, *args, **kwargs):
        submission = Submission.objects.get(case_id=case_id, id=submission_id)
        document = Document.objects.get(id=document_id)
        doc_template = SubmissionDocument.objects.get(submission=submission, document=document)
        if doc_template.downloads == 0:
            doc_template.downloaded = True
            doc_template.save()
        return ResponseSuccess(
            {"result": {"id": str(document.id), "download_url": document.download_url}}
        )


class DocumentDownloadAPIView(TradeRemediesApiView):
    def get(self, request, case_id, organisation_id, submission_id, document_id, *args, **kwargs):
        submission = Submission.objects.get(case_id=case_id, id=submission_id)
        submission_document = submission.submissiondocument_set.filter(
            document__id=document_id, deleted_at__isnull=True
        )
        document = submission_document.document
        submission_document.downloads += 1
        submission_document.save()
        return ResponseSuccess(
            {"result": {"id": str(document.id), "download_url": document.download_url}}
        )


class CaseStatusAPI(TradeRemediesApiView):
    def get(self, request, case_id=None, *args, **kwargs):
        case = get_case(case_id)
        case_workflow = case.workflow
        status = {"stage": case.stage.name, "next_action": None, "next_action_due": None}
        if case_workflow:
            state = case_workflow.get_state()
            status["next_action"] = state.get("meta", {}).get("CURRENT_ACTION")
        return ResponseSuccess({"result": status})


class CaseWorkflowAPI(TradeRemediesApiView):
    """
    Get and set the case workflow response values.
    Each node in the case workflow can be set with a reponse/ack from the user.
    """

    def has_perms(self, request, workflow, key):
        """
        Confirm the authenticated user is allowed to update the specified
        node / key.

        TODO: Also check permissions on parent nodes.
        """
        node = workflow.get_node(key)
        if node:
            perm = node.get("permission")
            if perm:
                perm_parts = perm.split(".")
                if len(perm_parts) > 1:
                    perm = perm_parts[1]
            if perm and perm not in request.user.permission_map:
                return False
        return True

    def get(self, request, case_id=None, *args, **kwargs):
        case = get_case(case_id)
        case_workflow = case.workflow
        if not case_workflow:  # temp code to attach workflow to case
            template = WorkflowTemplate.objects.first()
            case_workflow, created = CaseWorkflow.objects.snapshot_from_template(
                case, template, requested_by=self.user
            )
        state = case_workflow.state_index()
        state["CURRENT_STAGE"] = case.stage and case.stage.name
        state["id"] = str(case_workflow.id)
        return ResponseSuccess(
            {"result": {"state": state, "workflow": case.workflow.as_workflow()}}
        )

    @transaction.atomic
    def post(self, request, case_id=None, node_id=None, node_key=None, *args, **kwargs):
        case = get_case(case_id)
        case.set_user_context(request.user)
        case_state = case.workflow.as_workflow()
        key_index = case_state.key_index
        node_key = [node_key] if node_key else request.data.getlist("nodes", [])
        if node_key:
            # update one or many workflow states
            if case and node_key:
                workflow = case.workflow.as_workflow()
                for key in node_key:
                    if not self.has_perms(request, workflow, key):
                        # report[key] = {'error': 'Access denied'}
                        continue
                    value = request.data.get(key.upper())
                    state, created = CaseWorkflowState.objects.set_value(
                        case=case, key=key, value=value, requested_by=request.user
                    )
                    case_state = case.workflow.get_state()
                    node_spec = case_state.key_index.get(key)
                    if node_spec and node_spec.get("outcome_spec"):
                        case_state.evaluate_outcome(key, case=case, requested_by=request.user)

            state = case.workflow.state_index()
            state["CURRENT_STAGE"] = [case.stage and case.stage.name, None]
            return ResponseSuccess({"result": state}, http_status=status.HTTP_201_CREATED)
        else:
            # Save a complete workflow
            workflow_str = request.data.get("workflow")
            if workflow_str:
                workflow = json.loads(workflow_str)
                case.workflow.replace_workflow(workflow)
                return ResponseSuccess({"result": workflow}, http_status=status.HTTP_201_CREATED)
            else:
                raise InvalidRequestParams("node key was not provided")


class CaseEnumsAPI(TradeRemediesApiView):
    """
    Return all case related enums and relevant support data sets.
    A case id can be provided to return certain case specific enums, such as which submission types
    a user can create.
    """

    def get(self, request, case_id=None, *args, **kwargs):
        case = None
        available_submission_types = {}
        case_id = case_id or request.query_params.get("case_id")
        case_types = CaseType.objects.select_related("workflow").all().order_by("order", "name")
        available_review_types = []
        case_stages = CaseStage.objects.select_related("type").all().order_by("order", "name")
        case_milestone_types = [
            (ms_type, CASE_MILESTONE_DATES[ms_type]) for ms_type in CASE_MILESTONE_DATES
        ]
        submission_statuses = [
            sub_status.to_dict()
            for sub_status in SubmissionStatus.objects.select_related("type").all().order_by("id")
        ]
        sectors = Sector.objects.all().order_by("id")
        roles = [role.to_dict() for role in CaseRole.objects.all().order_by("id")]
        statuses_by_type = deep_index_items_by(submission_statuses, "type/key")
        archive_reasons = ArchiveReason.objects.all().order_by("name")
        direction_kwargs = (
            {"direction__in": [int(request.query_params["direction"]), DIRECTION_BOTH]}
            if "direction" in request.query_params
            else {}
        )
        if case_id:
            case = Case.objects.get_case(id=case_id)
            submission_types = SubmissionType.objects.get_available_submission_types_for_case(
                case, direction_kwargs
            )
            available_review_types = CaseType.objects.available_case_review_types(case)
        else:
            submission_types = (
                SubmissionType.objects.select_related("requires")
                .filter(**direction_kwargs)
                .order_by("order", "name")
            )
        _submission_types = [
            submission_type.to_dict(case=case) for submission_type in submission_types
        ]
        _response_submission_types = [
            submission_type
            for submission_type in _submission_types
            if submission_type.get("requires")
        ]
        available_submission_types = {
            subtype["id"]: subtype["has_requirement"] for subtype in _submission_types
        }

        return ResponseSuccess(
            {
                "result": {
                    "roles": roles,
                    "role_index": key_by(roles, "key"),
                    "approval_role_id": SystemParameter.get("AWAITING_APPROVAL_ROLE_ID"),
                    "case_types": [case_type.to_dict() for case_type in case_types],
                    "case_stages": [case_stage.to_dict() for case_stage in case_stages],
                    "submission_types": _submission_types,
                    "statuses_by_type": statuses_by_type,
                    "submission_statuses": submission_statuses,
                    "sectors": [sector.to_dict() for sector in sectors],
                    "countries": list(countries),
                    "case_worker_allowed_submission_types": [
                        submission_type.to_dict()
                        for submission_type in submission_types
                        if submission_type.direction == DIRECTION_TRA_TO_PUBLIC
                    ],
                    "public_submission_types": [
                        submission_type.to_dict()
                        for submission_type in submission_types
                        if submission_type.direction == DIRECTION_BOTH
                    ],
                    "submission_status_map": SubmissionType.submission_status_map(),
                    "available_submission_types": available_submission_types,
                    "archive_reasons": [
                        archive_reason.to_dict() for archive_reason in archive_reasons
                    ],
                    "response_submission_types": _response_submission_types,
                    "milestone_types": case_milestone_types,
                    "available_review_types": available_review_types,
                    "safe_colours": SAFE_COLOURS,
                }
            }
        )


class CaseOrganisationsAPIView(TradeRemediesApiView):
    """
    Return all the organisations the requesting user is associated with
    for a case id.
    """

    def get(self, request, case_id):
        case = Case.objects.get(id=case_id)
        user_case_orgs = UserCase.objects.filter(user=request.user, case=case)
        # case_organisations = OrganisationCaseRole.objects.filter(
        #     case=case,
        #     organisation__organisationuser__user=request.user
        # )
        return ResponseSuccess(
            {
                "results": [
                    user_case_org.organisation.to_embedded_dict()
                    for user_case_org in user_case_orgs
                    if user_case_org.organisation
                ]
            }
        )


class SubmissionTypeAPI(TradeRemediesApiView):
    def get(self, request, submission_type_id):
        sub_type = SubmissionType.objects.get(id=submission_type_id)
        return ResponseSuccess({"result": sub_type.to_dict()})


class ThirdPartyInvitesAPI(TradeRemediesApiView):
    """
    Return third party invite submissions for an organisation
    """

    def get(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        invite_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_INVITE_3RD_PARTY)
        _filter_kwargs = {}
        if organisation_id:
            _filter_kwargs["organisation"] = Organisation.objects.get(id=organisation_id)
            _filter_kwargs["created_by"] = request.user
        if case_id:
            _filter_kwargs["case"] = Case.objects.get(id=case_id)
        submissions = (
            Submission.objects.select_related()
            .filter(type=invite_type, deleted_at__isnull=True, **_filter_kwargs)
            .order_by("created_at")
        )
        return ResponseSuccess(
            {"results": [submission.to_embedded_dict() for submission in submissions]}
        )


class CaseMilestoneDatesAPI(TradeRemediesApiView):
    def get(self, request, case_id):
        case = get_case(case_id)
        milestones = case.case_milestone_index()
        return ResponseSuccess(
            {
                "results": [
                    {
                        "key": mskey,
                        "name": CASE_MILESTONE_DATES[mskey],
                        "case": {"id": str(case_id), "name": case.name,},
                        "date": milestones[mskey].strftime(settings.API_DATE_FORMAT)
                        if milestones[mskey]
                        else None,
                    }
                    for mskey in milestones
                ]
            }
        )

    def post(self, request, case_id, milestone_key):
        case = get_case(case_id)
        date = request.data.get("date")
        CaseWorkflowState.objects.set_value(
            case=case, key=milestone_key, value=date, requested_by=request.user, mutate=False
        )
        return self.get(request, case_id)


class CaseReviewTypesAPI(TradeRemediesApiView):
    def get(self, request, case_id):
        case = Case.objects.get(id=case_id)
        summary = request.query_params.get("summary")
        available_review_types = CaseType.objects.available_case_review_types(case)
        return ResponseSuccess({"results": available_review_types})


class NoticesAPI(TradeRemediesApiView):
    def get(self, request, notice_id=None):
        if notice_id:
            notice = Notice.objects.get(id=notice_id)
            return ResponseSuccess({"result": notice.to_dict()})
        all_notices = request.query_params.get("all_notices", "true") == "true"
        notices = Notice.objects.filter()
        if all_notices:
            notices = notices.filter(
                Q(terminated_at__isnull=True) | Q(terminated_at__gte=timezone.now().date())
            )
        notices = notices.order_by("reference")
        return ResponseSuccess({"results": [notice.to_dict() for notice in notices]})

    def post(self, request, notice_id=None, case_id=None):
        name = request.data.get("name")
        reference = request.data.get("reference")
        terminated_at = request.data.get("terminated_at")
        published_at = request.data.get("published_at")
        case_type_id = request.data.get("case_type_id")
        review_case_id = request.data.get("review_case_id")
        if notice_id:
            notice = Notice.objects.get(id=notice_id)
        else:
            notice = Notice()
        notice.name = name
        notice.reference = reference
        try:
            notice.terminated_at = parser.parse(terminated_at).date() if terminated_at else None
        except Exception:
            pass
        try:
            notice.published_at = parser.parse(published_at).date() if published_at else None
        except Exception:
            pass
        notice.case_type = CaseType.objects.get(id=int(case_type_id)) if case_type_id else None
        notice.review_case = Case.objects.get(id=review_case_id) if review_case_id else None
        notice.save()
        return ResponseSuccess({"result": notice.to_dict()})
