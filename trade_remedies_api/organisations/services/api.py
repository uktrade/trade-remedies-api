import json
from django.utils import timezone
from django.conf import settings
from core.services.base import TradeRemediesApiView, ResponseSuccess
from core.services.exceptions import NotFoundApiExceptions
from core.utils import (
    public_login_url,
    filter_dict,
    get,
    pluck,
)
from core.constants import TRUTHFUL_INPUT_VALUES
from audit import AUDIT_TYPE_EVENT
from audit.utils import audit_log
from django.db import transaction
from django.db.models import Count, Q

from rest_framework import status
from organisations.models import Organisation
from organisations.constants import REJECTED_ORG_CASE_ROLE
from cases.models import Case, get_case, Submission
from contacts.models import Contact, CaseContact
from security.models import OrganisationUser, OrganisationCaseRole, CaseRole, UserCase
from titlecase import titlecase
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER


class OrganisationsAPIView(TradeRemediesApiView):
    """
    Return all or one organisations for a user.
    A user has access to the organisation record if they are a direct user of the organisation
    or if they are representing it in a case

    `GET /organisations/`
    Return all organisations the requesting user is allowed
    `GET /organisations/{organisation_id}`
    Return a single organisation details if the user is allowed access to it

    `POST /organisations/`

    """

    def get(self, request, organisation_id=None, case_id=None, *args, **kwargs):
        is_tra = request.user.is_tra()
        gov_body = request.query_params.get("gov_body", "false") in TRUTHFUL_INPUT_VALUES
        fields = request.query_params.get("fields")
        case = None
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Case not found or access denied")
        if gov_body:
            organisations = Organisation.objects.filter(gov_body=True).order_by("name")
            return ResponseSuccess(
                {"results": [organisation.to_embedded_dict() for organisation in organisations]}
            )
        elif organisation_id:
            try:
                organisation = Organisation.objects.get(id=organisation_id)
                org_data = organisation.to_dict(case=case)
                if case_id:
                    case_role = organisation.get_case_role(get_case(case_id))
                    org_data["case_role"] = case_role.to_dict() if case_role else None
                return ResponseSuccess({"result": org_data})
            except Organisation.DoesNotExist:
                raise NotFoundApiExceptions("Organisation does not exist or access is denied")
        elif is_tra:
            organisations = Organisation.objects.filter(deleted_at__isnull=True)
            return ResponseSuccess(
                {"results": [org.to_dict(fields=fields) for org in organisations]}
            )

        else:
            organisations = OrganisationUser.objects.filter(user=request.user)
        return ResponseSuccess(
            {"results": [org_user.organisation.to_dict() for org_user in organisations]}
        )

    @transaction.atomic
    def post(
        self, request, organisation_id=None, case_id=None, organisation_type=None, *args, **kwargs
    ):
        result = {}
        case = None
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise NotFoundApiExceptions("Case not found or access denied")
        organisation_type = organisation_type or request.data.get("organisation_type")
        sent_org_id = request.data.get("organisation_id")
        if sent_org_id:
            # This is a create org in case, but supplyimg the org id - so just assign
            organisation = Organisation.objects.get(id=sent_org_id)
        else:
            json_data = json.loads(request.data.get("json_data") or "{}")
            json_data["created_as_type"] = organisation_type
            organisation = Organisation.objects.create_or_update_organisation(
                user=request.user,
                name=request.data.get("organisation_name"),
                trade_association=request.data.get("trade_association") or False,
                address=request.data.get("organisation_address"),
                post_code=request.data.get("organisation_post_code"),
                country=request.data.get("organisation_country"),
                organisation_id=organisation_id,
                json_data=json_data,
                case=case,
                **filter_dict(
                    request.data,
                    [
                        "vat_number",
                        "eori_number",
                        "duns_number",
                        "organisation_website",
                        "companies_house_id",
                    ],
                ),
            )
        if case:
            organisation.assign_case(case, organisation_type, user=request.user)

        merge_with = request.data.get("merge_with")
        try:
            if merge_with:
                merge_org = Organisation.objects.get(id=merge_with)
                parameter_map = json.loads(request.data.get("parameter_map", "[]"))
                Organisation.objects.merge_organisation_records(
                    organisation,
                    merge_with=merge_org,
                    parameter_map=parameter_map,
                    merged_by=request.user,
                    notify=True,
                )
        except ValueError as e:
            result["errors"] = [f"Unable to merge ({str(e)})"]

        result["organisation"] = organisation.to_dict()

        return ResponseSuccess({"result": result}, http_status=status.HTTP_201_CREATED)

    @transaction.atomic
    def delete(self, request, organisation_id, case_id=None, *args, **kwargs):
        """
        Delete all org case roles from this org, then mark as deleted
        """
        organisation = Organisation.objects.get(id=organisation_id)
        ocr = OrganisationCaseRole.objects.filter(organisation=organisation)
        casecontacts = organisation.casecontact_set.all()
        invitations = organisation.invitations.all()
        # real-delete any case roles and case contact references
        ocr.delete()
        casecontacts.delete()
        # mark delete all invites
        for invitation in invitations:
            invitation.delete()
        organisation.delete()
        return ResponseSuccess(
            {"result": organisation.to_dict()}, http_status=status.HTTP_201_CREATED
        )


