import json
import mimetypes

from rest_framework.response import Response

from .auth.serializers import EmailSerializer
from .base import ResponseError, TradeRemediesApiView, ResponseSuccess
from .exceptions import InvalidRequestParams, IntegrityErrorRequest, NotFoundApiExceptions
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from feedback.models import FeedbackForm
from audit import AUDIT_TYPE_NOTIFY
from core.feature_flags import is_enabled, FeatureFlagNotFound
from core.models import User, SystemParameter, JobTitle
from core.utils import convert_to_e164, pluck, public_login_url
from core.notifier import get_template, get_preview, notify_footer, notify_contact_email
from core.constants import TRUTHFUL_INPUT_VALUES
from core.tasks import send_mail
from core.feedback import feedback_export
from organisations.models import Organisation
from invitations.models import Invitation
from security.exceptions import InvalidAccess
from security.constants import (
    GROUPS,
    SECURITY_GROUP_SUPER_USER,
    SECURITY_GROUPS_TRA_ADMINS,
    SECURITY_GROUPS_TRA,
    SECURITY_GROUPS_PUBLIC,
    SECURITY_GROUP_ORGANISATION_OWNER,
)


class ApiHealthView(APIView):
    """
    Perform a healthcheck on the API and return a status report.

    `GET /api/v1/health/`

    """

    authentication_classes = []

    def get(self, request, *args, **kwargs):
        """
        Return current API health status
        """
        try:
            database_ok = bool(User.objects.first())
        except Exception:
            database_ok = False
        try:
            cache.set("health-check", True, 10)
            cache_ok = cache.get("health-check") is True
            cache.delete("health-check")
        except Exception:
            cache_ok = False
        return ResponseSuccess(
            {
                "result": {
                    "health": "OK",
                    "database": "OK" if database_ok else "ERROR",
                    "cache": "OK" if cache_ok else "ERROR",
                }
            }
        )


class SecurityGroupsView(TradeRemediesApiView):
    """
    Return all available security groups

    `GET /security/groups`
    """

    def get(self, request, user_group=None, *args, **kwargs):
        group_limiter = (
            SECURITY_GROUPS_TRA if user_group == "caseworker" else SECURITY_GROUPS_PUBLIC
        )
        groups = [item for item in GROUPS[1:] if item[0] in group_limiter]
        return ResponseSuccess({"results": groups})


class GetUserEmailAPIView(TradeRemediesApiView):
    def get(self, request, user_email, *args, **kwargs):
        serializer = EmailSerializer(data={"email": user_email})
        if serializer.is_valid():
            return ResponseSuccess({"result": serializer.user.to_dict()})
        else:
            return ResponseError(
                error="User not found",
                http_status=status.HTTP_404_NOT_FOUND,
            )


