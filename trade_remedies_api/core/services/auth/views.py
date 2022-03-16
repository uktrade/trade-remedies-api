import datetime
import logging

from axes.decorators import axes_dispatch
from axes.utils import reset
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from notifications_python_client.errors import HTTPError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import APIView

from core.models import PasswordResetRequest, SystemParameter, TwoFactorAuth, User, UserProfile
from core.notifier import send_mail
from core.services.base import ResponseError, ResponseSuccess, TradeRemediesApiView
from core.services.exceptions import InvalidRequestParams
from invitations.models import Invitation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)
from .serializers import (
    AuthenticationSerializer,
    EmailAvailabilitySerializer,
    PasswordResetRequestSerializer,
    PasswordSerializer,
    RegistrationSerializer,
    TwoFactorAuthRequestSerializer,
    TwoFactorAuthVerifySerializer,
    VerifyEmailSerializer,
)

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
    authentication_classes = ()

    @staticmethod
    def post(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        serializer = EmailAvailabilitySerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return ResponseSuccess({"result": {"available": True}})
        except DRFValidationError:
            return ResponseSuccess({"result": {"available": False}})


@method_decorator(axes_dispatch, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class AuthenticationView(APIView):
    authentication_classes = ()
    """Authentication View.
    Accepts a user's login credentials and returns an access token.
    """

    @staticmethod
    def post(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Arguments:
            request: a Django Request object, must contain in the POST body:
                - email: Valid email address.
                - password: Valid password.
        Returns:
            HttpResponse response with the user's token and user data
        Raises:
            AccessDenied if request fails.
        """
        serializer = AuthenticationSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.validated_data["user"]
            email = serializer.validated_data["email"]

            code = request.data.get("code")
            case_id = request.data.get("case_id")
            user_agent = request.META.get("HTTP_X_USER_AGENT")

            login(request, user)  # Logging the user in
            reset(username=email)  # Reset any remaining access attempts
            invites = Invitation.objects.validate_all_pending(
                user, code, case_id
            )  # validate all pending invitations
            if invites:
                user.refresh_from_db()

            # Do we need to redirect the user after this? i.e. to 2fa (public users are always prompted)
            if not user.is_tra() or user.should_two_factor(user_agent=user_agent):
                user.twofactorauth.two_factor_auth(user_agent=user_agent)

            return ResponseSuccess(serializer.response_dict, http_status=status.HTTP_200_OK)

    def perform_authentication(self, request):
        """Perform Authentication.

        Method required to perform lazy authentication of the user for this end point.
        """
        pass


class RegistrationAPIView(APIView):
    authentication_classes = ()

    @transaction.atomic  # noqa: C901
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Arguments:
            request: a Django Request object:
        Returns:
            HttpResponse response with the user's token and user data
        Raises:
            serializers.ValidationError if request invalid.
        """
        serializer = RegistrationSerializer(
            data=request.data, context={"request": request}, many=False
        )
        if serializer.is_valid():
            serializer.is_valid(raise_exception=True)
            # if code and case are provided, validate the invite, do not accept
            invitation = None
            code = serializer.initial_data["code"]
            case_id = serializer.initial_data["case_id"]

            if code and case_id:
                invitation = Invitation.objects.get_invite_by_code(code, case_id)
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
                if serializer.initial_data["confirm_invited_org"] == "true":
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
                user = serializer.save(groups=groups, **contact_kwargs)
                invitation.process_invitation(
                    user, accept=accept, register_interest=register_interest
                )
            else:
                user = serializer.save()

            return ResponseSuccess({"result": user.to_dict()}, http_status=status.HTTP_201_CREATED)
        else:
            if serializer.errors.get("email", []) == ["User already exists."]:
                # If the email already exists,
                # notify the original user and pretend registration completed ok.
                user = serializer.get_user(serializer.initial_data["email"])
                template_id = SystemParameter.get("NOTIFY_EMAIL_EXISTS")
                send_mail(user.email, {"full_name": user.name}, template_id)

                return ResponseSuccess(
                    {
                        "result": {
                            "email": serializer.initial_data["email"],
                            "id": None,
                        }
                    },
                    http_status=status.HTTP_201_CREATED,
                )
            return ResponseError(serializer.errors)


class TwoFactorRequestAPI(TradeRemediesApiView):
    """
    Request or submit two-factor authentication
    """

    @staticmethod
    def get(request, delivery_type=None, *args, **kwargs):
        twofactorauth_object = request.user.twofactorauth
        serializer = TwoFactorAuthRequestSerializer(
            data={"delivery_type": delivery_type}, instance=twofactorauth_object
        )
        if serializer.is_valid():
            serializer.save()

            if twofactorauth_object.is_locked():
                locked_until = twofactorauth_object.locked_until + datetime.timedelta(seconds=15)
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
                send_report = twofactorauth_object.two_factor_auth(
                    user_agent=request.META["HTTP_X_USER_AGENT"], delivery_type=delivery_type
                )
            except HTTPError:
                raise InvalidRequestParams("Could not send code to phone")
            except Exception as exc:
                raise InvalidRequestParams(f"Error occurred when sending code: {exc}")
            if send_report:
                send_report["delivery_type"] = serializer.validated_data["delivery_type"]
            return ResponseSuccess(
                {
                    "result": send_report,
                }
            )
        else:
            raise InvalidRequestParams(
                f"Error occurred when sending 2fa code to {twofactorauth_object.user}"
            )

    @staticmethod
    def post(request, *args, **kwargs):
        twofactorauth_object = request.user.twofactorauth
        serializer = TwoFactorAuthVerifySerializer(
            data=request.data, instance=twofactorauth_object, context={"request": request}
        )
        if serializer.is_valid():
            request.user.refresh_from_db()
            twofactorauth_object.success(user_agent=request.META["HTTP_X_USER_AGENT"])
            return ResponseSuccess({"result": request.user.to_dict()})
        else:
            twofactorauth_object.fail()
            raise InvalidRequestParams("Invalid code")


class RequestPasswordReset(APIView):
    @staticmethod
    def get(request, *args, **kwargs):
        email = request.GET.get("email")
        logger.info(f"Password reset request for: {email}")
        # Invalidate all previous PasswordResetRequest objects for this user
        PasswordResetRequest.objects.reset_request(email=email)
        return ResponseSuccess({"result": True})


class PasswordResetForm(APIView):
    @staticmethod
    def get(request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.GET)
        user_pk = request.GET["user_pk"]
        logger.info(f"Password reset link clicked for: {user_pk}")
        if valid := serializer.is_valid():
            logger.info(f"Password reset link valid for: {user_pk}")
        else:
            logger.info(f"Password reset link invalid for: {user_pk}")

        return ResponseSuccess({"result": valid})

    @staticmethod
    def post(request, *args, **kwargs):
        token_serializer = PasswordResetRequestSerializer(data=request.data)
        password_serializer = PasswordSerializer(data=request.data)
        user_pk = request.data.get("user_pk")

        if token_serializer.is_valid() and password_serializer.is_valid():
            if PasswordResetRequest.objects.password_reset(
                token_serializer.initial_data["token"],
                token_serializer.initial_data["user_pk"],
                token_serializer.initial_data["password"],
            ):
                logger.info(f"Password reset completed for: {user_pk}")
                return ResponseSuccess({"result": {"reset": True}}, http_status=status.HTTP_200_OK)
        else:
            logger.warning(f"Could not reset password for user {user_pk}")
            raise InvalidRequestParams("Invalid or expired link")


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

            serializer = VerifyEmailSerializer(data={"code": code}, context={"profile": profile})
            if serializer.is_valid():
                profile.email_verified_at = timezone.now()
                profile.save()
                user.refresh_from_db()
                return ResponseSuccess({"result": user.to_dict()})
            else:
                raise InvalidRequestParams(serializer.errors)
        elif not request.user.is_anonymous:
            response = request.user.userprofile.verify_email()
            return ResponseSuccess({"result": response})
        else:
            raise InvalidRequestParams("User unknown")