class OrganisationUsersAPI(TradeRemediesApiView):
    """
    Get the users of this organisation
    """

    toggle_admin = False

    def get(self, request, organisation_id, *args, **kwargs):
        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation does not exist or access is denied")

        case_id = request.GET.get("case_id")
        if case_id:
            # Get from user-org-case
            user_cases = UserCase.objects.filter(organisation_id=organisation_id, case_id=case_id)
            case_contacts = CaseContact.objects.filter(
                organisation_id=organisation_id, case_id=case_id
            )
            primary_contact_ids = {}
            for cc in case_contacts:
                if cc.primary:
                    primary_contact_ids[str(cc.contact.id)] = True
            results = []
            for user_case in user_cases:
                _dict = user_case.to_dict()
                (_dict.get("user") or {})["contact_id"] = user_case.user.contact.id
                if primary_contact_ids.get(str(user_case.user.contact.id)):
                    _dict["primary"] = True
                results.append(_dict)
            return ResponseSuccess({"results": results})

        return ResponseSuccess({"results": [user.to_user_dict() for user in organisation.users]})

    def post(self, request, organisation_id, user_id=None, *args, **kwargs):
        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation does not exist or access is denied")
        if user_id:
            org_user = organisation.users.get(user_id=user_id)
            if org_user and self.toggle_admin:
                org_user.user.toggle_role(SECURITY_GROUP_ORGANISATION_OWNER)
        return ResponseSuccess({"result": org_user.to_user_dict()})