class UserApiView(TradeRemediesApiView):
    allowed_groups = {
        "GET": SECURITY_GROUPS_TRA,
        "POST": SECURITY_GROUPS_TRA_ADMINS,
        "DELETE": SECURITY_GROUPS_TRA_ADMINS,
    }
    required_keys = ["email", "password"]

    def get(self, request, user_id=None, user_group=None, *args, **kwargs):
        """
        Return all users or a specific one by id
        """
        if user_id is not None:
            user = User.objects.get(id=user_id)
            return ResponseSuccess({"result": user.to_dict()})
        else:
            groups = request.query_params.getlist("groups")
            users = (
                User.objects.exclude(groups__name=SECURITY_GROUP_SUPER_USER)
                .exclude(userprofile__isnull=True)
                .exclude(deleted_at__isnull=False)
            )
            if groups:
                users = users.filter(groups__name__in=groups)
            if user_group == "caseworker":  # general user group caseworker/public
                users = users.filter(groups__name__in=SECURITY_GROUPS_TRA)
            elif user_group == "public":
                users = users.filter(groups__name__in=SECURITY_GROUPS_PUBLIC)
            return ResponseSuccess(
                {
                    "results": [
                        # user.to_embedded_dict(groups=True) for user in users
                        user.to_dict()
                        for user in users
                    ]
                }
            )

    @transaction.atomic
    def post(self, request, user_id=None, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")
        roles = request.data.getlist("roles", [])
        country = request.data.get("country_code")
        timezone = request.data.get("timezone")
        phone = request.data.get("phone")
        name = request.data.get("name")
        title_id = request.data.get("job_title_id")
        active = request.data.get("active") in TRUTHFUL_INPUT_VALUES
        colour = request.data.get("colour")
        set_verified = request.data.get("set_verified")
        errors = []
        if user_id is not None:
            try:
                user = User.objects.update_user(
                    user_id=user_id,
                    name=name,
                    password=password,
                    groups=roles,
                    country=country,
                    timezone=timezone,
                    phone=phone,
                    job_title_id=title_id,
                    is_active=active,
                    colour=colour,
                    set_verified=set_verified,
                )
                return ResponseSuccess(
                    {"result": user.to_dict()}, http_status=status.HTTP_201_CREATED
                )
            except ValidationError as exc:
                raise InvalidRequestParams(detail={"errors": {"password": exc.messages}})
        else:
            missing_keys = self.validate_required_fields(request)
            if not missing_keys:
                try:
                    user = User.objects.create_user(
                        email=email.lower(),
                        password=password,
                        name=name,
                        groups=roles,
                        assign_default_groups=False,
                        country=country,
                        timezone=timezone,
                        phone=phone,
                        job_title_id=title_id,
                        is_active=active,
                    )
                except IntegrityError:
                    raise IntegrityErrorRequest(
                        detail={"errors": {"email": f"Email {email} already exists"}}, code="email"
                    )
                except ValidationError as exc:
                    raise InvalidRequestParams(detail={"errors": {"password": exc.messages}})
                else:
                    return ResponseSuccess(
                        {"result": user.to_dict()}, http_status=status.HTTP_201_CREATED
                    )
            else:
                raise InvalidRequestParams(
                    detail={"errors": {k: f"{k} is required" for k in missing_keys}},
                    code="missing_keys",
                )

    @transaction.atomic
    def delete(self, request, user_id, *args, **kwargs):
        user = User.objects.get(id=user_id)
        user_stats = user.statistics()
        purge = user_stats.get("non_draft_subs") == 0
        if purge:
            user.delete(purge=purge)
        else:
            user.delete(purge=False, anonymize=True)
        return ResponseSuccess({"result": "deleted"}, http_status=status.HTTP_201_CREATED)


class SystemParameterApiView(TradeRemediesApiView):
    """
    Get or set system parameters.
    System params are predefined key value pairs, where value can
    be of any type. A content type can be determined as well which will
    result in the value being treated as a unique id of that content type model.

    ### GET
    `/core/systemparams/`
    Get all system parameters

    ### POST
    `/core/systemparams/`
    Update a parameter value

    ### Parameters:
    `key` the key name
    `value` the value to set
    `content_type` one of the available content type names
    """

    def get(self, request, *args, **kwargs):
        key = request.query_params.get("key") or kwargs.get("key")
        editable = request.query_params.get("editable") or False
        system_params = SystemParameter.objects.filter()
        if key:
            system_params = system_params.filter(key=key.upper()).first()
            if system_params:
                response = {"result": system_params.to_dict(user=request.user)}
            else:
                raise NotFoundApiExceptions(f"System param key {key} not found")
        else:
            if editable:
                system_params = system_params.filter(editable=True)
            response = {"results": [param.to_dict(user=request.user) for param in system_params]}
        return ResponseSuccess(response)

    def post(self, request, *args, **kwargs):
        key = request.data.get("key")
        try:
            system_param = SystemParameter.objects.get(key=key)
            if system_param.data_type == "list":
                value = request.data.getlist("value")
            else:
                value = request.data.get("value")
            system_param.set_value(value)
            system_param.save()
            return self.get(request, key=key)
        except SystemParameter.DoesNotExist:
            raise NotFoundApiExceptions(f"System param key {key} not found")


class FeatureFlagApiView(TradeRemediesApiView):
    def get(self, request, key, *args, **kwargs):
        try:
            response = {"result": is_enabled(key)}
        except FeatureFlagNotFound:
            raise NotFoundApiExceptions(f"Feature flag {key} not found")
        return ResponseSuccess(response)


class NotificationTemplateAPI(TradeRemediesApiView):
    """
    Return a notifier template data based on a named system parameter.
    The system paramter should map to a notifier template id.
    Sending this request as a post will return a preview of the notification
    and will expect a value dict to assist in the parsing
    """

    def get(self, request, template_key, *args, **kwargs):
        template_id = SystemParameter.get(template_key)
        template = get_template(template_id)
        return ResponseSuccess({"result": template})

    def post(self, request, template_key, *args, **kwargs):
        template_id = SystemParameter.get(template_key)
        values = request.data.get("values") or {}
        if isinstance(values, str):
            values = json.loads(values)
        template = get_preview(template_id, values)
        return ResponseSuccess({"result": template})


class PublicUserApiView(TradeRemediesApiView):
    allowed_groups = {
        "GET": SECURITY_GROUPS_PUBLIC,
    }
    required_keys = ["email", "password"]

    def get(self, request, organisation_id=None, user_id=None, *args, **kwargs):
        """
        Return all one or all public users
        """
        if not organisation_id:
            organisation = request.user.owner_of
            if organisation:
                organisation_id = organisation.id
        else:
            organisation = Organisation.objects.get(id=organisation_id)
        if not organisation:
            raise InvalidRequestParams("User is not an owner of any organisation")
        if user_id is not None and (
            user_id == request.user.id
            or request.user.groups.filter(name=SECURITY_GROUP_ORGANISATION_OWNER).exists()
        ):
            user = User.objects.get(id=user_id)
            _user = user.to_dict(organisation=organisation)
            _user["case_ids"] = [str(case.id) for case in user.get_cases(organisation)]
            return ResponseSuccess({"result": _user})
        else:
            users = (
                User.objects.exclude(groups__name=SECURITY_GROUP_SUPER_USER)
                .exclude(deleted_at__isnull=False)
                .filter(groups__name__in=SECURITY_GROUPS_PUBLIC)
                .filter(organisationuser__organisation__id=organisation_id)
                .distinct()
            )
            return ResponseSuccess(
                {"results": [user.to_dict(organisation=organisation) for user in users]}
            )

    @transaction.atomic  # noqa: C901
    def post(self, request, organisation_id, user_id=None, invitation_id=None, *args, **kwargs):

        group = None
        password = None
        invitation = None
        contact = None
        cases = None
        errors = {}

        # If this is not an organisation owner, they can only update their own details
        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid parameters or access denied")
        if user_id and (user_id != request.user.id):
            if not request.user.groups.filter(name=SECURITY_GROUP_ORGANISATION_OWNER).exists():
                raise InvalidAccess("Only organisation owners can update other members")
        elif not user_id and invitation_id:
            try:
                invitation = Invitation.objects.get(id=invitation_id, organisation=organisation)
            except Invitation.DoesNotExist:
                raise NotFoundApiExceptions("Invalid parameters of access denied")
        request_data = request.data.dict()
        if invitation:
            request_data["group"] = invitation.meta["group"]
            request_data["active"] = invitation.meta["is_active"]
            request_data["case_spec"] = invitation.meta["case_spec"]
            request_data["email"] = invitation.email
            request_data["contact"] = invitation.contact
            organisation = invitation.organisation
        if request_data.get("group"):
            try:
                group = Group.objects.filter(name__in=SECURITY_GROUPS_PUBLIC).get(
                    name=request_data.get("group")
                )
            except Group.DoesNotExist:
                errors["group"] = "Invalid security group"
        if not request_data.get("email"):
            errors["email"] = "Email is required"
        if not request_data.get("name"):
            errors["name"] = "Name is required"
        if not user_id:
            try:
                User.objects.get(email=request.data.get("email"))
                errors["email"] = "User email already exists"
            except User.DoesNotExist:
                pass
        if request_data.get("password"):
            if request_data.get("password") == request_data.get("password_confirm"):
                password = request_data.get("password")
                try:
                    invalid_password = validate_password(password)
                    if invalid_password:
                        errors["password"] = invalid_password
                except ValidationError as exc:
                    errors["password"] = exc.messages
            else:
                errors["password"] = "Password not the same as confirmation"
        elif not user_id:
            errors["password"] = "Password is required"
        if request_data.get("terms_required") and not request_data.get("terms"):
            errors["terms"] = "Please accept the terms of use"

        if not errors:
            if user_id is not None:
                user = User.objects.get(id=user_id, organisationuser__organisation=organisation)
            else:
                user = User()
            # contact = user.contact
            user, _ = user.load_attributes(request_data)
            # contact.phone = request.data.get('phone', contact.phone)
            if request.data.get("active") is not None:
                is_active = request_data.get("active") in TRUTHFUL_INPUT_VALUES
                if is_active != user.is_active and not (user == request.user and not is_active):
                    user.is_active = is_active
            if password:
                user.set_password(request_data.get("password"))
            user.save()
            if group:
                user.groups.clear()
                user.groups.add(group)
                organisation.assign_user(user, group)
            cases = request_data.get("case_spec")
            phone = request_data.get("phone")
            if cases:
                cases = json.loads(cases) if isinstance(cases, str) else cases
                user.set_cases(organisation, cases, request.user)
            if request.data.getlist("unassign_case_id"):
                for case_id in request.data.getlist("unassign_case_id"):
                    user.remove_from_case(case_id, created_by=request.user)
                    # todo: remove contact from case too
            profile = user.userprofile
            if profile.contact:
                contact = profile.contact
                contact.organisation = organisation
                contact.address = request_data.get("address", contact.address)
                contact.country = request.data.get("country_code", contact.country.code)
                if not contact.address:
                    contact.address_from_org(organisation)
                contact.phone = convert_to_e164(phone, str(contact.country))
                contact._disable_audit = True
                contact.save()
            if not profile.email_verified_at or not profile.email_verify_code:
                profile.verify_email()
            return ResponseSuccess(
                {"result": user.to_dict(organisation=organisation)},
                http_status=status.HTTP_201_CREATED,
            )
        else:
            raise InvalidRequestParams(detail={"errors": errors})


class AssignUserToCaseView(TradeRemediesApiView):
    def get(self, request, organisation_id, user_id=None):
        from cases.models import Submission

        organisation = Organisation.objects.get(id=organisation_id)
        if user_id:
            user = User.objects.get(id=user_id)
            contact_ids = [user.contact.id]
        else:
            users = organisation.users
            contact_ids = users.values_list("user__userprofile__contact", flat=True)
        submissions = Submission.objects.filter(
            (Q(status__draft=True) | Q(status__received=True)),
            contact_id__in=contact_ids,
            created_by__in=users.values_list("user", flat=True),
            type__key="assign",
        )
        return ResponseSuccess({"results": [submission.to_dict() for submission in submissions]})

    @transaction.atomic
    def post(
        self,
        request,
        organisation_id,
        user_id,
        case_id,
        representing_id=None,
        submission_id=None,
        invite_id=None,
    ):
        from cases.models import get_case

        primary = request.data.get("primary")
        remove = request.data.get("remove")
        try:
            user_organisation = Organisation.objects.get(id=organisation_id)
            if representing_id:
                representing = Organisation.objects.get(id=representing_id)
            else:
                representing = user_organisation
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid parameters or access denied")
        if not request.user.is_tra() and user_id and (user_id != request.user.id):
            if not request.user.groups.filter(name=SECURITY_GROUP_ORGANISATION_OWNER).exists():
                raise InvalidAccess("Only organisation owners can update other members")
        case = get_case(case_id)
        user = User.objects.get(id=user_id, organisationuser__organisation=user_organisation)
        if not remove:
            user.assign_to_case(case=case, organisation=representing, created_by=request.user)
            user.contact.add_to_case(
                case=case,
                organisation=representing,
                primary=bool(primary),
            )
            context = {
                "case_name": case.name,
                "case_number": case.reference,
                "company_name": user_organisation.name,
                "representing_clause": f" representing {representing.name}",
                "login_url": public_login_url(),
            }
            context["footer"] = notify_footer(notify_contact_email(context.get("case_number")))
            context["full_name"] = user.contact.name or user.name
            audit_kwargs = {
                "audit_type": AUDIT_TYPE_NOTIFY,
                "case": case,
                "user": user,
                "model": user.contact,
            }
            send_mail(
                email=user.contact.email,
                context=context,
                template_id=SystemParameter.get("NOTIFY_USER_ASSIGNED_TO_CASE"),
                audit_kwargs=audit_kwargs,
            )
        else:
            user.remove_from_case(case_id, created_by=request.user, representing_id=representing_id)
            user.contact.remove_from_case(case, organisation=representing)

        return ResponseSuccess(
            {
                "result": {
                    "user": user.to_dict(),
                    "case": case.to_embedded_dict(),
                    "primary": primary,
                    "assigned": not remove,
                }
            }
        )


class MyAccountView(UserApiView):
    """
    Sub-class of the UserApiView allowing any authenticated TRA user to view
    and update their own user profile.
    """

    allowed_groups = {"GET": SECURITY_GROUPS_TRA, "POST": SECURITY_GROUPS_TRA}

    def get(self, request, *args, **kwargs):
        return super().get(request, user_id=request.user.id, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return super().post(request, user_id=request.user.id, *args, **kwargs)


class JobTitlesView(TradeRemediesApiView):
    """
    Return all available job titles

    `GET /core/jobtitles/`
    """

    def get(self, request, user_group=None, *args, **kwargs):
        job_titles = JobTitle.objects.all().order_by("name")
        return ResponseSuccess(
            {"results": [{"id": title.id, "name": title.name} for title in job_titles]}
        )


class CreatePendingUserAPI(TradeRemediesApiView):
    """
    Create a pending user invitation.
    A pending user invite is wrapped in an invitation model and contains all the data
    required to generate the user once they confirm and complete registration.
    If the user invited already exists, a dummy invite is create to avoid exposing that fact,
    and the user is notified that this has happened.

    If an invitation id is provided, the existing invite, if valid, not yet accepted, and the email
    still matches the request, will update it's parameters.
    If the invite id is not found a 404 exception
    will be raise, otherwise a new invite will be created.

    The case spec is a list of dicts in the following format, specifying which cases to assign the
    contact to, and if they are the primary contact for that case.
            [
                {'case': 'CASE-ID', 'primary': True|False}
            ]
    """

    def post(self, request, organisation_id, invitation_id=None, *args, **kwargs):  # noqa: C901
        from invitations.models import Invitation

        case_spec = request.data.get("case_spec") or []
        data = pluck(request.data, ["email", "name", "group", "phone"])
        data["is_active"] = request.data.get("active", "False").upper() == "TRUE"
        organisation = Organisation.objects.get(id=organisation_id)
        user = None
        contact = None
        data["case_spec"] = json.loads(case_spec) if isinstance(case_spec, str) else case_spec
        if invitation_id:
            try:
                invite = Invitation.objects.get(
                    id=invitation_id,
                    organisation=organisation,
                    deleted_at__isnull=True,
                )
                if invite.accepted_at or data["email"] != invite.email:
                    invitation_id = None
                else:
                    if data and data.get("email"):
                        data["email"] = data["email"].lower()
                    invite.meta = data
                    invite.save()
                    contact = invite.contact
                    _save_contact = False
                    if contact.phone != data.get("phone"):
                        contact.phone = convert_to_e164(
                            data["phone"],
                            data.get("country", request.user.userprofile.country.code),
                        )
                        _save_contact = True
                    if contact.name != data.get("name"):
                        contact.name = data["name"]
                        _save_contact = True
                    if _save_contact:
                        contact.save()
            except Invitation.DoesNotExist:
                raise NotFoundApiExceptions("Invalid invitation")
        if not invitation_id:
            try:
                user = User.objects.get(email=data.get("email").strip().lower())
                # if the user already exists, send an email to the user and leave it at that.
                invite = Invitation.objects.invite_existing_user(
                    user=user,
                    organisation=organisation,
                    invited_by=request.user,
                    name=data.get("name"),
                )
            except User.DoesNotExist:
                invite = Invitation.objects.create_user_invite(
                    user_email=data["email"].lower(),
                    organisation=organisation,
                    invited_by=request.user,
                    meta=data,
                )
        return ResponseSuccess(
            {
                "result": {
                    "user": user.to_dict() if user else None,
                    "contact": contact.to_dict() if contact else None,
                    "invite": invite.to_dict(),
                }
            }
        )

    def delete(self, request, organisation_id, invitation_id, *args, **kwargs):
        try:
            invite = Invitation.objects.get(id=invitation_id, organisation=organisation_id)
            invite.set_user_context(request.user)
            if not invite.accepted_at:
                invite.contact.delete()
                invite.delete()
            else:
                raise Invitation.DoesNotExist()
            return ResponseSuccess({"result": {"id": str(invitation_id), "deleted": True}})
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid invitation")


class FeedbackExport(TradeRemediesApiView):
    """
    Feedback data export
    """

    def get(self, request, form_id, *args, **kwargs):
        mimetypes.init()
        form = FeedbackForm.objects.get(id=form_id)
        export_file = feedback_export(form)
        mime_type = mimetypes.guess_type(export_file.name, False)[0]
        response = HttpResponse(export_file.read(), content_type=mime_type)
        response["Content-Disposition"] = "attachment; filename=Feedback-export.xls"
        return response
