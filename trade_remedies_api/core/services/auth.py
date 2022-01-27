import datetime
import logging
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import User, UserProfile, SystemParameter, PasswordResetRequest, TwoFactorAuth
from core.notifier import send_mail
from invitations.models import Invitation
from django.conf import settings
from notifications_python_client.errors import HTTPError
from axes.utils import reset
from axes.decorators import axes_dispatch
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
    ENVIRONMENT_GROUPS,
)
from core.constants import CONTENT_EMAIL_EXISTS
from config.version import __version__
from .base import TradeRemediesApiView, ResponseSuccess, ResponseError
from .exceptions import InvalidRequestParams, AccessDenied, InvalidRequestLockout


logger = logging.getLogger(__name__)


class ApiHealthView(TradeRemediesApiView):
    """Health check.

    Perform a health check and return a status report.
    """

    @staticmethod
    def get(request, *args, **kwargs):
        """Get health.

        :returns (HttpResponse): health status.
        """
        return ResponseSuccess({"health": "OK"})


class EmailAvailabilityAPI(APIView):
    authentication_classes = []

    @staticmethod
    def post(request, *args, **kwargs):
        email = request.data.get("email")
        if not email:
            raise InvalidRequestParams("Email is required")
        try:
            User.objects.get(email=email.strip().lower())
            return ResponseSuccess({"result": {"available": False}})
        except User.DoesNotExist:
            return ResponseSuccess({"result": {"available": True}})