class OrganisationContactsAPI(TradeRemediesApiView):
    """
    Gets all contacts for this organisation flagged as approprate
    """

    def get(self, request, organisation_id, case_id=None, *args, **kwargs):  # noqa: C901
        contacts = {}
        case = Case.objects.get(id=case_id) if case_id else None

        def add_contact(case_contact, case):
            if get(case_contact, "contact").address != "redacted":
                contact_id = str(get(case_contact, "contact").id)
                if contact_id not in contacts:
                    contact = get(case_contact, "contact")
                    contacts[contact_id] = contact.to_dict(case)
                    contacts[contact_id]["cases"] = {}
                    if get(contacts[contact_id], "user"):
                        try:
                            organisation = contact.user.organisation.organisation
                            contacts[contact_id]["user"]["organisation"] = {"id": organisation.id}
                        except AttributeError:
                            pass
                if case_contact.get("loa"):
                    contacts[contact_id]["loa"] = True
                if case_contact.get("organisation_contact"):
                    contacts[contact_id]["organisation_contact"] = True
                if case_contact.get("case_contact"):
                    contacts[contact_id]["case_contact"] = True
                case = get(case_contact, "case")
                if case:
                    cc = contacts[contact_id]["cases"].get(str(case.id)) or {"name": case.name}
                    cc.update(
                        {
                            k: v
                            for k, v in case_contact.items()
                            if v is not None
                            and k in ["primary", "loa", "name", "in_case", "case_contact"]
                        }
                    )
                    contacts[contact_id]["cases"][str(case.id)] = cc

        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation does not exist or access is denied")

        users = organisation.users  # get the users from user->org

        # Add contacts that are related via a user-case with this org - representing
        if not request.query_params.get("exclude_indirect"):
            user_cases = UserCase.objects.filter(
                organisation=organisation,
            )
            for user_case in user_cases:
                add_contact(
                    {
                        "contact": user_case.user.contact,
                        "case": user_case.case,
                        "primary": False,
                        "in_case": True,
                    },
                    case=case,
                )
            # Add case contacts if we don't have them already
            case_contacts = CaseContact.objects.filter(
                organisation=organisation,
                contact__deleted_at__isnull=True,
            )
            for case_contact in case_contacts:
                add_contact(
                    {
                        "contact": case_contact.contact,
                        "case": case_contact.case,
                        "primary": case_contact.primary,
                        "case_contact": True,
                    },
                    case=case,
                )
        # Add LOA contacts
        for caserole in OrganisationCaseRole.objects.filter(
            organisation=organisation, auth_contact__deleted_at__isnull=True
        ):
            if caserole.auth_contact:
                add_contact(
                    {
                        "contact": caserole.auth_contact,
                        "loa": True,
                    },
                    case=case,
                )
        # Add contacts that are attached directly to the organisation
        for org_contact in organisation.contacts:
            add_contact(
                {
                    "contact": org_contact,
                    "organisation_contact": True,
                },
                case=case,
            )

        return ResponseSuccess({"results": contacts.values()})


class OrganisationCaseSampleToggleAPI(TradeRemediesApiView):
    """
    Toggle the sampled flag for this organisation's role in the case.
    """

    def post(self, request, case_id, organisation_id, *args, **kwargs):
        try:
            case = Case.objects.get(id=case_id)
            organisation = Organisation.objects.get(id=organisation_id)
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("Case not found or access denied")
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation not found or access denied")
        sampled = request.data.get("sampled")
        org_case_role = OrganisationCaseRole.objects.get(case=case, organisation=organisation)
        org_case_role.sampled = sampled if sampled is not None else not org_case_role.sampled
        org_case_role.save()
        sampled_str = "sampled" if org_case_role.sampled else "non-sampled"
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=request.user,
            model=organisation,
            case=case,
            milestone=True,
            data={"message": f"{organisation.name} flagged as {sampled_str}"},
        )
        return ResponseSuccess(
            {
                "result": {
                    "organisation_id": organisation_id,
                    "case_id": case_id,
                    "sampled": org_case_role.sampled,
                    "organisation": organisation.to_embedded_dict(),
                }
            },
            http_status=status.HTTP_201_CREATED,
        )


class OrganisationNonResponsiveToggleAPI(TradeRemediesApiView):
    """
    Toggle the non_responsive flag for this organisation's role in the case.
    """

    def post(self, request, case_id, organisation_id, *args, **kwargs):
        try:
            case = Case.objects.get(id=case_id)
            organisation = Organisation.objects.get(id=organisation_id)
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("Case not found or access denied")
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation not found or access denied")
        non_responsive = request.data.get("non_responsive")
        org_case_role = OrganisationCaseRole.objects.get(case=case, organisation=organisation)
        org_case_role.non_responsive = (
            non_responsive if non_responsive is not None else not org_case_role.non_responsive
        )
        org_case_role.save()
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=request.user,
            model=organisation,
            case=case,
            milestone=True,
            data={"message": f"{organisation.name} marked unresponsive"},
        )
        return ResponseSuccess(
            {
                "result": {
                    "organisation_id": organisation_id,
                    "case_id": case_id,
                    "non_responsive": org_case_role.non_responsive,
                    "organisation": organisation.to_embedded_dict(),
                }
            },
            http_status=status.HTTP_201_CREATED,
        )


class OrganisationApprovalNotifyAPI(TradeRemediesApiView):
    """
    Approve the organisation into the case, assign its role and notify the contact
    """

    @transaction.atomic
    def post(self, request, case_id, organisation_id, action, *args, **kwargs):
        values = {key: request.data.get(key) for key in request.data.keys()}
        contact_id = values.pop("contact_id")
        organisation = Organisation.objects.get(id=organisation_id)
        case = Case.objects.get(id=case_id)
        values["case_number"] = case.reference
        values["case_name"] = case.name
        values["login_url"] = public_login_url()
        values["company_name"] = titlecase(organisation.name)
        user_granted_access = None

        if action in ("approve", "change"):
            role_key = values.pop("organisation_type", None)
            role = CaseRole.objects.get(key=role_key)
            values["role"] = role.contributor_or_interested()
            if action == "change":
                previous_role = case.organisationcaserole_set.filter(
                    organisation=organisation
                ).first()
                values["previous_role"] = previous_role.role.contributor_or_interested()
                values["new_role"] = values["role"]
            try:
                contact = Contact.objects.select_related("userprofile", "organisation").get(
                    id=contact_id, casecontact__case=case, casecontact__organisation=organisation
                )
            except Contact.DoesNotExist:
                contact = Contact.objects.select_related("userprofile", "organisation").get(
                    id=contact_id
                )
                CaseContact.objects.get_or_create(
                    contact=contact, case=case, organisation=organisation
                )
            caserole, created = organisation.assign_case(case, role)
            user_granted_access = caserole.created_by
            # assign the user registering access to the case
            case.assign_user(
                user_granted_access, created_by=request.user, organisation=organisation
            )
            message = f"Organisation {organisation.name} approved as {role.name}"
        else:
            role = CaseRole.objects.get(key="rejected")
            values["new_role"] = "rejected"
            caserole, created = organisation.assign_case(case, role)
            user_granted_access = caserole.created_by
            contact = Contact.objects.select_related("userprofile", "organisation").get(
                id=contact_id
            )
            message = f"Organisation {organisation.name} was rejected"
        values["full_name"] = contact.name
        # Send the message
        if action == "approve" or values.get("previous_role") != values.get("new_role"):
            organisation.notify_approval_status(action, contact, values, case, request.user)
        if action == "approve":
            audit_log(
                audit_type=AUDIT_TYPE_EVENT,
                user=request.user,
                model=case,
                case=case,
                milestone=True,
                data={
                    "action": "assign_user",
                    "message": f"User {user_granted_access} "
                    f"was granted access to the case for {organisation}",
                },
            )
        return ResponseSuccess({"result": values})


class SubmissionApprovalNotifyAPI(TradeRemediesApiView):
    """
    Given a ROI type submission with all the necessary data furnished in a JSON blob,
    a) create/update orgcaserole object
    b) create usercaseorg object to give user access (submission creator)
    c) send notification
    """

    @transaction.atomic
    def post(self, request, submission_id, *args, **kwargs):
        submission = Submission.objects.get(id=submission_id)
        case = submission.case
        organisation = submission.organisation
        caserole = OrganisationCaseRole.objects.get(case=case, organisation=organisation)
        json_data = submission.deficiency_notice_params or {}  # this has most of what we need
        submission.deficiency_notice_params = json_data
        auth_contact_details = None

        values = {
            "case_number": case.reference,
            "case_name": case.name,
            "login_url": public_login_url(),
            "company_name": titlecase(organisation.name),
            "full_name": submission.contact.name,
            "role": caserole.role.name,
        }

        case.assign_user(submission.created_by, created_by=request.user, organisation=organisation)
        if json_data.get("org_verify") == "verified":
            case.confirm_user_case(
                submission.created_by, created_by=request.user, organisation=organisation
            )

        # Work out whether it's an accept or reject
        # If either the org or contact org is rejected, or the decision is reject -> reject
        approve = (
            json_data.get("org_verify") != "rejected"
            and json_data.get("contact_org_verify") != "rejected"
        )
        # Mark bad organisations
        approval_to_case = caserole.approved_at
        if json_data.get("org_verify") == "rejected":
            organisation.fraudulent = True
            organisation.save()
            approve = False
        result = organisation.notify_approval_status(
            "approve" if approval_to_case else "deny",
            submission.contact,
            values,
            case,
            request.user,
        )
        # Mark as complete
        json_data["notification_sent_at"] = timezone.now().strftime(settings.API_DATETIME_FORMAT)
        submission.save()
        return ResponseSuccess({"result": "ok"})