@method_decorator(axes_dispatch, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class AuthenticationView(APIView):
    authentication_classes = []
    """Authentication View.

    Accepts a user login credentials and provide an access token.
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """Post.

        :param (Request) request: Should contain:
          - email: Valid email address.
          - password: Valid password.
        :returns (HttpResponse): Responds with the user's token and user data.
        :raises: AccessDenied if request fails.
        """
        email = request.data.get("email")
        password = request.data.get("password")
        code = request.data.get("code")
        case_id = request.data.get("case_id")
        user_agent = request.META.get("HTTP_X_USER_AGENT")
        if not email or not password:
            raise InvalidRequestParams("Email and password are required to log in.")
        email = email.strip().lower()
        user = authenticate(email=email, password=password.strip(), request=request)
        if not user or (user and user.deleted_at):
            raise AccessDenied(
                "You have entered an incorrect email address or password. "
                "Please try again or click on the Forgotten password link below."
            )
        if user.is_active:
            # ensure the origin of the request is allowed for this user group
            env_key = request.META.get("HTTP_X_ORIGIN_ENVIRONMENT")
            if not env_key or not user.has_groups(groups=ENVIRONMENT_GROUPS[env_key]):
                if not env_key:
                    logger.error(f"env_key not defined while logging  {user.email} ")
                else:
                    logger.error(
                        f" env_key = {env_key};"
                        f" {user.email} does not have access "
                        f"to {ENVIRONMENT_GROUPS[env_key]}"
                    )
                raise AccessDenied("Invalid access to environment")
            login(request, user)
            auth_token = user.get_access_token()
            # reset any remaining access attempts
            reset(username=email)
            # validate al pending invitations
            invites = Invitation.objects.validate_all_pending(user, code, case_id)
            if invites:
                user.refresh_from_db()
            two_factor_enabled = SystemParameter.get("ENABLE_2FA")
            is_public = not user.is_tra()
            should_2fa = user.should_two_factor(user_agent=user_agent)
            email_verified = user.userprofile.email_verified_at or not is_public
            if not email_verified:
                return ResponseSuccess(
                    {
                        "needs_verify": True,
                        "user": user.to_dict(user_agent=user_agent),
                        "version": __version__,
                    },
                    http_status=status.HTTP_201_CREATED,
                )
            if two_factor_enabled and email_verified and (is_public or should_2fa):
                try:
                    user.twofactorauth.two_factor_auth(user_agent=user_agent)
                except Exception as exc_2fa:
                    logger.error(f"Could not 2fa for {user} / {user.id}: {exc_2fa}")
            return ResponseSuccess(
                {
                    "token": str(auth_token),
                    "user": user.to_dict(user_agent=user_agent),
                    "version": __version__,
                },
                http_status=status.HTTP_201_CREATED,
            )
        else:
            raise AccessDenied("User account disabled")

    def perform_authentication(self, request):
        """Perform Authentication.

        Method required to bypass CRSF for this end point.
        """
        pass


class RegistrationAPIView(APIView):
    authentication_classes = []

    @transaction.atomic  # noqa: C901
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")
        code = request.data.get("code")
        case_id = request.data.get("case_id")
        confirm_invited_org = request.data.get("confirm_invited_org")
        errors = {}
        required_fields = ["email", "password", "name"]
        if not code and not case_id:
            required_fields.append("organisation_name")
        for key in required_fields:
            if not request.data.get(key):
                _key = key.replace("_", " ").capitalize()
                errors[key] = f"{_key} is required"
        try:
            # If the email already exists,
            # notify the original user and pretend registration completed ok.
            user = User.objects.get(email=email.strip().lower())
            template_id = SystemParameter.get("NOTIFY_EMAIL_EXISTS")
            send_mail(user.email, {"full_name": user.name}, template_id)
            return ResponseSuccess(
                {
                    "result": {
                        "email": email,
                        "id": None,
                    }
                },
                http_status=status.HTTP_201_CREATED,
            )
        except User.DoesNotExist:
            pass
        try:
            validate_password(password)
        except ValidationError as exc:
            errors["password"] = "<br/>".join(exc.messages)
        # Temp switch to lock down registrations
        if SystemParameter.get("REGISTRATION_SOFT_LOCK") and not password.startswith(
            SystemParameter.get("REGISTRATION_SOFT_LOCK_KEY")
        ):
            errors["lockdown"] = "Registrations are currently locked"
        if not errors:
            # check if email exists
            exists = User.objects.filter(email=email).exists()
            if exists:
                errors["email"] = CONTENT_EMAIL_EXISTS
            else:
                # if code and case are provided, validate the invite, do not accept
                invitation = None
                if code and case_id:
                    invitation = Invitation.objects.get_invite_by_code(code, case_id)
                user_data = request.data.dict()
                user_data["email"] = user_data["email"].lower()
                if invitation:
                    invited_organisation = invitation.organisation
                    if group := invitation.organisation_security_group:
                        if group.name == SECURITY_GROUP_THIRD_PARTY_USER:
                            # Third Party's org is on the contact not the invite
                            invited_organisation = invitation.contact.organisation
                    else:
                        invited_organisation = invitation.organisation
                    # register interest if this is the first user of this organisation
                    register_interest = not invited_organisation.has_users
                    contact_kwargs = {}
                    if confirm_invited_org == "true":
                        contact_kwargs = {
                            "contact": invitation.contact,
                        }
                    else:
                        register_interest = False
                    accept = False
                    groups = []
                    if invitation.organisation_security_group:
                        # There is a group specified so add it
                        groups.append(invitation.organisation_security_group.name)
                        accept = True
                    if invited_organisation.has_users:
                        groups.append(SECURITY_GROUP_ORGANISATION_USER)
                    else:
                        groups.append(SECURITY_GROUP_ORGANISATION_OWNER)
                    user = User.objects.create_user(
                        groups=groups,
                        **contact_kwargs,
                        **user_data,
                    )
                    profile = user.userprofile
                    profile.verify_email()
                    invitation.process_invitation(
                        user, accept=accept, register_interest=register_interest
                    )
                else:
                    user = User.objects.create_user(**user_data)
                    profile = user.userprofile
                    profile.verify_email()

                return ResponseSuccess(
                    {"result": user.to_dict()}, http_status=status.HTTP_201_CREATED
                )
        if errors:
            return ResponseError(errors)


class TwoFactorRequestAPI(TradeRemediesApiView):
    """
    Request or submit two factor authentication
    """

    @staticmethod
    def get(request, delivery_type=None, *args, **kwargs):
        delivery_type = delivery_type or TwoFactorAuth.SMS
        if delivery_type not in dict(TwoFactorAuth.DELIVERY_TYPE_CHOICES):
            raise InvalidRequestParams("Invalid 2FA delivery type requested")
        if delivery_type == TwoFactorAuth.SMS and not request.user.phone:
            delivery_type = TwoFactorAuth.EMAIL
        two_factor = request.user.twofactorauth
        two_factor.delivery_type = delivery_type
        two_factor.save()
        if two_factor.is_locked():
            locked_until = two_factor.locked_until + datetime.timedelta(seconds=15)
            locked_for_seconds = (locked_until - timezone.now()).seconds
            return ResponseSuccess(
                {
                    "result": {
                        "error": "You have entered an incorrect code too many times "
                        "and we have temporarily locked your account.",
                        "locked_until": locked_until.strftime(settings.API_DATETIME_FORMAT),
                        "locked_for_seconds": locked_for_seconds,
                    }
                }
            )
        try:
            send_report = two_factor.two_factor_auth(
                user_agent=request.META["HTTP_X_USER_AGENT"], delivery_type=delivery_type
            )
        except HTTPError:
            raise InvalidRequestParams("Could not send code to phone")
        except Exception as exc:
            raise InvalidRequestParams(f"Error occurred when sending code: {exc}")
        if send_report:
            send_report["delivery_type"] = delivery_type
        return ResponseSuccess(
            {
                "result": send_report,
            }
        )

    @staticmethod
    def post(request, *args, **kwargs):
        code = request.data.get("code")
        user_agent = request.META["HTTP_X_USER_AGENT"]
        two_factor = request.user.twofactorauth
        if two_factor.is_locked():
            raise InvalidRequestLockout(
                "You have entered an incorrect code too many times "
                "and we have temporarily locked your account."
            )
        if two_factor.validate(code):
            two_factor.success(user_agent=user_agent)
            request.user.refresh_from_db()
            return ResponseSuccess({"result": request.user.to_dict()})
        else:
            two_factor.fail()
            raise InvalidRequestParams("Invalid code")


class PasswordResetAPI(APIView):
    @staticmethod
    def get(request, *args, **kwargs):
        email = request.GET.get("email")
        code = request.GET.get("code")
        code_valid = True
        logger.info(f"Password reset request for: {email}")
        try:
            if not code:
                PasswordResetRequest.objects.reset_request(email=email)
            else:
                code_valid = PasswordResetRequest.objects.validate_code(code, validate_only=True)
        except User.DoesNotExist:
            logger.warning(f"Password reset request failed, user {email} does not exist")
        return ResponseSuccess({"result": bool(code_valid)})

    @staticmethod
    def post(request, *args, **kwargs):
        code = request.data.get("code")
        password = request.data.get("password")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise InvalidRequestParams("<br/>".join(exc.messages))
        user = PasswordResetRequest.objects.password_reset(code, password)
        if user:
            return ResponseSuccess(
                {"result": {"reset": bool(user)}}, http_status=status.HTTP_201_CREATED
            )
        else:
            raise InvalidRequestParams("Could not reset password")


class VerifyEmailAPI(TradeRemediesApiView):
    @staticmethod
    def post(request, code=None):
        if code:
            user = request.user
            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.filter(email_verify_code=code).first()
                user = profile.user
            if profile and code == profile.email_verify_code:
                profile.email_verified_at = timezone.now()
                profile.save()
                user.refresh_from_db()
                return ResponseSuccess({"result": user.to_dict()})
            else:
                raise InvalidRequestParams("Invalid verification code")
        elif not request.user.is_anonymous:
            response = request.user.userprofile.verify_email()
            return ResponseSuccess({"result": response})
        else:
            raise InvalidRequestParams("User unknown")