class OrganisationCaseRoleAPI(TradeRemediesApiView):
    """
    Set the role of an organisation in a case
    """

    verify = False
    post_type = None

    def get(self, request, case_id, organisation_id):
        organisation = Organisation.objects.get(id=organisation_id)
        case = Case.objects.get(id=case_id)
        try:
            caserole = OrganisationCaseRole.objects.get(case=case, organisation=organisation)
        except:
            return ResponseSuccess({"result": None})
        return ResponseSuccess({"result": caserole.to_dict()})

    @transaction.atomic  # noqa: C901
    def post(self, request, case_id, organisation_id, role_key=None, *args, **kwargs):
        sampled = request.data.get("sampled", "true") == "true"
        organisation = Organisation.objects.get(id=organisation_id)
        case = Case.objects.get(id=case_id)

        if role_key:
            role = CaseRole.objects.get(key=role_key)
        else:
            # Assign a default role if role_key is not provided
            role = CaseRole.objects.get(key="applicant")

        case_role, _ = OrganisationCaseRole.objects.get_or_create(
            case=case, organisation=organisation, defaults={"role": role}
        )

        # Add/update LOA contact
        if self.post_type == "loa":
            # Create a contact to store LOA details if present
            loa_updated = False
            loa_contact = case_role.auth_contact
            auth_contact_details = (
                pluck(
                    request.data,
                    ["LOA_contact_id", "name", "org_name", "email", "phone", "address"],
                )
                or {}
            )
            contact_id = auth_contact_details.get("LOA_contact_id")
            email = auth_contact_details.get("email")
            if not loa_contact or loa_contact.id != contact_id:
                # If we get an id, stick with that
                if contact_id:
                    try:
                        loa_contact = Contact.objects.get(id=contact_id)
                    except Exception:
                        pass
                if email:
                    # No contact so try to find one based on email
                    try:
                        loa_contact = Contact.objects.get(email__iexact=email)
                    except Exception:
                        loa_contact = Contact.objects.create(created_by=request.user)
                    # Create a new org if there isn't one, or it doesn't match supplied name
                    loa_org_name = auth_contact_details.get("org_name")
                    loa_contact.organisation = organisation

                    for field, value in auth_contact_details.items():
                        if (
                            value
                            and hasattr(loa_contact, field)
                            and getattr(loa_contact, field) != value
                        ):
                            setattr(loa_contact, field, value)
                            loa_updated = True
                    if loa_updated:
                        loa_contact.save()
                    # write back
                case_role.auth_contact = loa_contact
                case_role.save()

            return ResponseSuccess({"result": {"success": case_role.to_dict()}})
        # Approve into case and set case role
        approve = request.data.get("approve")
        if approve:
            if approve == "accept":
                if not case_role.approved_at:
                    case_role.approved_at = timezone.now()
                    case_role.approved_by = request.user
                    case_role.save()
            elif approve == "reject":
                role_key = "rejected"
                if case_role.approved_at:
                    case_role.approved_at = None
                    case_role.approved_by = None
                    case_role.save()

        if self.verify:
            case_role.validated_by = request.user
            case_role.validated_at = timezone.now()
            case_role.save()
            return ResponseSuccess({"result": {"validated_at": case_role.to_dict()}})
        role = CaseRole.objects.get(key=role_key)
        case_role.role = role
        case_role.sampled = sampled
        case_role.save()
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=request.user,
            model=case,
            case=case,
            milestone=True,
            data={"message": f"The role of {organisation} was set to {role} in case {case.name}"},
        )
        return ResponseSuccess({"result": {"new_role": role.to_dict()}})

    @transaction.atomic
    def delete(self, request, case_id, organisation_id, *args, **kwargs):
        # Remove from case
        organisation = Organisation.objects.get(id=organisation_id)
        case = Case.objects.get(id=case_id)
        case_role, _ = OrganisationCaseRole.objects.get_or_create(
            case=case, organisation=organisation
        )
        case_role.delete()
        audit_log(
            audit_type=AUDIT_TYPE_EVENT,
            user=request.user,
            model=case,
            case=case,
            milestone=True,
            data={"message": f"Organisation {organisation} was removed from case {case.name}"},
        )
        return ResponseSuccess({"result": organisation.to_dict()})


class DuplicateOrganisationsAPI(TradeRemediesApiView):
    """
    Surface organisations with duplicate names
    """

    def get(self, request, *args, **kwargs):
        limit = request.query_params.get("limit")
        if limit and float(limit) > 1:
            limit = float(limit) / 100
        duplicates = (
            Organisation.objects.values("name").annotate(count=Count("name")).filter(count__gt=1)
        )
        similar = Organisation.objects.find_similar_organisations(limit=limit)
        return ResponseSuccess(
            {
                "results": {
                    "duplicates": duplicates,
                    "similar": similar,
                }
            }
        )


class OrganisationMatchingAPI(TradeRemediesApiView):
    def add_usercase_to_target(self, target, org_id, usercase, org_case_roles_by_org_case):
        target.setdefault(org_id, [])

        caserole = org_case_roles_by_org_case.get(
            str(usercase.case.id) + ":" + str(usercase.organisation.id)
        )
        if caserole and (
            caserole.role.key not in (REJECTED_ORG_CASE_ROLE) or caserole.validated_at
        ):
            target[org_id].append(
                {
                    "case": usercase.case.to_minimal_dict(),
                    "user": usercase.user.to_embedded_dict() if hasattr(usercase, "user") else None,
                    "organisation": usercase.organisation.to_embedded_dict(),
                    "usercase": usercase.to_dict(),
                    "caserole": caserole.to_embedded_dict(),
                }
            )

    def get(self, request, organisation_id=None):  # noqa: C901
        # Get a list of matching orgs
        all_details = request.GET.get("with_details", "all")
        query = Q(id=None)
        if organisation_id:
            organisation = Organisation.objects.get(id=organisation_id)
            for field in [
                "companies_house_id",
                "vat_number",
                "eori_number",
                "duns_number",
                "organisation_website",
            ]:
                field_val = getattr(organisation, field)
                if field_val:
                    query.add(Q(**{field: field_val}), Q.OR)
        else:
            # we should be given a name and maybe reg number to match on
            for field in ["companies_house_id", "name"]:
                field_val = request.GET.get(field)
                if field_val:
                    query.add(Q(**{field: field_val}), Q.OR)

        query.add(Q(deleted_at__isnull=True), Q.AND)
        organisation_matches = Organisation.objects.filter(query)
        if all_details != "none":
            detail_matches = organisation_matches
            # If all_details parameter is set false,
            # only the details on the primary org will be furnished
            if all_details != "all" and organisation_id:
                detail_matches = Organisation.objects.filter(id=organisation_id)

            organisation_cases = OrganisationCaseRole.objects.filter(
                organisation__in=detail_matches
            )
            organisations_users = OrganisationUser.objects.filter(organisation__in=detail_matches)

            organisation_indirect_usercases = UserCase.objects.filter(
                user__in=organisations_users.values("user").distinct()
            )
            organisation_indirect_orgs = OrganisationCaseRole.objects.filter(
                organisation__in=organisation_indirect_usercases.values("organisation").distinct()
            )
            organisation_direct_usercases = UserCase.objects.filter(organisation__in=detail_matches)

            # build index of usercase on user_id
            user_idx_org_usercases = {}
            for ouc in organisation_indirect_usercases:
                user_idx_org_usercases.setdefault(ouc.user.id, [])
                user_idx_org_usercases[ouc.user.id].append(ouc)

            # build index of org_case_roles
            org_case_roles_by_org_case = {}
            for ocr in organisation_indirect_orgs:
                key = str(ocr.case.id) + ":" + str(ocr.organisation.id)
                org_case_roles_by_org_case[key] = ocr
            for ocr in organisation_cases:
                key = str(ocr.case.id) + ":" + str(ocr.organisation.id)
                org_case_roles_by_org_case[key] = ocr

            user_by_org = {}
            usercase_by_org = {}
            ocr_by_org = {}
            for ou in organisations_users:
                _dict = {"id": ou.user.id, "name": ou.user.name, "email": ou.user.email}
                org_id = str(ou.organisation.id)
                user_by_org.setdefault(org_id, [])
                user_by_org[org_id].append(_dict)
                usercases = user_idx_org_usercases.get(ou.user.id)
                for uc in usercases or []:
                    if uc.organisation and str(uc.organisation.id) != org_id:
                        self.add_usercase_to_target(
                            usercase_by_org, org_id, uc, org_case_roles_by_org_case
                        )
            for uc in organisation_direct_usercases:
                self.add_usercase_to_target(
                    ocr_by_org, str(uc.organisation.id), uc, org_case_roles_by_org_case
                )
            for oc in organisation_cases:
                self.add_usercase_to_target(
                    ocr_by_org, str(oc.organisation.id), oc, org_case_roles_by_org_case
                )

        org_matches_dict = []
        for org in organisation_matches:
            if all_details != "none":
                _dict = org.to_dict()
                _dict.update(
                    {
                        "cases": ocr_by_org.get(str(org.id)),
                        "indirect_cases": usercase_by_org.get(str(org.id)),
                        "users": user_by_org.get(str(org.id)),
                    }
                )
            else:
                _dict = org.to_embedded_dict()
                _dict["json_data"] = org.json_data
            org_matches_dict.append(_dict)

        return ResponseSuccess(
            {
                "result": sorted(
                    org_matches_dict,
                    key=lambda su: str(su.get("id")) == str(organisation_id),
                    reverse=True,
                )
            }
        )


class OrganisationUserCaseAPI(TradeRemediesApiView):
    """
    Get the auth contact details from all case-user-org objects for this organisation
    """

    def get(self, request, organisation_id=None):
        organisation_usercases = UserCase.objects.filter(organisation__id=organisation_id)

        return ResponseSuccess(
            {"results": [usercase.to_dict() for usercase in organisation_usercases]}
        )


class OrganisationRejectAPI(TradeRemediesApiView):
    """
    Set the org to fraudulent
    """

    @transaction.atomic
    def post(self, request, organisation_id, set=True):
        organisation = Organisation.objects.get(id=organisation_id)
        organisation.fraudulent = set
        organisation.save()
        rejected_role = CaseRole.objects.get(key="rejected")
        # Set all caseroles for this org to rejected to stop further case participation
        for ocr in OrganisationCaseRole.objects.filter(organisation_id=organisation_id):
            ocr.role = rejected_role
            ocr.save()
        return ResponseSuccess({"result": organisation.to_dict()})


class OrganisationLookupAPI(TradeRemediesApiView):
    def get(self, request, *args, **kwargs):
        names = request.GET.getlist("name")
        case_summary = request.GET.get("cases", "false") in TRUTHFUL_INPUT_VALUES
        upper_names = [n.upper() for n in names]
        organisations = Organisation.objects.filter(name__in=upper_names)
        results = []
        for org in organisations:
            _item = org.to_embedded_dict()
            if case_summary:
                cases = Case.objects.filter(organisationcaserole__organisation=org)
                _item["cases"] = [{"id": str(case.id), "name": case.name} for case in cases]
            results.append(_item)
        return ResponseSuccess({"results": results})
